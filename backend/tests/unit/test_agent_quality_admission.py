from __future__ import annotations

import unittest
from unittest.mock import patch
from uuid import uuid4

from app.schemas.quality import AgentQualityEvaluationCase, AgentQualityEvaluationRun
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


    def test_newly_failed_case_rejects_non_regression_policy(self) -> None:
        baseline = AgentQualityEvaluationRun(
            run_id=uuid4(),
            created_at="2026-01-01T00:00:00Z",
            total_cases=1,
            passed_cases=1,
            pass_rate=1.0,
            model_strategy="offline_rule_based_admission",
            cases=[
                AgentQualityEvaluationCase(
                    case_id="bill_dining",
                    passed=True,
                    expected_intent="create_bill",
                    actual_intent="create_bill",
                )
            ],
        )
        current = [
            AgentQualityEvaluationCase(
                case_id="bill_dining",
                passed=False,
                expected_intent="create_bill",
                actual_intent="unsupported",
            )
        ]

        regression = agent_quality_service._regression(baseline, current, 0.0)
        admission = agent_quality_service._admission(
            {
                "policy_id": "test-policy",
                "dataset_version": "test",
                "minimum_pass_rate": 0.0,
                "require_no_regression": True,
            },
            current,
            0.0,
            regression,
        )

        self.assertTrue(regression.regressed)
        self.assertEqual(regression.newly_failed_case_ids, ["bill_dining"])
        self.assertFalse(admission.admitted)
        self.assertIn("quality_regression:bill_dining", admission.failure_reasons)
if __name__ == "__main__":
    unittest.main()
