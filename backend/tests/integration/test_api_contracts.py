import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import create_app
from app.schemas.agent import BillCandidateData, ParseBillResponse
from app.schemas.bill import BillSource, TransactionType
from app.schemas.chat import ChatActionType
from app.services.bill_candidate_store import bill_candidate_store
from app.services.candidate_session_store import candidate_session_store


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

    def test_quality_summary_contract_is_available_without_login(self) -> None:
        response = self.client.get("/quality/summary")

        self.assertEqual(response.status_code, 200)
        self.assertIn("feedback_count", response.json())
        self.assertIn("recent_evaluations", response.json())

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
