from __future__ import annotations

import unittest
from datetime import datetime, timezone
from uuid import uuid4

from app.core.user_context import reset_current_owner_id, set_current_owner_id
from app.schemas.quality import (
    AgentQualityEvaluationCase,
    AgentQualityEvaluationRun,
    OnlineEvaluationAnnotationCreate,
    RagQualityEvaluationSummary,
)
from app.services.agent_quality_service import agent_quality_service
from app.services.sqlite_state_store import sqlite_state_store


class EvaluationGovernanceTests(unittest.TestCase):
    def test_dataset_snapshot_sampling_consistency_and_run_comparison(self) -> None:
        token = set_current_owner_id(f"evaluation-governance-{uuid4().hex}")
        try:
            now = datetime.now(timezone.utc)
            for trace_id, intent in ((uuid4().hex, "create_bill"), (uuid4().hex, "analyze_bills")):
                sqlite_state_store.append_agent_trace(
                    {
                        "trace_id": trace_id,
                        "occurred_at": now.isoformat(),
                        "request_id": "governance-test",
                        "message_id": str(uuid4()),
                        "intent": intent,
                        "action_type": "bill_candidate",
                        "model_provider": "test-provider",
                        "model_strategy": "test-agent",
                        "outcome": "completed",
                        "latency_ms": 9.0,
                        "function_call_count": 1,
                        "knowledge_hit_count": 1,
                        "warning_count": 0,
                        "payload": {"agent_release_label": "test-release"},
                    }
                )

            draft = agent_quality_service.create_dataset_snapshot(approval_note="Prepared for review")
            self.assertEqual(draft.status, "draft")
            approved = agent_quality_service.approve_dataset_snapshot(
                draft.snapshot_id,
                approval_note="Second reviewer approved the suite.",
            )
            self.assertEqual(approved.status, "approved")

            samples = agent_quality_service.collect_online_samples(requested_count=2)
            self.assertEqual(len(samples), 2)
            sample = samples[0]
            self.assertNotIn("message", sample.snapshot)
            agent_quality_service.annotate_online_sample(
                sample.sample_id,
                OnlineEvaluationAnnotationCreate(annotator_id="reviewer-a", verdict="pass"),
            )
            agent_quality_service.annotate_online_sample(
                sample.sample_id,
                OnlineEvaluationAnnotationCreate(annotator_id="reviewer-b", verdict="fail"),
            )
            consistency = agent_quality_service.annotation_consistency()
            self.assertEqual(consistency.dual_annotated_samples, 1)
            self.assertEqual(consistency.disagreement_count, 1)
            self.assertEqual(consistency.agreement_rate, 0.0)
            self.assertEqual(consistency.cohens_kappa, 0.0)

            baseline = AgentQualityEvaluationRun(
                run_id=uuid4(),
                created_at=now,
                total_cases=1,
                passed_cases=1,
                pass_rate=1.0,
                model_strategy="baseline-model",
                cases=[AgentQualityEvaluationCase(case_id="bill", passed=True, expected_intent="create_bill", actual_intent="create_bill")],
                rag_evaluation=RagQualityEvaluationSummary(recall_at_k=1.0, citation_accuracy=1.0, abstention_accuracy=1.0),
            )
            candidate = AgentQualityEvaluationRun(
                run_id=uuid4(),
                created_at=now,
                total_cases=1,
                passed_cases=0,
                pass_rate=0.0,
                model_strategy="candidate-model",
                cases=[AgentQualityEvaluationCase(case_id="bill", passed=False, expected_intent="create_bill", actual_intent="unsupported")],
                rag_evaluation=RagQualityEvaluationSummary(recall_at_k=0.5, citation_accuracy=0.5, abstention_accuracy=1.0),
            )
            sqlite_state_store.append_agent_quality_evaluation(baseline.model_dump(mode="json"))
            sqlite_state_store.append_agent_quality_evaluation(candidate.model_dump(mode="json"))
            comparison = agent_quality_service.compare_evaluations(baseline.run_id, candidate.run_id)
            self.assertEqual(comparison.pass_rate_delta, -1.0)
            self.assertEqual(comparison.newly_failed_case_ids, ["bill"])
            self.assertEqual(comparison.rag_recall_at_k_delta, -0.5)
        finally:
            reset_current_owner_id(token)


if __name__ == "__main__":
    unittest.main()
