from __future__ import annotations

import time
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch
from uuid import uuid4

from app.schemas.async_job import AsyncJobRead, AsyncJobStatus, AsyncJobType
from app.services.async_job_service import async_job_service
from app.services.sqlite_state_store import sqlite_state_store


class AsyncJobServiceTests(unittest.TestCase):
    @patch.object(async_job_service, "_execute", return_value={"ok": True})
    def test_enqueued_job_persists_successful_result(self, execute) -> None:
        job = async_job_service.enqueue(AsyncJobType.agent_quality_evaluation)
        deadline = time.monotonic() + 3
        latest = None
        while time.monotonic() < deadline:
            latest = async_job_service.get(job.job_id)
            if latest and latest.status == AsyncJobStatus.succeeded:
                break
            time.sleep(0.02)

        self.assertIsNotNone(latest)
        self.assertEqual(latest.status, AsyncJobStatus.succeeded)
        self.assertEqual(latest.result, {"ok": True})
        self.assertEqual(latest.attempt, 1)
        execute.assert_called_once_with(AsyncJobType.agent_quality_evaluation)

    def test_quality_evaluation_job_runs_end_to_end(self) -> None:
        job = async_job_service.enqueue(AsyncJobType.agent_quality_evaluation)
        deadline = time.monotonic() + 5
        latest = None
        while time.monotonic() < deadline:
            latest = async_job_service.get(job.job_id)
            if latest and latest.status in {AsyncJobStatus.succeeded, AsyncJobStatus.failed}:
                break
            time.sleep(0.03)

        self.assertIsNotNone(latest)
        self.assertEqual(latest.status, AsyncJobStatus.succeeded)
        self.assertTrue(latest.result["admission"]["admitted"])

    @patch("app.services.async_job_service.agent_quality_service.run_evaluation")
    def test_live_evaluation_job_uses_live_execution_mode(self, run_evaluation) -> None:
        run_evaluation.return_value = Mock(model_dump=Mock(return_value={"mode": "live"}))

        result = async_job_service._execute(AsyncJobType.agent_quality_evaluation_live)

        self.assertEqual(result, {"mode": "live"})
        run_evaluation.assert_called_once_with(execution_mode="live")

    @patch.object(async_job_service, "_execute", return_value={"ok": True})
    def test_same_idempotency_key_returns_one_job(self, execute) -> None:
        key = f"unit-idempotency-{uuid4().hex}"
        first = async_job_service.enqueue(
            AsyncJobType.agent_quality_evaluation,
            idempotency_key=key,
        )
        duplicate = async_job_service.enqueue(
            AsyncJobType.agent_quality_evaluation,
            idempotency_key=key,
        )
        deadline = time.monotonic() + 3
        latest = None
        while time.monotonic() < deadline:
            latest = async_job_service.get(first.job_id)
            if latest and latest.status == AsyncJobStatus.succeeded:
                break
            time.sleep(0.02)

        self.assertEqual(first.job_id, duplicate.job_id)
        self.assertIsNotNone(latest)
        self.assertEqual(latest.status, AsyncJobStatus.succeeded)
        execute.assert_called_once_with(AsyncJobType.agent_quality_evaluation)

    @patch.object(async_job_service, "_retry_delay_seconds", return_value=0.05)
    @patch.object(
        async_job_service,
        "_execute",
        side_effect=[RuntimeError("temporary provider failure"), {"recovered": True}],
    )
    def test_transient_failure_is_retried_with_delayed_state(self, execute, retry_delay) -> None:
        job = async_job_service.enqueue(AsyncJobType.agent_quality_evaluation)
        deadline = time.monotonic() + 4
        latest = None
        while time.monotonic() < deadline:
            latest = async_job_service.get(job.job_id)
            if latest and latest.status == AsyncJobStatus.succeeded:
                break
            time.sleep(0.02)

        self.assertIsNotNone(latest)
        self.assertEqual(latest.status, AsyncJobStatus.succeeded)
        self.assertEqual(latest.attempt, 2)
        self.assertEqual(latest.result, {"recovered": True})
        self.assertEqual(execute.call_count, 2)
        retry_delay.assert_called_once_with(1)

    def test_expired_lease_is_recovered_for_another_worker(self) -> None:
        owner_id = f"unit-lease-{uuid4().hex}"
        now = datetime.now(timezone.utc)
        job = AsyncJobRead(
            job_id=uuid4(),
            job_type=AsyncJobType.rag_reindex,
            status=AsyncJobStatus.queued,
            created_at=now,
            updated_at=now,
            available_at=now,
            max_attempts=2,
        )
        sqlite_state_store.create_or_get_async_job(job.model_dump(mode="json"), owner_id=owner_id)
        claimed = sqlite_state_store.claim_async_job(
            job.job_id,
            owner_id=owner_id,
            worker_id="interrupted-worker",
            lease_token="expired-token",
            lease_expires_at=(now - timedelta(seconds=1)).isoformat(),
        )
        sqlite_state_store.recover_async_jobs(owner_id=owner_id)
        recovered = sqlite_state_store.get_async_job(job.job_id, owner_id=owner_id)

        self.assertIsNotNone(claimed)
        self.assertIsNotNone(recovered)
        self.assertEqual(recovered["status"], AsyncJobStatus.retry_scheduled.value)
        self.assertIsNone(recovered["lease_token"])
        self.assertEqual(recovered["attempt"], 1)
        event_types = [
            event["event_type"]
            for event in sqlite_state_store.list_async_job_events(job.job_id, owner_id=owner_id)
        ]
        self.assertEqual(event_types, ["lease_recovered", "claimed", "created"])

    def test_final_failure_can_be_redriven_with_durable_history(self) -> None:
        owner_id = f"unit-redrive-{uuid4().hex}"
        now = datetime.now(timezone.utc)
        job = AsyncJobRead(
            job_id=uuid4(),
            job_type=AsyncJobType.rag_reindex,
            status=AsyncJobStatus.queued,
            created_at=now,
            updated_at=now,
            available_at=now,
            max_attempts=1,
        )
        sqlite_state_store.create_or_get_async_job(job.model_dump(mode="json"), owner_id=owner_id)
        sqlite_state_store.claim_async_job(
            job.job_id,
            owner_id=owner_id,
            worker_id="failing-worker",
            lease_token="failing-token",
            lease_expires_at=(now + timedelta(minutes=1)).isoformat(),
        )
        sqlite_state_store.fail_async_job(
            job.job_id,
            owner_id=owner_id,
            error_code="test_failure",
            error_message="intentional final failure",
            lease_token="failing-token",
            retry_delay_seconds=0,
        )
        redriven = sqlite_state_store.redrive_async_job(job.job_id, owner_id=owner_id)
        events = sqlite_state_store.list_async_job_events(job.job_id, owner_id=owner_id)

        self.assertIsNotNone(redriven)
        self.assertEqual(redriven["status"], AsyncJobStatus.queued.value)
        self.assertEqual(redriven["attempt"], 0)
        self.assertEqual(
            [event["event_type"] for event in events],
            ["redriven", "failed", "claimed", "created"],
        )


if __name__ == "__main__":
    unittest.main()
