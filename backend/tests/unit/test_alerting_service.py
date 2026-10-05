import unittest
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

from app.schemas.observability import MonitoringSummary
from app.services.alerting_service import alerting_service
from app.services.sqlite_state_store import sqlite_state_store


class AlertingServiceTests(unittest.TestCase):
    def test_evaluate_creates_alerts_for_threshold_breaches(self) -> None:
        monitoring = MonitoringSummary(
            generated_at=datetime.now(timezone.utc),
            uptime_seconds=120,
            request_count=40,
            error_count=4,
            error_rate=0.1,
            average_request_latency_ms=30,
            agent_trace_count=20,
            agent_average_latency_ms=9000,
            agent_p95_latency_ms=9000,
            agent_outcomes={},
        )
        quality = SimpleNamespace(latest_evaluation=None)
        readiness = SimpleNamespace(
            status="ready",
            action_required_count=0,
            components=[],
        )

        with (
            patch("app.services.alerting_service.observability_service.summary", return_value=monitoring),
            patch("app.services.alerting_service.agent_quality_service.summary", return_value=quality),
            patch("app.services.alerting_service.diagnostics_service.readiness", return_value=readiness),
            patch("app.services.alerting_service.sqlite_state_store.sync_operational_alerts", return_value=[]) as sync,
        ):
            summary = alerting_service.evaluate()

        candidates = sync.call_args.args[0]
        self.assertEqual(summary.active_count, 0)
        self.assertEqual(
            {candidate["rule_id"] for candidate in candidates},
            {"http_error_rate_high", "agent_latency_high"},
        )
        self.assertEqual(
            next(candidate for candidate in candidates if candidate["rule_id"] == "http_error_rate_high")["severity"],
            "critical",
        )

    def test_persisted_alert_is_deduplicated_then_resolved(self) -> None:
        owner_id = f"alerting-test-{uuid4().hex}"
        candidate = {
            "fingerprint": "test-rule",
            "rule_id": "test-rule",
            "severity": "warning",
            "title": "Test alert",
            "summary": "A deterministic test alert.",
            "metadata": {"source": "unit-test"},
        }

        first = sqlite_state_store.sync_operational_alerts([candidate], owner_id=owner_id)
        second = sqlite_state_store.sync_operational_alerts([candidate], owner_id=owner_id)
        resolved = sqlite_state_store.sync_operational_alerts([], owner_id=owner_id)

        self.assertEqual(len(first), 1)
        self.assertEqual(first[0]["status"], "active")
        self.assertEqual(second[0]["occurrence_count"], 2)
        self.assertEqual(resolved[0]["status"], "resolved")
        self.assertIsNotNone(resolved[0]["resolved_at"])

