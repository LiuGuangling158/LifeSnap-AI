from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from app.core.config import settings


class SQLiteStateStore:
    """Transactional JSON-document persistence backed by SQLite.

    Existing domain stores keep their public contracts while this adapter moves
    their durable state from scattered JSON files into one migration-managed
    database. Legacy files are read only once, on first access to a namespace.
    """

    _migration_version = 2
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

    def load_json(self, namespace: str, legacy_path: Path) -> Any | None:
        with self._lock:
            connection = self._connect()
            try:
                collection = self._collection_tables.get(namespace)
                if collection is not None:
                    table_name, _ = collection
                    initialized = connection.execute(
                        "SELECT 1 FROM collection_state WHERE namespace = ?",
                        (namespace,),
                    ).fetchone()
                    if initialized is not None:
                        rows = connection.execute(
                            f"SELECT payload FROM {table_name} ORDER BY updated_at, record_id"
                        ).fetchall()
                        return [json.loads(str(row["payload"])) for row in rows]

                row = connection.execute(
                    "SELECT payload FROM state_documents WHERE namespace = ?",
                    (namespace,),
                ).fetchone()
                if row is not None:
                    return json.loads(str(row["payload"]))

                legacy_value = self._read_legacy_json(legacy_path)
                if legacy_value is not None:
                    self._write_json(connection, namespace, legacy_value)
                    connection.commit()
                return legacy_value
            finally:
                connection.close()

    def save_json(self, namespace: str, value: Any) -> None:
        connection = self._active_connection()
        if connection is not None:
            self._write_json(connection, namespace, value)
            return

        with self._lock:
            connection = self._connect()
            try:
                self._write_json(connection, namespace, value)
                connection.commit()
            finally:
                connection.close()

    def namespace_exists(self, namespace: str) -> bool:
        with self._lock:
            connection = self._connect()
            try:
                if namespace in self._collection_tables:
                    return connection.execute(
                        "SELECT 1 FROM collection_state WHERE namespace = ?",
                        (namespace,),
                    ).fetchone() is not None
                return connection.execute(
                    "SELECT 1 FROM state_documents WHERE namespace = ?",
                    (namespace,),
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

    def _write_json(self, connection: sqlite3.Connection, namespace: str, value: Any) -> None:
        collection = self._collection_tables.get(namespace)
        if collection is not None:
            self._write_collection(connection, namespace, collection, value)
            return
        payload = json.dumps(
            value,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        connection.execute(
            """
            INSERT INTO state_documents(namespace, payload, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(namespace) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (namespace, payload, self._now()),
        )

    def _apply_collection_migration(self, connection: sqlite3.Connection) -> None:
        applied = connection.execute(
            "SELECT 1 FROM schema_migrations WHERE version = ?",
            (self._migration_version,),
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
            self._write_collection(connection, namespace, collection, legacy_value)
            connection.execute(
                "DELETE FROM state_documents WHERE namespace = ?",
                (namespace,),
            )

        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (self._migration_version, self._now()),
        )

    def _write_collection(
        self,
        connection: sqlite3.Connection,
        namespace: str,
        collection: tuple[str, str],
        value: Any,
    ) -> None:
        if not isinstance(value, list):
            raise ValueError(f"{namespace} must be persisted as a list")
        table_name, id_field = collection
        now = self._now()
        connection.execute(f"DELETE FROM {table_name}")
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
                f"INSERT INTO {table_name}(record_id, payload, updated_at) VALUES (?, ?, ?)",
                (record_id, payload, now),
            )
        connection.execute(
            """
            INSERT INTO collection_state(namespace, updated_at)
            VALUES (?, ?)
            ON CONFLICT(namespace) DO UPDATE SET updated_at = excluded.updated_at
            """,
            (namespace, now),
        )

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
