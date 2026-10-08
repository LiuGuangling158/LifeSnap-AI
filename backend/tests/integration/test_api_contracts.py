import unittest
import json
from dataclasses import replace
from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from app.api import agent as agent_api
from app.main import create_app
from app.schemas.agent import BillCandidateData, ParseBillResponse
from app.schemas.async_job import AsyncJobRead, AsyncJobStatus, AsyncJobType
from app.schemas.bill import BillSource, TransactionType
from app.schemas.chat import ChatActionType
from app.services.bill_candidate_store import bill_candidate_store
from app.services.candidate_session_store import candidate_session_store
from app.services import admin_auth_service as admin_auth_module
from app.services.sqlite_state_store import sqlite_state_store
from app.core.config import settings


class ApiContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.client = TestClient(create_app())

    @classmethod
    def tearDownClass(cls) -> None:
        cls.client.close()

    def test_health_and_public_business_bootstrap_contract(self) -> None:
        health = self.client.get("/health")
        bootstrap = self.client.get("/app/bootstrap")

        self.assertEqual(health.status_code, 200)
        self.assertEqual(health.json()["status"], "ok")
        self.assertEqual(bootstrap.status_code, 200)
        self.assertIn("dashboard", bootstrap.json())

    def test_metrics_contract_exposes_operational_counters(self) -> None:
        self.client.get("/health")
        response = self.client.get("/metrics")

        self.assertEqual(response.status_code, 200)
        self.assertIn("lifesnap_http_requests_total", response.text)
        self.assertIn("lifesnap_http_request_p95_seconds", response.text)
        self.assertIn("lifesnap_operational_alerts_active", response.text)
        self.assertIn("lifesnap_async_jobs", response.text)
        self.assertIn("lifesnap_async_job_queue_lag_seconds", response.text)
        self.assertIn("lifesnap_model_invocations_total", response.text)

    def test_operational_alert_contract_evaluates_and_returns_history(self) -> None:
        evaluated = self.client.post("/observability/alerts/evaluate")
        listed = self.client.get("/observability/alerts")

        self.assertEqual(evaluated.status_code, 200)
        self.assertEqual(listed.status_code, 200)
        self.assertIn("active_count", evaluated.json())
        self.assertIn("alerts", listed.json())

    def test_quality_summary_contract_is_available_without_login(self) -> None:
        response = self.client.get("/quality/summary")

        self.assertEqual(response.status_code, 200)
        self.assertIn("feedback_count", response.json())
        self.assertIn("recent_evaluations", response.json())

    def test_agent_release_catalog_contract_is_available_without_login(self) -> None:
        response = self.client.get("/agent/releases")

        self.assertEqual(response.status_code, 200)
        self.assertIn("active_release_id", response.json())
        self.assertIn("releases", response.json())

    def test_model_usage_contract_is_available_without_login(self) -> None:
        response = self.client.get("/observability/model-usage")

        self.assertEqual(response.status_code, 200)
        self.assertIn("estimated_cost_usd", response.json())
        self.assertIn("records", response.json())

    def test_chat_response_includes_a_privacy_safe_agent_explanation(self) -> None:
        response = self.client.post(
            "/chat/messages",
            json={"message": "午餐花了 23 元"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        explanation = payload["explanation"]
        self.assertEqual(explanation["decision"], "candidate_ready")
        self.assertIn("rag_retrieval", explanation["reasoning_basis"])
        self.assertIn("function_tools", explanation["reasoning_basis"])
        self.assertEqual(explanation["guardrail"], "confirmation_required")
        self.assertNotIn("午餐", json.dumps(explanation, ensure_ascii=False))

        feedback = self.client.post(
            "/quality/feedback",
            json={"message_id": payload["message_id"], "verdict": "corrected"},
        )
        self.assertEqual(feedback.status_code, 201)
        self.assertTrue(feedback.json()["trace_id"])
        self.assertEqual(feedback.json()["trace_snapshot"]["intent"], "create_bill")

    def test_admin_can_read_durable_async_job_events(self) -> None:
        now = datetime.now(timezone.utc)
        job = AsyncJobRead(
            job_id=uuid4(),
            job_type=AsyncJobType.rag_reindex,
            status=AsyncJobStatus.queued,
            created_at=now,
            updated_at=now,
            available_at=now,
        )
        sqlite_state_store.create_or_get_async_job(job.model_dump(mode="json"))

        admin_settings = replace(settings, admin_api_key="contract-admin-key")
        with (
            patch.object(agent_api, "settings", admin_settings),
            patch.object(admin_auth_module, "settings", admin_settings),
        ):
            session = self.client.post(
                "/agent/admin-session",
                json={"admin_key": "contract-admin-key"},
            )
            self.assertEqual(session.status_code, 200)
            headers = {"Authorization": f"Bearer {session.json()['token']}"}
            response = self.client.get(f"/jobs/{job.job_id}/events", headers=headers)

        self.assertEqual(response.status_code, 200)
        events = response.json()
        self.assertTrue(events)
        self.assertIn("created", [event["event_type"] for event in events])

    def test_monthly_report_applies_budget_rules_and_detects_anomalies(self) -> None:
        invalid_budget = self.client.patch(
            "/settings/budget",
            json={"category_budgets": {"餐饮": -1}},
        )
        self.assertEqual(invalid_budget.status_code, 422)

        budget = self.client.patch(
            "/settings/budget",
            json={
                "monthly_budget": 100,
                "warning_threshold_percent": 80,
                "category_budgets": {"餐饮": 50},
            },
        )
        self.assertEqual(budget.status_code, 200)

        for amount, merchant, paid_at in (
            (60, "测试午餐", "2026-09-10T12:00:00+08:00"),
            (20, "测试咖啡", "2026-09-11T12:00:00+08:00"),
            (300, "测试大额消费", "2026-09-12T12:00:00+08:00"),
        ):
            response = self.client.post(
                "/bills",
                json={
                    "amount": amount,
                    "merchant": merchant,
                    "category": "餐饮",
                    "transaction_type": "expense",
                    "paid_at": paid_at,
                },
            )
            self.assertEqual(response.status_code, 201)

        report = self.client.get("/reports/monthly?year=2026&month=9")

        self.assertEqual(report.status_code, 200)
        payload = report.json()
        self.assertTrue(payload["alerts"])
        self.assertEqual(payload["category_budget_statuses"][0]["category"], "餐饮")
        self.assertEqual(payload["category_budget_statuses"][0]["status"], "over_budget")
        self.assertTrue(payload["anomalies"])

    def test_chat_candidate_session_rejects_stale_edits_and_confirms_latest_revision(self) -> None:
        candidate = bill_candidate_store.save(
            ParseBillResponse(
                candidate_id=uuid4(),
                confidence=0.9,
                data=BillCandidateData(
                    amount=28,
                    merchant="候选会话测试",
                    category="餐饮",
                    transaction_type=TransactionType.expense,
                    source=BillSource.ai_chat,
                ),
                field_confidence={"amount": 1, "transaction_type": 1},
                warnings=[],
            )
        )
        session = candidate_session_store.ensure(
            ChatActionType.bill_candidate,
            candidate.candidate_id,
        )
        first_edit = self.client.patch(
            f"/chat/candidates/{candidate.candidate_id}",
            json={
                "action_type": "bill_candidate",
                "candidate_session_id": str(session.session_id),
                "expected_revision": session.revision,
                "updates": {"merchant": "已更新的候选会话测试"},
            },
        )

        self.assertEqual(first_edit.status_code, 200)
        edited = first_edit.json()
        self.assertEqual(edited["candidate"]["data"]["merchant"], "已更新的候选会话测试")
        self.assertEqual(edited["candidate_session"]["revision"], 2)

        stale_edit = self.client.patch(
            f"/chat/candidates/{candidate.candidate_id}",
            json={
                "action_type": "bill_candidate",
                "candidate_session_id": str(session.session_id),
                "expected_revision": 1,
                "updates": {"merchant": "旧页面不应覆盖"},
            },
        )
        self.assertEqual(stale_edit.status_code, 409)

        confirmed = self.client.post(
            "/chat/confirm-action",
            json={
                "action_type": "bill_candidate",
                "candidate_id": str(candidate.candidate_id),
                "candidate_session_id": str(session.session_id),
                "expected_revision": 2,
            },
        )
        self.assertEqual(confirmed.status_code, 200)
        confirmed_payload = confirmed.json()
        self.assertEqual(confirmed_payload["candidate_session"]["revision"], 3)
        self.assertEqual(confirmed_payload["candidate_session"]["status"], "confirmed")
        self.assertEqual(
            confirmed_payload["created_bill"]["merchant"],
            "已更新的候选会话测试",
        )
