from __future__ import annotations

import logging
import threading
from concurrent.futures import Future, ThreadPoolExecutor, wait
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from app.core.config import settings
from app.schemas.async_job import AsyncJobRead, AsyncJobStatus, AsyncJobType
from app.services.agent_knowledge_base import agent_knowledge_base
from app.services.agent_quality_service import agent_quality_service
from app.services.observability_service import observability_service
from app.services.sqlite_state_store import sqlite_state_store


logger = logging.getLogger(__name__)


class AsyncJobService:
    """Single-node durable worker with leases, heartbeats, and delayed retries."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._executor: ThreadPoolExecutor | None = None
        self._scheduler_thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._wake_event = threading.Event()
        self._submitted: dict[UUID, Future[None]] = {}
        self._worker_id = f"lifesnap-{uuid4().hex[:12]}"

    def start(self) -> None:
        with self._lock:
            if self._executor is None:
                self._executor = ThreadPoolExecutor(
                    max_workers=settings.async_job_worker_count,
                    thread_name_prefix="lifesnap-job",
                )
                self._stop_event.clear()
                self._wake_event.clear()
                sqlite_state_store.recover_async_jobs()
                self._scheduler_thread = threading.Thread(
                    target=self._scheduler_loop,
                    name="lifesnap-job-scheduler",
                    daemon=True,
                )
                self._scheduler_thread.start()
        self._wake_event.set()

    def shutdown(self) -> None:
        self._stop_event.set()
        self._wake_event.set()
        with self._lock:
            scheduler = self._scheduler_thread
            executor = self._executor
            futures = list(self._submitted.values())
            self._scheduler_thread = None
            self._executor = None
            self._submitted = {}
        if scheduler and scheduler.is_alive():
            scheduler.join(timeout=2)
        if futures:
            wait(futures, timeout=min(10, settings.async_job_lease_seconds / 2))
        if executor is not None:
            executor.shutdown(wait=False, cancel_futures=False)

    def enqueue(
        self,
        job_type: AsyncJobType,
        *,
        idempotency_key: str | None = None,
    ) -> AsyncJobRead:
        self.start()
        now = datetime.now(timezone.utc)
        job = AsyncJobRead(
            job_id=uuid4(),
            job_type=job_type,
            status=AsyncJobStatus.queued,
            created_at=now,
            updated_at=now,
            available_at=now,
            max_attempts=settings.async_job_max_attempts,
            idempotency_key=self._normalize_idempotency_key(idempotency_key),
        )
        raw, created = sqlite_state_store.create_or_get_async_job(job.model_dump(mode="json"))
        if created:
            self._wake_event.set()
        return AsyncJobRead.model_validate(raw)

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
        self._wake_event.set()
        return AsyncJobRead.model_validate(raw)

    def cancel(self, job_id: UUID) -> AsyncJobRead | None:
        raw = sqlite_state_store.cancel_async_job(job_id)
        return AsyncJobRead.model_validate(raw) if raw else None

    def _scheduler_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._dispatch_due_jobs()
            except Exception:
                logger.exception("Asynchronous job scheduler iteration failed")
            self._wake_event.wait(settings.async_job_poll_interval_seconds)
            self._wake_event.clear()

    def _dispatch_due_jobs(self) -> None:
        with self._lock:
            executor = self._executor
            capacity = settings.async_job_worker_count - len(self._submitted)
        if executor is None or capacity <= 0:
            return
        for raw in sqlite_state_store.list_dispatchable_async_jobs(limit=capacity):
            self._dispatch(UUID(str(raw["job_id"])))

    def _dispatch(self, job_id: UUID) -> None:
        with self._lock:
            if self._executor is None or job_id in self._submitted:
                return
            future = self._executor.submit(self._run, job_id)
            self._submitted[job_id] = future
            future.add_done_callback(lambda _: self._mark_dispatch_complete(job_id))

    def _mark_dispatch_complete(self, job_id: UUID) -> None:
        with self._lock:
            self._submitted.pop(job_id, None)
        self._wake_event.set()

    def _run(self, job_id: UUID) -> None:
        lease_token = uuid4().hex
        raw = sqlite_state_store.claim_async_job(
            job_id,
            worker_id=self._worker_id,
            lease_token=lease_token,
            lease_expires_at=self._lease_expiry(),
        )
        if raw is None:
            return
        job = AsyncJobRead.model_validate(raw)
        observability_service.record_async_job_event(
            job_id=str(job.job_id),
            job_type=job.job_type.value,
            status=AsyncJobStatus.running.value,
            attempt=job.attempt,
            max_attempts=job.max_attempts,
        )
        heartbeat_stop = threading.Event()
        heartbeat = threading.Thread(
            target=self._heartbeat_loop,
            args=(job.job_id, lease_token, heartbeat_stop),
            name=f"lifesnap-job-lease-{job.job_id.hex[:8]}",
            daemon=True,
        )
        heartbeat.start()
        try:
            result = self._execute(job.job_type)
        except Exception as error:  # Worker exceptions are recorded and retried safely.
            logger.exception("Asynchronous job failed: %s", job.job_id)
            retry_delay_seconds = self._retry_delay_seconds(job.attempt)
            sqlite_state_store.fail_async_job(
                job.job_id,
                error_code="job_execution_failed",
                error_message=str(error)[:500] or error.__class__.__name__,
                lease_token=lease_token,
                retry_delay_seconds=retry_delay_seconds,
            )
            observability_service.record_async_job_event(
                job_id=str(job.job_id),
                job_type=job.job_type.value,
                status=(
                    AsyncJobStatus.retry_scheduled.value
                    if job.attempt < job.max_attempts
                    else AsyncJobStatus.failed.value
                ),
                attempt=job.attempt,
                max_attempts=job.max_attempts,
                retry_delay_seconds=retry_delay_seconds if job.attempt < job.max_attempts else None,
            )
        else:
            sqlite_state_store.succeed_async_job(
                job.job_id,
                result,
                lease_token=lease_token,
            )
            observability_service.record_async_job_event(
                job_id=str(job.job_id),
                job_type=job.job_type.value,
                status=AsyncJobStatus.succeeded.value,
                attempt=job.attempt,
                max_attempts=job.max_attempts,
            )
        finally:
            heartbeat_stop.set()
            heartbeat.join(timeout=1)
            self._wake_event.set()

    def _heartbeat_loop(
        self,
        job_id: UUID,
        lease_token: str,
        stop_event: threading.Event,
    ) -> None:
        interval = max(1.0, settings.async_job_lease_seconds / 3)
        while not stop_event.wait(interval):
            if not sqlite_state_store.renew_async_job_lease(
                job_id,
                lease_token=lease_token,
                lease_expires_at=self._lease_expiry(),
            ):
                return

    @staticmethod
    def _normalize_idempotency_key(value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if len(normalized) > 128:
            raise ValueError("Idempotency-Key must be at most 128 characters")
        return normalized or None

    @staticmethod
    def _lease_expiry() -> str:
        return (datetime.now(timezone.utc) + timedelta(seconds=settings.async_job_lease_seconds)).isoformat()

    @staticmethod
    def _retry_delay_seconds(attempt: int) -> float:
        return min(300.0, settings.async_job_retry_base_seconds * (2 ** max(0, attempt - 1)))

    def _execute(self, job_type: AsyncJobType) -> dict[str, Any]:
        if job_type == AsyncJobType.agent_quality_evaluation:
            return agent_quality_service.run_evaluation().model_dump(mode="json")
        if job_type == AsyncJobType.agent_quality_evaluation_live:
            return agent_quality_service.run_evaluation(
                execution_mode="live"
            ).model_dump(mode="json")
        if job_type == AsyncJobType.rag_reindex:
            return agent_knowledge_base.reindex().model_dump(mode="json")
        raise ValueError(f"Unsupported asynchronous job type: {job_type}")


async_job_service = AsyncJobService()
