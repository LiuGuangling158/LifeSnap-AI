from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from app.core.config import settings
from app.schemas.async_job import AsyncJobRead, AsyncJobStatus, AsyncJobType
from app.services.agent_knowledge_base import agent_knowledge_base
from app.services.agent_quality_service import agent_quality_service
from app.services.sqlite_state_store import sqlite_state_store


logger = logging.getLogger(__name__)


class AsyncJobService:
    """Durable, process-local worker queue for bounded administrative jobs."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._executor: ThreadPoolExecutor | None = None

    def start(self) -> None:
        with self._lock:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(
                    max_workers=settings.async_job_worker_count,
                    thread_name_prefix="lifesnap-job",
                )
            queued = sqlite_state_store.recover_async_jobs()
            for job in queued:
                self._dispatch(UUID(str(job["job_id"])))

    def shutdown(self) -> None:
        with self._lock:
            executor = self._executor
            self._executor = None
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=False)

    def enqueue(self, job_type: AsyncJobType) -> AsyncJobRead:
        self.start()
        now = datetime.now(timezone.utc)
        job = AsyncJobRead(
            job_id=uuid4(),
            job_type=job_type,
            status=AsyncJobStatus.queued,
            created_at=now,
            updated_at=now,
            max_attempts=settings.async_job_max_attempts,
        )
        sqlite_state_store.create_async_job(job.model_dump(mode="json"))
        self._dispatch(job.job_id)
        return job

    def get(self, job_id: UUID) -> AsyncJobRead | None:
        raw = sqlite_state_store.get_async_job(job_id)
        return AsyncJobRead.model_validate(raw) if raw else None

    def list_recent(self, limit: int = 20) -> list[AsyncJobRead]:
        return [
            AsyncJobRead.model_validate(item)
            for item in sqlite_state_store.list_async_jobs(limit=limit)
        ]

    def retry(self, job_id: UUID) -> AsyncJobRead | None:
        self.start()
        raw = sqlite_state_store.retry_async_job(job_id)
        if raw is None:
            return None
        job = AsyncJobRead.model_validate(raw)
        self._dispatch(job.job_id)
        return job

    def cancel(self, job_id: UUID) -> AsyncJobRead | None:
        raw = sqlite_state_store.cancel_async_job(job_id)
        return AsyncJobRead.model_validate(raw) if raw else None

    def _dispatch(self, job_id: UUID) -> None:
        with self._lock:
            if self._executor is None:
                return
            self._executor.submit(self._run, job_id)

    def _run(self, job_id: UUID) -> None:
        raw = sqlite_state_store.claim_async_job(job_id)
        if raw is None:
            return
        job = AsyncJobRead.model_validate(raw)
        try:
            result = self._execute(job.job_type)
        except Exception as error:  # Keep worker exceptions from escaping the pool.
            logger.exception("Asynchronous job failed: %s", job.job_id)
            sqlite_state_store.fail_async_job(
                job.job_id,
                error_code="job_execution_failed",
                error_message=str(error)[:500] or error.__class__.__name__,
            )
            return
        sqlite_state_store.succeed_async_job(job.job_id, result)

    def _execute(self, job_type: AsyncJobType) -> dict[str, Any]:
        if job_type == AsyncJobType.agent_quality_evaluation:
            return agent_quality_service.run_evaluation().model_dump(mode="json")
        if job_type == AsyncJobType.rag_reindex:
            return agent_knowledge_base.reindex().model_dump(mode="json")
        raise ValueError(f"Unsupported asynchronous job type: {job_type}")


async_job_service = AsyncJobService()
