from __future__ import annotations

import unittest
from unittest.mock import patch

from app.schemas.quality import AgentQualityEvaluationCase
from app.services.agent_quality_service import agent_quality_service


class AgentQualityAdmissionTests(unittest.TestCase):
    @patch("app.services.rag_retriever.httpx.post")
    def test_offline_admission_is_reproducible_and_does_not_call_embedding(
        self,
        embedding_post,
    ) -> None:
        run = agent_quality_service.run_evaluation(execution_mode="offline")

        self.assertTrue(run.admission.admitted)
        self.assertEqual(run.execution_mode, "offline")
        self.assertEqual(run.total_cases, 8)
        self.assertEqual(run.passed_cases, 8)
        self.assertEqual(run.admission.critical_case_count, 7)
        embedding_post.assert_not_called()

    def test_failed_critical_case_rejects_admission(self) -> None:
        case = AgentQualityEvaluationCase(
            case_id="critical_bill",
            passed=False,
            expected_intent="create_bill",
            actual_intent="unsupported",
            critical=True,
        )
        admission = agent_quality_service._admission(
            {
                "policy_id": "test-policy",
                "dataset_version": "test",
                "minimum_pass_rate": 0.95,
            },
            [case],
            0.0,
        )

        self.assertFalse(admission.admitted)
        self.assertEqual(admission.failed_critical_case_ids, ["critical_bill"])
        self.assertIn("critical_cases_failed:critical_bill", admission.failure_reasons)


if __name__ == "__main__":
    unittest.main()
