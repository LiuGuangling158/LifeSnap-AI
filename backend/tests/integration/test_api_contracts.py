import unittest

from fastapi.testclient import TestClient

from app.main import create_app


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
