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
