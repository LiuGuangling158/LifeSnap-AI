from __future__ import annotations

import unittest
from unittest.mock import patch

from app.schemas.agent_release import AgentReleaseSnapshot, AgentReleaseState
from app.services.agent_release_service import AgentReleaseService


class AgentReleaseServiceTests(unittest.TestCase):
    def _snapshot(self, fingerprint: str = "a" * 64) -> AgentReleaseSnapshot:
        return AgentReleaseSnapshot(
            app_version="0.1.0",
            runtime_fingerprint=fingerprint,
            model_provider="deepseek",
            model_strategy="base_llm_with_rag_and_function_calling",
            runtime_model="deepseek-chat",
            knowledge_version_id="rag-test-version",
            quality_run_id="quality-run-1",
            quality_dataset_version="v2",
            quality_pass_rate=1.0,
            rag_dataset_version="v1",
            rag_recall_at_k=1.0,
            rag_citation_accuracy=1.0,
            rag_abstention_accuracy=1.0,
        )

    @patch("app.services.agent_release_service.sqlite_state_store.save_json")
    @patch("app.services.agent_release_service.sqlite_state_store.load_json", return_value=None)
    def test_candidate_promotion_and_rollback_are_durable(
        self,
        _load_json,
        save_json,
    ) -> None:
        service = AgentReleaseService()
        first = service.create_candidate(
            label="2026.10 stable",
            note="offline gate admitted",
            snapshot=self._snapshot(),
        )
        active = service.promote(first.release_id, current_fingerprint="a" * 64)
        second = service.create_candidate(
            label="2026.10 candidate",
            note=None,
            snapshot=self._snapshot("b" * 64),
        )
        next_active = service.promote(second.release_id, current_fingerprint="b" * 64)

        response = service.response()
        self.assertEqual(active.state, AgentReleaseState.active)
        self.assertEqual(next_active.state, AgentReleaseState.active)
        self.assertEqual(response.active_release_id, second.release_id)
        self.assertEqual(
            next(item for item in response.releases if item.release_id == first.release_id).state,
            AgentReleaseState.superseded,
        )

        rolled_back = service.rollback(first.release_id, current_fingerprint="a" * 64)
        self.assertEqual(rolled_back.state, AgentReleaseState.active)
        self.assertEqual(service.response().active_release_id, first.release_id)
        self.assertGreaterEqual(save_json.call_count, 4)

    @patch("app.services.agent_release_service.sqlite_state_store.save_json")
    @patch("app.services.agent_release_service.sqlite_state_store.load_json", return_value=None)
    def test_runtime_or_knowledge_drift_blocks_promotion(
        self,
        _load_json,
        _save_json,
    ) -> None:
        service = AgentReleaseService()
        candidate = service.create_candidate(
            label="guarded release",
            note=None,
            snapshot=self._snapshot(),
        )

        with self.assertRaisesRegex(ValueError, "differs from this release snapshot"):
            service.promote(candidate.release_id, current_fingerprint="b" * 64)

    @patch("app.services.agent_release_service.sqlite_state_store.save_json")
    @patch("app.services.agent_release_service.sqlite_state_store.load_json", return_value=None)
    def test_candidate_cannot_bypass_promotion_with_rollback(
        self,
        _load_json,
        _save_json,
    ) -> None:
        service = AgentReleaseService()
        candidate = service.create_candidate(
            label="candidate only",
            note=None,
            snapshot=self._snapshot(),
        )

        with self.assertRaisesRegex(ValueError, "Only a superseded Agent release"):
            service.rollback(candidate.release_id, current_fingerprint="a" * 64)


if __name__ == "__main__":
    unittest.main()
