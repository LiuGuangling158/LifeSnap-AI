from __future__ import annotations

import time
import unittest
from unittest.mock import patch

from app.schemas.async_job import AsyncJobStatus, AsyncJobType
from app.services.async_job_service import async_job_service


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


if __name__ == "__main__":
    unittest.main()
