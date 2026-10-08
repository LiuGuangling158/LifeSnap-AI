from __future__ import annotations

import json
import sqlite3
import threading
import uuid
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

    _migration_version = 11
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

    def find_agent_trace_by_message_id(
        self,
        message_id: str,
        *,
        owner_id: str | None = None,
    ) -> dict[str, Any] | None:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                row = connection.execute(
                    """
                    SELECT trace_id, occurred_at, request_id, message_id, intent,
                           action_type, model_provider, model_strategy, outcome,
                           latency_ms, function_call_count, knowledge_hit_count,
                           warning_count, payload
                    FROM agent_execution_traces
                    WHERE owner_id = ? AND message_id = ?
                    ORDER BY occurred_at DESC
                    LIMIT 1
                    """,
                    (owner_id, message_id),
                ).fetchone()
                if row is None:
                    return None
                return {**dict(row), "payload": json.loads(str(row["payload"]))}
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

    def upsert_agent_quality_feedback(
        self,
        feedback: dict[str, Any],
        *,
        owner_id: str | None = None,
    ) -> dict[str, Any]:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                existing = connection.execute(
                    """
                    SELECT feedback_id FROM agent_quality_feedback
                    WHERE owner_id = ? AND message_id = ?
                    ORDER BY created_at DESC LIMIT 1
                    """,
                    (owner_id, str(feedback["message_id"])),
                ).fetchone()
                if existing is None:
                    connection.execute(
                        """
                        INSERT INTO agent_quality_feedback(
                            feedback_id, owner_id, message_id, verdict, expected_intent,
                            expected_category, note, created_at, trace_id, trace_snapshot,
                            review_status, review_note, reviewed_at, promoted_case_id
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        self._feedback_values(feedback, owner_id),
                    )
                    feedback_id = str(feedback["feedback_id"])
                else:
                    feedback_id = str(existing["feedback_id"])
                    connection.execute(
                        """
                        UPDATE agent_quality_feedback_cases
                        SET enabled = 0, updated_at = ?
                        WHERE feedback_id = ? AND owner_id = ?
                        """,
                        (self._now(), feedback_id, owner_id),
                    )
                    connection.execute(
                        """
                        UPDATE agent_quality_feedback
                        SET verdict = ?, expected_intent = ?, expected_category = ?, note = ?,
                            created_at = ?, trace_id = ?, trace_snapshot = ?,
                            review_status = 'pending', review_note = NULL, reviewed_at = NULL,
                            promoted_case_id = NULL
                        WHERE feedback_id = ? AND owner_id = ?
                        """,
                        (
                            str(feedback["verdict"]),
                            feedback.get("expected_intent"),
                            feedback.get("expected_category"),
                            feedback.get("note"),
                            str(feedback["created_at"]),
                            feedback.get("trace_id"),
                            json.dumps(feedback.get("trace_snapshot", {}), ensure_ascii=False),
                            feedback_id,
                            owner_id,
                        ),
                    )
                connection.commit()
                return self._agent_quality_feedback_row(connection, feedback_id, owner_id)
            finally:
                connection.close()

    def append_agent_quality_feedback(self, feedback: dict[str, Any], *, owner_id: str | None = None) -> None:
        """Backward-compatible wrapper for older callers."""
        self.upsert_agent_quality_feedback(feedback, owner_id=owner_id)

    def list_agent_quality_feedback(self, *, owner_id: str | None = None, limit: int = 500) -> list[dict[str, Any]]:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                rows = connection.execute(
                    """
                    SELECT feedback_id, message_id, verdict, expected_intent,
                           expected_category, note, created_at, trace_id, trace_snapshot,
                           review_status, review_note, reviewed_at, promoted_case_id
                    FROM agent_quality_feedback
                    WHERE owner_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (owner_id, max(1, min(limit, 1000))),
                ).fetchall()
                return [self._serialize_feedback_row(row) for row in rows]
            finally:
                connection.close()

    def get_agent_quality_feedback(
        self,
        feedback_id: str,
        *,
        owner_id: str | None = None,
    ) -> dict[str, Any] | None:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                row = connection.execute(
                    """
                    SELECT feedback_id, message_id, verdict, expected_intent,
                           expected_category, note, created_at, trace_id, trace_snapshot,
                           review_status, review_note, reviewed_at, promoted_case_id
                    FROM agent_quality_feedback
                    WHERE feedback_id = ? AND owner_id = ?
                    """,
                    (feedback_id, owner_id),
                ).fetchone()
                return self._serialize_feedback_row(row) if row else None
            finally:
                connection.close()

    def review_agent_quality_feedback(
        self,
        feedback_id: str,
        *,
        review_status: str,
        review_note: str | None,
        promoted_case_id: str | None = None,
        owner_id: str | None = None,
    ) -> dict[str, Any] | None:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                cursor = connection.execute(
                    """
                    UPDATE agent_quality_feedback
                    SET review_status = ?, review_note = ?, reviewed_at = ?, promoted_case_id = ?
                    WHERE feedback_id = ? AND owner_id = ?
                    """,
                    (
                        review_status,
                        review_note,
                        self._now(),
                        promoted_case_id,
                        feedback_id,
                        owner_id,
                    ),
                )
                connection.commit()
                if cursor.rowcount == 0:
                    return None
                return self._agent_quality_feedback_row(connection, feedback_id, owner_id)
            finally:
                connection.close()

    def upsert_agent_quality_feedback_case(
        self,
        feedback_id: str,
        payload: dict[str, Any],
        *,
        owner_id: str | None = None,
    ) -> None:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                connection.execute(
                    """
                    INSERT INTO agent_quality_feedback_cases(
                        feedback_id, owner_id, case_id, payload, created_at, updated_at, enabled
                    ) VALUES (?, ?, ?, ?, ?, ?, 1)
                    ON CONFLICT(feedback_id) DO UPDATE SET
                        case_id = excluded.case_id, payload = excluded.payload,
                        updated_at = excluded.updated_at, enabled = 1
                    """,
                    (
                        feedback_id,
                        owner_id,
                        str(payload["case_id"]),
                        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                        self._now(),
                        self._now(),
                    ),
                )
                connection.commit()
            finally:
                connection.close()

    def list_agent_quality_feedback_cases(
        self,
        *,
        owner_id: str | None = None,
    ) -> list[dict[str, Any]]:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                rows = connection.execute(
                    """
                    SELECT payload FROM agent_quality_feedback_cases
                    WHERE owner_id = ? AND enabled = 1
                    ORDER BY created_at ASC
                    """,
                    (owner_id,),
                ).fetchall()
                return [json.loads(str(row["payload"])) for row in rows]
            finally:
                connection.close()

    @staticmethod
    def _feedback_values(feedback: dict[str, Any], owner_id: str) -> tuple[Any, ...]:
        return (
            str(feedback["feedback_id"]),
            owner_id,
            str(feedback["message_id"]),
            str(feedback["verdict"]),
            feedback.get("expected_intent"),
            feedback.get("expected_category"),
            feedback.get("note"),
            str(feedback["created_at"]),
            feedback.get("trace_id"),
            json.dumps(feedback.get("trace_snapshot", {}), ensure_ascii=False),
            str(feedback.get("review_status") or "pending"),
            feedback.get("review_note"),
            feedback.get("reviewed_at"),
            feedback.get("promoted_case_id"),
        )

    def _agent_quality_feedback_row(
        self,
        connection: sqlite3.Connection,
        feedback_id: str,
        owner_id: str,
    ) -> dict[str, Any]:
        row = connection.execute(
            """
            SELECT feedback_id, message_id, verdict, expected_intent,
                   expected_category, note, created_at, trace_id, trace_snapshot,
                   review_status, review_note, reviewed_at, promoted_case_id
            FROM agent_quality_feedback
            WHERE feedback_id = ? AND owner_id = ?
            """,
            (feedback_id, owner_id),
        ).fetchone()
        if row is None:
            raise RuntimeError("Agent quality feedback was not persisted")
        return self._serialize_feedback_row(row)

    @staticmethod
    def _serialize_feedback_row(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        raw_snapshot = item.pop("trace_snapshot", None)
        try:
            item["trace_snapshot"] = json.loads(str(raw_snapshot or "{}"))
        except json.JSONDecodeError:
            item["trace_snapshot"] = {}
        return item

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

    def create_or_get_async_job(
        self,
        job: dict[str, Any],
        *,
        owner_id: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Persist a job once for an owner, type, and client idempotency key."""
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                try:
                    connection.execute(
                        """
                        INSERT INTO async_jobs(
                            job_id, owner_id, job_type, status, created_at, updated_at,
                            available_at, started_at, completed_at, lease_expires_at,
                            worker_id, lease_token, idempotency_key, attempt, max_attempts,
                            result, error_code, error_message
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            str(job["job_id"]),
                            owner_id,
                            str(job["job_type"]),
                            str(job["status"]),
                            str(job["created_at"]),
                            str(job["updated_at"]),
                            str(job.get("available_at") or job["created_at"]),
                            job.get("started_at"),
                            job.get("completed_at"),
                            job.get("lease_expires_at"),
                            job.get("worker_id"),
                            job.get("lease_token"),
                            job.get("idempotency_key"),
                            int(job.get("attempt", 0)),
                            int(job.get("max_attempts", 1)),
                            self._json_value(job.get("result")),
                            job.get("error_code"),
                            job.get("error_message"),
                        ),
                    )
                    created = True
                except sqlite3.IntegrityError:
                    idempotency_key = job.get("idempotency_key")
                    if not idempotency_key:
                        raise
                    created = False
                if not created:
                    row = connection.execute(
                        """
                        SELECT * FROM async_jobs
                        WHERE owner_id = ? AND job_type = ? AND idempotency_key = ?
                        """,
                        (owner_id, str(job["job_type"]), str(job["idempotency_key"])),
                    ).fetchone()
                    if row is None:
                        raise RuntimeError("Async job idempotency conflict could not be resolved")
                    connection.commit()
                    return self._async_job_row(row), False
                row = connection.execute(
                    "SELECT * FROM async_jobs WHERE job_id = ? AND owner_id = ?",
                    (str(job["job_id"]), owner_id),
                ).fetchone()
                if row is not None:
                    self._append_async_job_event(
                        connection,
                        owner_id=owner_id,
                        job_id=str(job["job_id"]),
                        event_type="created",
                        status=str(job["status"]),
                        attempt=int(job.get("attempt", 0)),
                    )
                connection.commit()
                if row is None:
                    raise RuntimeError("Created asynchronous job could not be read")
                return self._async_job_row(row), True
            finally:
                connection.close()

    def create_async_job(self, job: dict[str, Any], *, owner_id: str | None = None) -> None:
        """Compatibility wrapper for callers that do not need idempotency feedback."""
        self.create_or_get_async_job(job, owner_id=owner_id)

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

    def list_async_job_events(
        self,
        job_id: Any,
        *,
        owner_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                rows = connection.execute(
                    """
                    SELECT event_id, job_id, occurred_at, event_type, status, attempt, error_code
                    FROM async_job_events
                    WHERE owner_id = ? AND job_id = ?
                    ORDER BY occurred_at DESC, event_id DESC
                    LIMIT ?
                    """,
                    (owner_id, str(job_id), max(1, min(limit, 500))),
                ).fetchall()
                return [dict(row) for row in rows]
            finally:
                connection.close()

    def list_dispatchable_async_jobs(
        self,
        *,
        owner_id: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        owner_id = owner_id or current_owner_id()
        now = self._now()
        with self._lock:
            connection = self._connect()
            try:
                rows = connection.execute(
                    """
                    SELECT * FROM async_jobs
                    WHERE owner_id = ?
                      AND status IN ('queued', 'retry_scheduled')
                      AND COALESCE(available_at, created_at) <= ?
                    ORDER BY COALESCE(available_at, created_at), created_at
                    LIMIT ?
                    """,
                    (owner_id, now, max(1, min(limit, 100))),
                ).fetchall()
                return [self._async_job_row(row) for row in rows]
            finally:
                connection.close()

    def claim_async_job(
        self,
        job_id: Any,
        *,
        worker_id: str,
        lease_token: str,
        lease_expires_at: str,
        owner_id: str | None = None,
    ) -> dict[str, Any] | None:
        owner_id = owner_id or current_owner_id()
        now = self._now()
        with self._lock:
            connection = self._connect()
            try:
                updated = connection.execute(
                    """
                    UPDATE async_jobs
                    SET status = 'running', started_at = COALESCE(started_at, ?), updated_at = ?,
                        completed_at = NULL, attempt = attempt + 1, worker_id = ?,
                        lease_token = ?, lease_expires_at = ?
                    WHERE job_id = ? AND owner_id = ?
                      AND status IN ('queued', 'retry_scheduled')
                      AND COALESCE(available_at, created_at) <= ?
                    """,
                    (
                        now,
                        now,
                        worker_id,
                        lease_token,
                        lease_expires_at,
                        str(job_id),
                        owner_id,
                        now,
                    ),
                ).rowcount
                if not updated:
                    connection.commit()
                    return None
                row = connection.execute(
                    "SELECT * FROM async_jobs WHERE job_id = ? AND owner_id = ?",
                    (str(job_id), owner_id),
                ).fetchone()
                if row is not None:
                    self._append_async_job_event(
                        connection,
                        owner_id=owner_id,
                        job_id=str(job_id),
                        event_type="claimed",
                        status="running",
                        attempt=int(row["attempt"]),
                    )
                connection.commit()
                return self._async_job_row(row) if row else None
            finally:
                connection.close()

    def renew_async_job_lease(
        self,
        job_id: Any,
        *,
        lease_token: str,
        lease_expires_at: str,
        owner_id: str | None = None,
    ) -> bool:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                updated = connection.execute(
                    """
                    UPDATE async_jobs SET lease_expires_at = ?, updated_at = ?
                    WHERE job_id = ? AND owner_id = ? AND status = 'running' AND lease_token = ?
                    """,
                    (lease_expires_at, self._now(), str(job_id), owner_id, lease_token),
                ).rowcount
                connection.commit()
                return bool(updated)
            finally:
                connection.close()

    def succeed_async_job(
        self,
        job_id: Any,
        result: dict[str, Any],
        *,
        lease_token: str,
        owner_id: str | None = None,
    ) -> None:
        self._finish_async_job(
            job_id,
            "succeeded",
            result=result,
            lease_token=lease_token,
            owner_id=owner_id,
        )

    def fail_async_job(
        self,
        job_id: Any,
        *,
        error_code: str,
        error_message: str,
        lease_token: str,
        retry_delay_seconds: float,
        owner_id: str | None = None,
    ) -> None:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                now = self._now()
                row = connection.execute(
                    """
                    SELECT attempt, max_attempts FROM async_jobs
                    WHERE job_id = ? AND owner_id = ? AND status = 'running' AND lease_token = ?
                    """,
                    (str(job_id), owner_id, lease_token),
                ).fetchone()
                if row is None:
                    connection.commit()
                    return
                retryable = int(row["attempt"]) < int(row["max_attempts"])
                available_at = datetime.fromtimestamp(
                    datetime.now(timezone.utc).timestamp() + max(0.0, retry_delay_seconds),
                    timezone.utc,
                ).isoformat()
                connection.execute(
                    """
                    UPDATE async_jobs
                    SET status = ?, updated_at = ?, available_at = ?, completed_at = ?,
                        worker_id = NULL, lease_token = NULL, lease_expires_at = NULL,
                        error_code = ?, error_message = ?
                    WHERE job_id = ? AND owner_id = ? AND status = 'running' AND lease_token = ?
                    """,
                    (
                        "retry_scheduled" if retryable else "failed",
                        now,
                        available_at if retryable else now,
                        None if retryable else now,
                        error_code,
                        error_message,
                        str(job_id),
                        owner_id,
                        lease_token,
                    ),
                )
                self._append_async_job_event(
                    connection,
                    owner_id=owner_id,
                    job_id=str(job_id),
                    event_type="retry_scheduled" if retryable else "failed",
                    status="retry_scheduled" if retryable else "failed",
                    attempt=int(row["attempt"]),
                    error_code=error_code,
                )
                connection.commit()
            finally:
                connection.close()

    def cancel_async_job(self, job_id: Any, *, owner_id: str | None = None) -> dict[str, Any] | None:
        return self._change_async_job_status(
            job_id,
            "cancelled",
            ("queued", "retry_scheduled"),
            event_type="cancelled",
            owner_id=owner_id,
        )

    def retry_async_job(self, job_id: Any, *, owner_id: str | None = None) -> dict[str, Any] | None:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                now = self._now()
                updated = connection.execute(
                    """
                    UPDATE async_jobs
                    SET status = 'queued', updated_at = ?, available_at = ?, started_at = NULL,
                        completed_at = NULL, worker_id = NULL, lease_token = NULL,
                        lease_expires_at = NULL, error_code = NULL, error_message = NULL, result = NULL
                    WHERE job_id = ? AND owner_id = ? AND status IN ('failed', 'cancelled')
                      AND attempt < max_attempts
                    """,
                    (now, now, str(job_id), owner_id),
                ).rowcount
                row = connection.execute(
                    "SELECT * FROM async_jobs WHERE job_id = ? AND owner_id = ?",
                    (str(job_id), owner_id),
                ).fetchone()
                if updated and row is not None:
                    self._append_async_job_event(
                        connection,
                        owner_id=owner_id,
                        job_id=str(job_id),
                        event_type="manual_retry",
                        status="queued",
                        attempt=int(row["attempt"]),
                    )
                connection.commit()
                return self._async_job_row(row) if updated and row else None
            finally:
                connection.close()

    def redrive_async_job(self, job_id: Any, *, owner_id: str | None = None) -> dict[str, Any] | None:
        """Start a new execution cycle for a final failed job after operator review."""
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                now = self._now()
                updated = connection.execute(
                    """
                    UPDATE async_jobs
                    SET status = 'queued', updated_at = ?, available_at = ?, started_at = NULL,
                        completed_at = NULL, worker_id = NULL, lease_token = NULL,
                        lease_expires_at = NULL, attempt = 0, error_code = NULL,
                        error_message = NULL, result = NULL
                    WHERE job_id = ? AND owner_id = ? AND status = 'failed'
                    """,
                    (now, now, str(job_id), owner_id),
                ).rowcount
                row = connection.execute(
                    "SELECT * FROM async_jobs WHERE job_id = ? AND owner_id = ?",
                    (str(job_id), owner_id),
                ).fetchone()
                if updated and row is not None:
                    self._append_async_job_event(
                        connection,
                        owner_id=owner_id,
                        job_id=str(job_id),
                        event_type="redriven",
                        status="queued",
                        attempt=0,
                    )
                connection.commit()
                return self._async_job_row(row) if updated and row else None
            finally:
                connection.close()

    def recover_async_jobs(self, *, owner_id: str | None = None) -> list[dict[str, Any]]:
        """Recover expired leases without racing still-running workers after restart."""
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                now = self._now()
                expired_rows = connection.execute(
                    """
                    SELECT job_id, attempt, max_attempts FROM async_jobs
                    WHERE owner_id = ? AND status = 'running'
                      AND (lease_expires_at IS NULL OR lease_expires_at <= ?)
                    """,
                    (owner_id, now),
                ).fetchall()
                connection.execute(
                    """
                    UPDATE async_jobs
                    SET status = CASE WHEN attempt < max_attempts THEN 'retry_scheduled' ELSE 'failed' END,
                        available_at = ?, completed_at = CASE WHEN attempt < max_attempts THEN NULL ELSE ? END,
                        updated_at = ?, worker_id = NULL, lease_token = NULL, lease_expires_at = NULL,
                        error_code = 'worker_lease_expired',
                        error_message = 'Worker lease expired before the job completed.'
                    WHERE owner_id = ? AND status = 'running'
                      AND (lease_expires_at IS NULL OR lease_expires_at <= ?)
                    """,
                    (now, now, now, owner_id, now),
                )
                for expired in expired_rows:
                    retryable = int(expired["attempt"]) < int(expired["max_attempts"])
                    self._append_async_job_event(
                        connection,
                        owner_id=owner_id,
                        job_id=str(expired["job_id"]),
                        event_type="lease_recovered",
                        status="retry_scheduled" if retryable else "failed",
                        attempt=int(expired["attempt"]),
                        error_code="worker_lease_expired",
                    )
                connection.execute(
                    """
                    UPDATE async_jobs SET available_at = created_at
                    WHERE owner_id = ? AND status = 'queued' AND available_at IS NULL
                    """,
                    (owner_id,),
                )
                rows = connection.execute(
                    """
                    SELECT * FROM async_jobs
                    WHERE owner_id = ? AND status IN ('queued', 'retry_scheduled')
                      AND COALESCE(available_at, created_at) <= ?
                    ORDER BY COALESCE(available_at, created_at), created_at
                    """,
                    (owner_id, now),
                ).fetchall()
                connection.commit()
                return [self._async_job_row(row) for row in rows]
            finally:
                connection.close()

    def sync_operational_alerts(
        self,
        alerts: list[dict[str, Any]],
        *,
        owner_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Upsert currently firing alerts and resolve no-longer-firing records."""
        owner_id = owner_id or current_owner_id()
        now = self._now()
        fingerprints = {str(alert["fingerprint"]) for alert in alerts}
        with self._lock:
            connection = self._connect()
            try:
                for alert in alerts:
                    fingerprint = str(alert["fingerprint"])
                    existing = connection.execute(
                        "SELECT alert_id FROM operational_alerts WHERE owner_id = ? AND fingerprint = ?",
                        (owner_id, fingerprint),
                    ).fetchone()
                    if existing is None:
                        connection.execute(
                            """
                            INSERT INTO operational_alerts(
                                alert_id, owner_id, fingerprint, rule_id, severity, status,
                                title, summary, first_seen_at, last_seen_at, resolved_at,
                                occurrence_count, metadata
                            ) VALUES (?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, NULL, 1, ?)
                            """,
                            (
                                uuid.uuid4().hex,
                                owner_id,
                                fingerprint,
                                str(alert["rule_id"]),
                                str(alert["severity"]),
                                str(alert["title"]),
                                str(alert["summary"]),
                                now,
                                now,
                                self._json_value(alert.get("metadata", {})),
                            ),
                        )
                    else:
                        connection.execute(
                            """
                            UPDATE operational_alerts
                            SET rule_id = ?, severity = ?, status = 'active', title = ?,
                                summary = ?, last_seen_at = ?, resolved_at = NULL,
                                occurrence_count = occurrence_count + 1, metadata = ?
                            WHERE owner_id = ? AND fingerprint = ?
                            """,
                            (
                                str(alert["rule_id"]),
                                str(alert["severity"]),
                                str(alert["title"]),
                                str(alert["summary"]),
                                now,
                                self._json_value(alert.get("metadata", {})),
                                owner_id,
                                fingerprint,
                            ),
                        )

                if fingerprints:
                    placeholders = ", ".join("?" for _ in fingerprints)
                    connection.execute(
                        "UPDATE operational_alerts SET status = 'resolved', resolved_at = ?, "
                        "last_seen_at = ? WHERE owner_id = ? AND status = 'active' "
                        f"AND fingerprint NOT IN ({placeholders})",
                        (now, now, owner_id, *sorted(fingerprints)),
                    )
                else:
                    connection.execute(
                        "UPDATE operational_alerts SET status = 'resolved', resolved_at = ?, "
                        "last_seen_at = ? WHERE owner_id = ? AND status = 'active'",
                        (now, now, owner_id),
                    )
                connection.commit()
            finally:
                connection.close()
        return self.list_operational_alerts(owner_id=owner_id, include_resolved=True)

    def list_operational_alerts(
        self,
        *,
        owner_id: str | None = None,
        include_resolved: bool = True,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                filter_sql = "" if include_resolved else "AND status = 'active'"
                rows = connection.execute(
                    "SELECT * FROM operational_alerts WHERE owner_id = ? "
                    + filter_sql
                    + " ORDER BY CASE status WHEN 'active' THEN 0 ELSE 1 END, "
                    "last_seen_at DESC LIMIT ?",
                    (owner_id, max(1, min(limit, 200))),
                ).fetchall()
                return [self._operational_alert_row(row) for row in rows]
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
        lease_token: str,
        owner_id: str | None = None,
    ) -> None:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                now = self._now()
                updated = connection.execute(
                    """
                    UPDATE async_jobs
                    SET status = ?, updated_at = ?, completed_at = ?, result = ?,
                        worker_id = NULL, lease_token = NULL, lease_expires_at = NULL,
                        error_code = ?, error_message = ?
                    WHERE job_id = ? AND owner_id = ? AND status = 'running' AND lease_token = ?
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
                        lease_token,
                    ),
                ).rowcount
                if updated:
                    row = connection.execute(
                        "SELECT attempt FROM async_jobs WHERE job_id = ? AND owner_id = ?",
                        (str(job_id), owner_id),
                    ).fetchone()
                    if row is not None:
                        self._append_async_job_event(
                            connection,
                            owner_id=owner_id,
                            job_id=str(job_id),
                            event_type=status,
                            status=status,
                            attempt=int(row["attempt"]),
                            error_code=error_code,
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
        event_type: str | None = None,
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
                if updated and row is not None:
                    self._append_async_job_event(
                        connection,
                        owner_id=owner_id,
                        job_id=str(job_id),
                        event_type=event_type or status,
                        status=status,
                        attempt=int(row["attempt"]),
                    )
                connection.commit()
                return self._async_job_row(row) if updated and row else None
            finally:
                connection.close()

    def _append_async_job_event(
        self,
        connection: sqlite3.Connection,
        *,
        owner_id: str,
        job_id: str,
        event_type: str,
        status: str,
        attempt: int,
        error_code: str | None = None,
    ) -> None:
        connection.execute(
            """
            INSERT INTO async_job_events(
                event_id, owner_id, job_id, occurred_at, event_type, status, attempt, error_code
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid.uuid4().hex,
                owner_id,
                job_id,
                self._now(),
                event_type,
                status,
                attempt,
                error_code,
            ),
        )

    @staticmethod
    def _json_value(value: Any) -> str | None:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str) if value is not None else None

    @staticmethod
    def _async_job_row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["result"] = json.loads(data["result"]) if data.get("result") else None
        return data

    def async_job_status_counts(self, *, owner_id: str | None = None) -> dict[str, Any]:
        owner_id = owner_id or current_owner_id()
        with self._lock:
            connection = self._connect()
            try:
                rows = connection.execute(
                    "SELECT status, COUNT(*) AS count FROM async_jobs WHERE owner_id = ? GROUP BY status",
                    (owner_id,),
                ).fetchall()
                oldest = connection.execute(
                    """
                    SELECT MIN(COALESCE(available_at, created_at)) AS available_at
                    FROM async_jobs
                    WHERE owner_id = ? AND status IN ('queued', 'retry_scheduled')
                    """,
                    (owner_id,),
                ).fetchone()
                return {
                    "counts": {str(row["status"]): int(row["count"]) for row in rows},
                    "oldest_available_at": oldest["available_at"] if oldest else None,
                }
            finally:
                connection.close()

    @staticmethod
    def _operational_alert_row(row: sqlite3.Row) -> dict[str, Any]:
        data = dict(row)
        data["metadata"] = json.loads(data["metadata"]) if data.get("metadata") else {}
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
                self._apply_operational_alert_migration(connection)
                self._apply_async_job_reliability_migration(connection)
                self._apply_async_job_event_migration(connection)
                self._apply_feedback_loop_migration(connection)
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

    def _apply_operational_alert_migration(self, connection: sqlite3.Connection) -> None:
        applied = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            (8,),
        ).fetchone()
        if applied is not None:
            return
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS operational_alerts (
                alert_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                rule_id TEXT NOT NULL,
                severity TEXT NOT NULL,
                status TEXT NOT NULL,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                resolved_at TEXT,
                occurrence_count INTEGER NOT NULL,
                metadata TEXT NOT NULL,
                UNIQUE(owner_id, fingerprint)
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_operational_alerts_owner_status_seen "
            "ON operational_alerts(owner_id, status, last_seen_at DESC)"
        )
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (8, self._now()),
        )

    def _apply_async_job_reliability_migration(self, connection: sqlite3.Connection) -> None:
        applied = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            (9,),
        ).fetchone()
        if applied is not None:
            return
        columns = {
            str(row["name"])
            for row in connection.execute("PRAGMA table_info(async_jobs)").fetchall()
        }
        additions = {
            "available_at": "TEXT",
            "lease_expires_at": "TEXT",
            "worker_id": "TEXT",
            "lease_token": "TEXT",
            "idempotency_key": "TEXT",
        }
        for name, definition in additions.items():
            if name not in columns:
                connection.execute(f"ALTER TABLE async_jobs ADD COLUMN {name} {definition}")
        connection.execute(
            "UPDATE async_jobs SET available_at = created_at WHERE available_at IS NULL"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_async_jobs_dispatch "
            "ON async_jobs(owner_id, status, available_at, created_at)"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_async_jobs_lease "
            "ON async_jobs(owner_id, status, lease_expires_at)"
        )
        connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_async_jobs_idempotency "
            "ON async_jobs(owner_id, job_type, idempotency_key) "
            "WHERE idempotency_key IS NOT NULL"
        )
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (9, self._now()),
        )

    def _apply_async_job_event_migration(self, connection: sqlite3.Connection) -> None:
        applied = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            (10,),
        ).fetchone()
        if applied is not None:
            return
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS async_job_events (
                event_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                job_id TEXT NOT NULL,
                occurred_at TEXT NOT NULL,
                event_type TEXT NOT NULL,
                status TEXT NOT NULL,
                attempt INTEGER NOT NULL,
                error_code TEXT
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_async_job_events_owner_job_occurred "
            "ON async_job_events(owner_id, job_id, occurred_at DESC)"
        )
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (10, self._now()),
        )

    def _apply_feedback_loop_migration(self, connection: sqlite3.Connection) -> None:
        applied = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            (11,),
        ).fetchone()
        if applied is not None:
            return
        connection.execute("ALTER TABLE agent_quality_feedback ADD COLUMN trace_id TEXT")
        connection.execute(
            "ALTER TABLE agent_quality_feedback ADD COLUMN trace_snapshot TEXT NOT NULL DEFAULT '{}'"
        )
        connection.execute(
            "ALTER TABLE agent_quality_feedback ADD COLUMN review_status TEXT NOT NULL DEFAULT 'pending'"
        )
        connection.execute("ALTER TABLE agent_quality_feedback ADD COLUMN review_note TEXT")
        connection.execute("ALTER TABLE agent_quality_feedback ADD COLUMN reviewed_at TEXT")
        connection.execute("ALTER TABLE agent_quality_feedback ADD COLUMN promoted_case_id TEXT")
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_quality_feedback_owner_status_created "
            "ON agent_quality_feedback(owner_id, review_status, created_at DESC)"
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS agent_quality_feedback_cases (
                feedback_id TEXT PRIMARY KEY,
                owner_id TEXT NOT NULL,
                case_id TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                enabled INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS idx_agent_quality_feedback_cases_owner_created "
            "ON agent_quality_feedback_cases(owner_id, created_at ASC)"
        )
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (11, self._now()),
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
