from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.core.config import settings
from app.core.user_context import LEGACY_OWNER_ID, current_owner_id


class SQLiteStateStore:
    """Transactional JSON-document persistence backed by SQLite.

    Existing domain stores keep their public contracts while this adapter moves
    their durable state from scattered JSON files into one migration-managed
    database. Legacy files are read only once, on first access to a namespace.
    """

    _migration_version = 7
    _collection_tables = {
        "bills": ("bills", "id"),
        "tasks": ("tasks", "id"),
        "diaries": ("diaries", "id"),
        "attachments": ("attachments", "id"),
        "bill_candidates": ("bill_candidates", "candidate_id"),
        "task_candidates": ("task_candidates", "candidate_id"),
        "diary_candidates": ("diary_candidates", "candidate_id"),
        "audit_events": ("audit_events", "event_id"),
    }

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._local = threading.local()
        self._initialize()

    @property
    def path(self) -> Path:
        return settings.local_database_path

    @contextmanager
    def transaction(self) -> Iterator[None]:
        with self._lock:
            connection = self._active_connection()
            if connection is not None:
                self._local.depth += 1
                try:
                    yield
                finally:
                    self._local.depth -= 1
                return

            connection = self._connect()
            self._local.connection = connection
            self._local.depth = 1
            try:
                connection.execute("BEGIN IMMEDIATE")
                yield
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                self._local.connection = None
                self._local.depth = 0
                connection.close()

    def load_json(
        self,
        namespace: str,
        legacy_path: Path,
        *,
        owner_id: str | None = None,
    ) -> Any | None:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                collection = self._collection_tables.get(namespace)
                if collection is not None:
                    table_name, _ = collection
                    initialized = connection.execute(
                        "SELECT 1 FROM collection_state WHERE namespace = ?",
                        (self._scope(namespace, owner_id),),
                    ).fetchone()
                    if initialized is not None:
                        rows = connection.execute(
                            f"SELECT payload FROM {table_name} WHERE owner_id = ? "
                            "ORDER BY updated_at, record_id",
                            (owner_id,),
                        ).fetchall()
                        return [json.loads(str(row["payload"])) for row in rows]

                row = connection.execute(
                    "SELECT payload FROM state_documents WHERE namespace = ? AND owner_id = ?",
                    (namespace, owner_id),
                ).fetchone()
                if row is not None:
                    return json.loads(str(row["payload"]))

                # Legacy files are an import source only.  Reading them for a
                # newly created account would leak pre-auth local data.
                legacy_value = (
                    self._read_legacy_json(legacy_path)
                    if owner_id == LEGACY_OWNER_ID
                    else None
                )
                if legacy_value is not None:
                    self._write_json(connection, namespace, legacy_value, owner_id)
                    connection.commit()
                return legacy_value
            finally:
                connection.close()

    def save_json(self, namespace: str, value: Any, *, owner_id: str | None = None) -> None:
        owner_id = owner_id or current_owner_id()
        connection = self._active_connection()
        if connection is not None:
            self._write_json(connection, namespace, value, owner_id)
            return

        with self._lock:
            connection = self._connect()
            try:
                self._write_json(connection, namespace, value, owner_id)
                connection.commit()
            finally:
                connection.close()

    def namespace_exists(self, namespace: str, *, owner_id: str | None = None) -> bool:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                if namespace in self._collection_tables:
                    return connection.execute(
                        "SELECT 1 FROM collection_state WHERE namespace = ?",
                        (self._scope(namespace, owner_id),),
                    ).fetchone() is not None
                return connection.execute(
                    "SELECT 1 FROM state_documents WHERE namespace = ? AND owner_id = ?",
                    (namespace, owner_id),
                ).fetchone() is not None
            finally:
                connection.close()

    def diagnostics(self) -> dict[str, Any]:
        with self._lock:
            connection = self._connect()
            try:
                row = connection.execute(
                    """
                    SELECT
                        (SELECT COUNT(*) FROM state_documents) +
                        (SELECT COUNT(*) FROM collection_state) AS count
                    """
                ).fetchone()
                version_row = connection.execute(
                    "SELECT MAX(version) AS version FROM schema_migrations"
                ).fetchone()
                return {
                    "backend": "sqlite",
                    "path": str(self.path),
                    "schema_version": int(version_row["version"] or 0),
                    "namespace_count": int(row["count"]),
                }
            finally:
                connection.close()

    def claim_legacy_owner(self, owner_id: str) -> None:
        """Assign pre-auth local data to the first registered account."""
        with self.transaction():
            connection = self._active_connection()
            if connection is None:
                raise RuntimeError("SQLite transaction connection is unavailable")
            for table_name, _ in self._collection_tables.values():
                connection.execute(
                    f"UPDATE {table_name} SET owner_id = ? WHERE owner_id = ?",
                    (owner_id, LEGACY_OWNER_ID),
                )
            connection.execute(
                "UPDATE state_documents SET owner_id = ? "
                "WHERE owner_id = ? AND namespace != 'agent_knowledge'",
                (owner_id, LEGACY_OWNER_ID),
            )
            for namespace in (*self._collection_tables.keys(),):
                connection.execute(
                    "UPDATE collection_state SET namespace = ? "
                    "WHERE namespace = ?",
                    (self._scope(namespace, owner_id), self._scope(namespace, LEGACY_OWNER_ID)),
                )

    def append_agent_trace(self, trace: dict[str, Any], *, owner_id: str | None = None) -> None:
        owner_id = owner_id or current_owner_id()
        payload = json.dumps(trace.get("payload", {}), ensure_ascii=False, separators=(",", ":"))
        values = (
            str(trace["trace_id"]),
            owner_id,
            str(trace["occurred_at"]),
            trace.get("request_id"),
            str(trace["message_id"]),
            str(trace["intent"]),
            str(trace["action_type"]),
            str(trace["model_provider"]),
            str(trace["model_strategy"]),
            str(trace["outcome"]),
            float(trace["latency_ms"]),
            int(trace["function_call_count"]),
            int(trace["knowledge_hit_count"]),
            int(trace["warning_count"]),
            payload,
        )
        with self._lock:
            connection = self._connect()
            try:
                connection.execute(
                    """
                    INSERT INTO agent_execution_traces(
                        trace_id, owner_id, occurred_at, request_id, message_id,
                        intent, action_type, model_provider, model_strategy, outcome,
                        latency_ms, function_call_count, knowledge_hit_count,
                        warning_count, payload
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    values,
                )
                connection.commit()
            finally:
                connection.close()

    def list_agent_traces(self, *, owner_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                rows = connection.execute(
                    """
                    SELECT trace_id, occurred_at, request_id, message_id, intent,
                           action_type, model_provider, model_strategy, outcome,
                           latency_ms, function_call_count, knowledge_hit_count,
                           warning_count, payload
                    FROM agent_execution_traces
                    WHERE owner_id = ?
                    ORDER BY occurred_at DESC
                    LIMIT ?
                    """,
                    (owner_id, max(1, min(limit, 200))),
                ).fetchall()
                return [
                    {
                        **dict(row),
                        "payload": json.loads(str(row["payload"])),
                    }
                    for row in rows
                ]
            finally:
                connection.close()

    def agent_trace_summary(self, *, owner_id: str | None = None) -> dict[str, Any]:
        traces = self.list_agent_traces(owner_id=owner_id, limit=200)
        latencies = sorted(float(trace["latency_ms"]) for trace in traces)
        outcomes: dict[str, int] = {}
        for trace in traces:
            outcome = str(trace["outcome"])
            outcomes[outcome] = outcomes.get(outcome, 0) + 1
        percentile_index = max(0, round((len(latencies) - 1) * 0.95))
        return {
            "trace_count": len(traces),
            "outcomes": outcomes,
            "average_latency_ms": round(sum(latencies) / len(latencies), 2) if latencies else 0.0,
            "p95_latency_ms": round(latencies[percentile_index], 2) if latencies else 0.0,
        }

    def append_agent_quality_feedback(self, feedback: dict[str, Any], *, owner_id: str | None = None) -> None:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                connection.execute(
                    """
                    INSERT INTO agent_quality_feedback(
                        feedback_id, owner_id, message_id, verdict, expected_intent,
                        expected_category, note, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(feedback["feedback_id"]),
                        owner_id,
                        str(feedback["message_id"]),
                        str(feedback["verdict"]),
                        feedback.get("expected_intent"),
                        feedback.get("expected_category"),
                        feedback.get("note"),
                        str(feedback["created_at"]),
                    ),
                )
                connection.commit()
            finally:
                connection.close()

    def list_agent_quality_feedback(self, *, owner_id: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                rows = connection.execute(
                    """
                    SELECT feedback_id, message_id, verdict, expected_intent,
                           expected_category, note, created_at
                    FROM agent_quality_feedback
                    WHERE owner_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (owner_id, max(1, min(limit, 1000))),
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                connection.close()

    def append_agent_quality_evaluation(self, run: dict[str, Any], *, owner_id: str | None = None) -> None:
        owner_id = owner_id or current_owner_id()
        payload = json.dumps(run, ensure_ascii=False, separators=(",", ":"), default=str)
        with self._lock:
            connection = self._connect()
            try:
                connection.execute(
                    """
                    INSERT INTO agent_quality_evaluation_runs(
                        run_id, owner_id, created_at, pass_rate, payload
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        str(run["run_id"]),
                        owner_id,
                        str(run["created_at"]),
                        float(run["pass_rate"]),
                        payload,
                    ),
                )
                connection.commit()
            finally:
                connection.close()

    def latest_agent_quality_evaluation(self, *, owner_id: str | None = None) -> dict[str, Any] | None:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                row = connection.execute(
                    """
                    SELECT payload FROM agent_quality_evaluation_runs
                    WHERE owner_id = ?
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (owner_id,),
                ).fetchone()
                return json.loads(str(row["payload"])) if row else None
            finally:
                connection.close()

    def list_agent_quality_evaluations(
        self,
        *,
        owner_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Return recent runs so callers can select a compatible baseline."""
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                rows = connection.execute(
                    """
                    SELECT payload FROM agent_quality_evaluation_runs
                    WHERE owner_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (owner_id, max(1, min(limit, 500))),
                ).fetchall()
                return [json.loads(str(row["payload"])) for row in rows]
            finally:
                connection.close()

    def create_async_job(self, job: dict[str, Any], *, owner_id: str | None = None) -> None:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                connection.execute(
                    """
                    INSERT INTO async_jobs(
                        job_id, owner_id, job_type, status, created_at, updated_at,
                        started_at, completed_at, attempt, max_attempts, result,
                        error_code, error_message
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(job["job_id"]),
                        owner_id,
                        str(job["job_type"]),
                        str(job["status"]),
                        str(job["created_at"]),
                        str(job["updated_at"]),
                        job.get("started_at"),
                        job.get("completed_at"),
                        int(job.get("attempt", 0)),
                        int(job.get("max_attempts", 1)),
                        self._json_value(job.get("result")),
                        job.get("error_code"),
                        job.get("error_message"),
                    ),
                )
                connection.commit()
            finally:
                connection.close()

    def get_async_job(self, job_id: Any, *, owner_id: str | None = None) -> dict[str, Any] | None:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                row = connection.execute(
                    "SELECT * FROM async_jobs WHERE job_id = ? AND owner_id = ?",
                    (str(job_id), owner_id),
                ).fetchone()
                return self._async_job_row(row) if row else None
            finally:
                connection.close()

    def list_async_jobs(self, *, owner_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                rows = connection.execute(
                    """
                    SELECT * FROM async_jobs WHERE owner_id = ?
                    ORDER BY created_at DESC LIMIT ?
                    """,
                    (owner_id, max(1, min(limit, 100))),
                ).fetchall()
                return [self._async_job_row(row) for row in rows]
            finally:
                connection.close()

    def claim_async_job(self, job_id: Any, *, owner_id: str | None = None) -> dict[str, Any] | None:
        owner_id = owner_id or current_owner_id()
        now = self._now()
        with self._lock:
            connection = self._connect()
            try:
                updated = connection.execute(
                    """
                    UPDATE async_jobs
                    SET status = 'running', started_at = ?, updated_at = ?, attempt = attempt + 1
                    WHERE job_id = ? AND owner_id = ? AND status = 'queued'
                    """,
                    (now, now, str(job_id), owner_id),
                ).rowcount
                if not updated:
                    connection.commit()
                    return None
                row = connection.execute(
                    "SELECT * FROM async_jobs WHERE job_id = ? AND owner_id = ?",
                    (str(job_id), owner_id),
                ).fetchone()
                connection.commit()
                return self._async_job_row(row) if row else None
            finally:
                connection.close()

    def succeed_async_job(self, job_id: Any, result: dict[str, Any], *, owner_id: str | None = None) -> None:
        self._finish_async_job(job_id, "succeeded", result=result, owner_id=owner_id)

    def fail_async_job(
        self,
        job_id: Any,
        *,
        error_code: str,
        error_message: str,
        owner_id: str | None = None,
    ) -> None:
        self._finish_async_job(
            job_id,
            "failed",
            error_code=error_code,
            error_message=error_message,
            owner_id=owner_id,
        )

    def cancel_async_job(self, job_id: Any, *, owner_id: str | None = None) -> dict[str, Any] | None:
        return self._change_async_job_status(job_id, "cancelled", ("queued",), owner_id=owner_id)

    def retry_async_job(self, job_id: Any, *, owner_id: str | None = None) -> dict[str, Any] | None:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                now = self._now()
                updated = connection.execute(
                    """
                    UPDATE async_jobs
                    SET status = 'queued', updated_at = ?, started_at = NULL, completed_at = NULL,
                        error_code = NULL, error_message = NULL, result = NULL
                    WHERE job_id = ? AND owner_id = ? AND status IN ('failed', 'cancelled')
                      AND attempt < max_attempts
                    """,
                    (now, str(job_id), owner_id),
                ).rowcount
                row = connection.execute(
                    "SELECT * FROM async_jobs WHERE job_id = ? AND owner_id = ?",
                    (str(job_id), owner_id),
                ).fetchone()
                connection.commit()
                return self._async_job_row(row) if updated and row else None
            finally:
                connection.close()

    def recover_async_jobs(self, *, owner_id: str | None = None) -> list[dict[str, Any]]:
        """Mark interrupted work explicitly and return safely queued jobs to dispatch."""
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                now = self._now()
                connection.execute(
                    """
                    UPDATE async_jobs
                    SET status = 'failed', completed_at = ?, updated_at = ?,
                        error_code = 'worker_interrupted',
                        error_message = 'Worker stopped before the job completed.'
                    WHERE owner_id = ? AND status = 'running'
                    """,
                    (now, now, owner_id),
                )
                rows = connection.execute(
                    "SELECT * FROM async_jobs WHERE owner_id = ? AND status = 'queued'",
                    (owner_id,),
                ).fetchall()
                connection.commit()
                return [self._async_job_row(row) for row in rows]
            finally:
                connection.close()

    def _finish_async_job(
        self,
        job_id: Any,
        status: str,
        *,
        result: dict[str, Any] | None = None,
        error_code: str | None = None,
        error_message: str | None = None,
        owner_id: str | None = None,
    ) -> None:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                now = self._now()
                connection.execute(
                    """
                    UPDATE async_jobs
                    SET status = ?, updated_at = ?, completed_at = ?, result = ?,
                        error_code = ?, error_message = ?
                    WHERE job_id = ? AND owner_id = ? AND status = 'running'
                    """,
                    (
                        status,
                        now,
                        now,
                        self._json_value(result),
                        error_code,
                        error_message,
                        str(job_id),
                        owner_id,
                    ),
                )
                connection.commit()
            finally:
                connection.close()

    def _change_async_job_status(
        self,
        job_id: Any,
        status: str,
        allowed_statuses: tuple[str, ...],
        *,
        owner_id: str | None = None,
    ) -> dict[str, Any] | None:
        owner_id = owner_id or current_owner_id()
        placeholders = ", ".join("?" for _ in allowed_statuses)
        with self._lock:
            connection = self._connect()
            try:
                now = self._now()
                updated = connection.execute(
                    f"UPDATE async_jobs SET status = ?, updated_at = ?, completed_at = ? "
                    f"WHERE job_id = ? AND owner_id = ? AND status IN ({placeholders})",
                    (status, now, now, str(job_id), owner_id, *allowed_statuses),
                ).rowcount
                row = connection.execute(
                    "SELECT * FROM async_jobs WHERE job_id = ? AND owner_id = ?",
                    (str(job_id), owner_id),
                ).fetchone()
                connection.commit()
                return self._async_job_row(row) if updated and row else None
            finally:
                connection.close()

    @staticmethod
    def _json_value(value: Any) -> str | None:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str) if value is not None else None

    @staticmethod
    def _async_job_row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["result"] = json.loads(data["result"]) if data.get("result") else None
        return data

    def _initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            connection = self._connect()
            try:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS schema_migrations (
                        version INTEGER PRIMARY KEY,
                        applied_at TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS state_documents (
                        namespace TEXT PRIMARY KEY,
                        payload TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                    """
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_state_documents_updated_at "
                    "ON state_documents(updated_at)"
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO schema_migrations(version, applied_at)
                    VALUES (?, ?)
                    """,
                    (1, self._now()),
                )
                self._apply_collection_migration(connection)
                self._apply_owner_migration(connection)
                self._apply_user_migration(connection)
                self._apply_observability_migration(connection)
                self._apply_agent_quality_migration(connection)
                self._apply_async_job_migration(connection)
                connection.commit()
            finally:
                connection.close()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self.path,
            timeout=10,
            isolation_level=None,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = FULL")
        connection.execute("PRAGMA busy_timeout = 10000")
        return connection

    def _active_connection(self) -> sqlite3.Connection | None:
        return getattr(self._local, "connection", None)

    def _write_json(
        self,
        connection: sqlite3.Connection,
        namespace: str,
        value: Any,
        owner_id: str,
    ) -> None:
        collection = self._collection_tables.get(namespace)
        if collection is not None:
            self._write_collection(connection, namespace, collection, value, owner_id)
            return
        payload = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        connection.execute(
            """
            INSERT INTO state_documents(namespace, owner_id, payload, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(namespace, owner_id) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (namespace, owner_id, payload, self._now()),
        )

    def _apply_collection_migration(self, connection: sqlite3.Connection) -> None:
        applied = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            (2,),
        ).fetchone()
        if applied is not None:
            return

        for table_name, _ in self._collection_tables.values():
            connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    record_id TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table_name}_updated_at "
                f"ON {table_name}(updated_at)"
            )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS collection_state (
                namespace TEXT PRIMARY KEY,
                updated_at TEXT NOT NULL
            )
            """
        )

        for namespace, collection in self._collection_tables.items():
            row = connection.execute(
                "SELECT payload FROM state_documents WHERE namespace = ?",
                (namespace,),
            ).fetchone()
            if row is None:
                continue
            try:
                legacy_value = json.loads(str(row["payload"]))
            except (TypeError, ValueError):
                continue
            self._write_collection(connection, namespace, collection, legacy_value, LEGACY_OWNER_ID)
            connection.execute(
                "DELETE FROM state_documents WHERE namespace = ?",
                (namespace,),
            )

        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (2, self._now()),
        )

    def _apply_owner_migration(self, connection: sqlite3.Connection) -> None:
        applied = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            (3,),
        ).fetchone()
        if applied is not None:
            return

        columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(state_documents)").fetchall()
        }
        if "owner_id" not in columns:
            connection.execute(
                """
                CREATE TABLE state_documents_v3 (
                    namespace TEXT NOT NULL,
                    owner_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(namespace, owner_id)
                )
                """
            )
            connection.execute(
                """
                INSERT INTO state_documents_v3(namespace, owner_id, payload, updated_at)
                SELECT namespace, ?, payload, updated_at FROM state_documents
                """,
                (LEGACY_OWNER_ID,),
            )
            connection.execute("DROP TABLE state_documents")
            connection.execute("ALTER TABLE state_documents_v3 RENAME TO state_documents")

        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_state_documents_updated_at "
            "ON state_documents(updated_at)"
        )
        for table_name, _ in self._collection_tables.values():
            columns = {
                str(row["name"])
                for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
            }
            if "owner_id" not in columns:
                connection.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN owner_id TEXT NOT NULL "
                    f"DEFAULT '{LEGACY_OWNER_ID}'"
                )
            connection.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{table_name}_owner_updated_at "
                f"ON {table_name}(owner_id, updated_at)"
            )
        connection.execute(
            """
            UPDATE collection_state
            SET namespace = ? || ':' || namespace
            WHERE instr(namespace, ':') = 0
            """,
            (LEGACY_OWNER_ID,),
        )
        connection.execute(
            """
            UPDATE state_documents
            SET owner_id = ?
            WHERE namespace = 'agent_knowledge' AND owner_id = ?
            """,
            ("system", LEGACY_OWNER_ID),
        )
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (3, self._now()),
        )

    def _apply_user_migration(self, connection: sqlite3.Connection) -> None:
        applied = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            (4,),
        ).fetchone()
        if applied is not None:
            return
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id TEXT PRIMARY KEY,
                username TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'admin')),
                display_name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)"
        )
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (4, self._now()),
        )

    def _apply_observability_migration(self, connection: sqlite3.Connection) -> None:
        applied = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            (5,),
        ).fetchone()
        if applied is not None:
            return
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_execution_traces (
                trace_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                request_id TEXT,
                message_id TEXT NOT NULL,
                intent TEXT NOT NULL,
                action_type TEXT NOT NULL,
                model_provider TEXT NOT NULL,
                model_strategy TEXT NOT NULL,
                outcome TEXT NOT NULL,
                latency_ms REAL NOT NULL,
                function_call_count INTEGER NOT NULL,
                knowledge_hit_count INTEGER NOT NULL,
                warning_count INTEGER NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_traces_owner_occurred "
            "ON agent_execution_traces(owner_id, occurred_at DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_traces_request "
            "ON agent_execution_traces(request_id)"
        )
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (5, self._now()),
        )

    def _apply_agent_quality_migration(self, connection: sqlite3.Connection) -> None:
        applied = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            (6,),
        ).fetchone()
        if applied is not None:
            return
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_quality_feedback (
                feedback_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                verdict TEXT NOT NULL,
                expected_intent TEXT,
                expected_category TEXT,
                note TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_quality_feedback_owner_created "
            "ON agent_quality_feedback(owner_id, created_at DESC)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_quality_evaluation_runs (
                run_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                pass_rate REAL NOT NULL,
                payload TEXT NOT NULL
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_quality_evaluations_owner_created "
            "ON agent_quality_evaluation_runs(owner_id, created_at DESC)"
        )
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (6, self._now()),
        )

    def _apply_async_job_migration(self, connection: sqlite3.Connection) -> None:
        applied = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            (7,),
        ).fetchone()
        if applied is not None:
            return
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS async_jobs (
                job_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                job_type TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                attempt INTEGER NOT NULL DEFAULT 0,
                max_attempts INTEGER NOT NULL DEFAULT 1,
                result TEXT,
                error_code TEXT,
                error_message TEXT
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_async_jobs_owner_created "
            "ON async_jobs(owner_id, created_at DESC)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_async_jobs_owner_status "
            "ON async_jobs(owner_id, status, created_at)"
        )
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (7, self._now()),
        )

    def _write_collection(
        self,
        connection: sqlite3.Connection,
        namespace: str,
        collection: tuple[str, str],
        value: Any,
        owner_id: str,
    ) -> None:
        if not isinstance(value, list):
            raise ValueError(f"{namespace} must be persisted as a list")
        table_name, id_field = collection
        now = self._now()
        connection.execute(f"DELETE FROM {table_name} WHERE owner_id = ?", (owner_id,))
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                raise ValueError(f"{namespace} contains a non-object record")
            record_id = str(item.get(id_field) or index)
            payload = json.dumps(
                item,
                ensure_ascii=False,
                separators=(",", ":"),
                default=str,
            )
            connection.execute(
                f"INSERT INTO {table_name}(record_id, owner_id, payload, updated_at) VALUES (?, ?, ?, ?)",
                (record_id, owner_id, payload, now),
            )
        connection.execute(
            """
            INSERT INTO collection_state(namespace, updated_at)
            VALUES (?, ?)
            ON CONFLICT(namespace) DO UPDATE SET updated_at = excluded.updated_at
            """,
            (self._scope(namespace, owner_id), now),
        )

    def _scope(self, namespace: str, owner_id: str) -> str:
        return f"{owner_id}:{namespace}"

    def _read_legacy_json(self, path: Path) -> Any | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None

    def _now(self) -> str:
        return datetime.now(timezone.utc).isoformat()


sqlite_state_store = SQLiteStateStore()
