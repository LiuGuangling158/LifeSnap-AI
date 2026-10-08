from __future__ import annotations

import unittest
from datetime import datetime, timezone
from uuid import uuid4

from app.core.user_context import reset_current_owner_id, set_current_owner_id
from app.schemas.quality import (
    AgentQualityFeedbackCreate,
    AgentQualityFeedbackReviewRequest,
)
from app.services.agent_quality_service import agent_quality_service
from app.services.sqlite_state_store import sqlite_state_store


class AgentFeedbackLoopTests(unittest.TestCase):
    def test_feedback_links_trace_and_promotes_a_sanitized_regression_case(self) -> None:
        owner_id = f"feedback-loop-{uuid4().hex}"
        message_id = uuid4()
        trace_id = uuid4().hex
        token = set_current_owner_id(owner_id)
        try:
            sqlite_state_store.append_agent_trace(
                {
                    "trace_id": trace_id,
                    "occurred_at": datetime.now(timezone.utc).isoformat(),
                    "request_id": "feedback-loop-test",
                    "message_id": str(message_id),
                    "intent": "create_bill",
                    "action_type": "bill_candidate",
                    "model_provider": "test-provider",
                    "model_strategy": "test-agent",
                    "outcome": "needs_confirmation",
                    "latency_ms": 12.5,
                    "function_call_count": 2,
                    "knowledge_hit_count": 1,
                    "warning_count": 0,
                    "payload": {"agent_release_label": "test-release"},
                }
            )
            feedback = agent_quality_service.record_feedback(
                AgentQualityFeedbackCreate(
                    message_id=message_id,
                    verdict="corrected",
                    expected_intent="create_bill",
                    expected_category="餐饮",
                )
            )

            self.assertEqual(feedback.trace_id, trace_id)
            self.assertEqual(feedback.trace_snapshot["model_provider"], "test-provider")
            self.assertEqual(feedback.review_status, "pending")

            reviewed = agent_quality_service.review_feedback(
                feedback.feedback_id,
                AgentQualityFeedbackReviewRequest(
                    disposition="promote",
                    evaluation_prompt="午餐 28 元",
                    expected_intent="create_bill",
                    expected_category="餐饮",
                    review_note="Sanitized and approved for regression coverage.",
                ),
            )

            self.assertEqual(reviewed.review_status, "promoted")
            self.assertTrue(reviewed.promoted_case_id)
            cases = sqlite_state_store.list_agent_quality_feedback_cases()
            self.assertEqual(len(cases), 1)
            self.assertEqual(cases[0]["message"], "午餐 28 元")
            self.assertEqual(cases[0]["tools"], ["bill_candidate"])

            reopened = agent_quality_service.record_feedback(
                AgentQualityFeedbackCreate(
                    message_id=message_id,
                    verdict="rejected",
                )
            )
            self.assertEqual(reopened.feedback_id, feedback.feedback_id)
            self.assertEqual(reopened.review_status, "pending")
            self.assertEqual(sqlite_state_store.list_agent_quality_feedback_cases(), [])
        finally:
            reset_current_owner_id(token)


if __name__ == "__main__":
    unittest.main()
