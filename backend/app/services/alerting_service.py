from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from app.core.config import settings
from app.core.user_context import current_owner_id
from app.schemas.observability import (
    AlertSeverity,
    AlertStatus,
    OperationalAlert,
    OperationalAlertSummary,
)
from app.services.agent_quality_service import agent_quality_service
from app.services.diagnostics_service import diagnostics_service
from app.services.observability_service import observability_service
from app.services.model_invocation_service import model_invocation_service
from app.services.sqlite_state_store import sqlite_state_store


logger = logging.getLogger(__name__)


class AlertingService:
    """Evaluates privacy-safe operational signals into durable alert states."""

    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.RLock()

    def start(self) -> None:
        try:
            self.evaluate()
        except Exception:
            # Monitoring must not prevent the business application from starting.
            logger.exception("Initial operational alert evaluation failed")
        if settings.alert_evaluation_interval_seconds <= 0:
            return
        with self._lock:
            if self._thread and self._thread.is_alive():
                return
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._run_loop,
                name="lifesnap-alerting",
                daemon=True,
            )
            self._thread.start()

    def shutdown(self) -> None:
        self._stop_event.set()
        with self._lock:
            thread = self._thread
            self._thread = None
        if thread and thread.is_alive():
            thread.join(timeout=2)

    def evaluate(self) -> OperationalAlertSummary:
        owner_id = current_owner_id()
        previous_records = {
            str(record["fingerprint"]): record
            for record in sqlite_state_store.list_operational_alerts(
                owner_id=owner_id,
                include_resolved=True,
            )
        }
        monitoring = observability_service.summary(owner_id=owner_id)
        quality = agent_quality_service.summary()
        readiness = diagnostics_service.readiness()
        model_usage = model_invocation_service.summary()
        candidates: list[dict] = []

        if (
            monitoring.request_count >= settings.alert_minimum_request_count
            and monitoring.error_rate >= settings.alert_http_error_rate_threshold
        ):
            candidates.append(
                self._candidate(
                    rule_id="http_error_rate_high",
                    severity=AlertSeverity.critical,
                    title="HTTP error rate is high",
                    summary=(
                        f"HTTP 5xx rate is {monitoring.error_rate:.1%} across "
                        f"{monitoring.request_count} requests."
                    ),
                    metadata={
                        "error_rate": monitoring.error_rate,
                        "request_count": monitoring.request_count,
                        "error_count": monitoring.error_count,
                        "threshold": settings.alert_http_error_rate_threshold,
                    },
                )
            )

        if (
            monitoring.agent_trace_count >= settings.alert_minimum_agent_trace_count
            and monitoring.agent_p95_latency_ms >= settings.alert_agent_p95_latency_ms
        ):
            candidates.append(
                self._candidate(
                    rule_id="agent_latency_high",
                    severity=AlertSeverity.warning,
                    title="Agent latency is high",
                    summary=(
                        f"Agent P95 latency is {monitoring.agent_p95_latency_ms:.0f} ms "
                        f"across {monitoring.agent_trace_count} traces."
                    ),
                    metadata={
                        "agent_p95_latency_ms": monitoring.agent_p95_latency_ms,
                        "trace_count": monitoring.agent_trace_count,
                        "threshold_ms": settings.alert_agent_p95_latency_ms,
                    },
                )
            )

        model_attempts = model_usage.success_count + model_usage.failure_count
        if model_usage.active_circuit_count:
            candidates.append(
                self._candidate(
                    rule_id="model_circuit_open",
                    severity=AlertSeverity.warning,
                    title="External model circuit is open",
                    summary=(
                        f"{model_usage.active_circuit_count} model circuit breaker(s) are open; "
                        "the Agent is using its local fallback."
                    ),
                    metadata={"active_circuit_count": model_usage.active_circuit_count},
                )
            )

        if (
            model_attempts >= settings.alert_minimum_model_call_count
            and model_usage.failure_count / model_attempts
            >= settings.alert_model_failure_rate_threshold
        ):
            candidates.append(
                self._candidate(
                    rule_id="model_failure_rate_high",
                    severity=AlertSeverity.warning,
                    title="External model failure rate is high",
                    summary=(
                        f"Model failure rate is {model_usage.failure_count / model_attempts:.1%} "
                        f"across {model_attempts} completed calls."
                    ),
                    metadata={
                        "failure_count": model_usage.failure_count,
                        "completed_call_count": model_attempts,
                        "threshold": settings.alert_model_failure_rate_threshold,
                    },
                )
            )

        if (
            settings.alert_model_cost_threshold_usd > 0
            and model_usage.estimated_cost_usd >= settings.alert_model_cost_threshold_usd
        ):
            candidates.append(
                self._candidate(
                    rule_id="model_cost_threshold_exceeded",
                    severity=AlertSeverity.warning,
                    title="External model cost threshold exceeded",
                    summary=(
                        f"Estimated model cost is ${model_usage.estimated_cost_usd:.4f}, "
                        "above the configured threshold."
                    ),
                    metadata={
                        "estimated_cost_usd": model_usage.estimated_cost_usd,
                        "threshold_usd": settings.alert_model_cost_threshold_usd,
                    },
                )
            )

        evaluation = quality.latest_evaluation
        if evaluation is not None and not evaluation.admission.admitted:
            candidates.append(
                self._candidate(
                    rule_id="agent_admission_rejected",
                    severity=AlertSeverity.critical,
                    title="Offline Agent admission is rejected",
                    summary="The latest deterministic Agent release gate is not admitted.",
                    metadata={
                        "run_id": str(evaluation.run_id),
                        "dataset_version": evaluation.dataset_version,
                        "failure_reasons": evaluation.admission.failure_reasons,
                    },
                )
            )

        if readiness.status == "action_required":
            candidates.append(
                self._candidate(
                    rule_id="production_readiness_action_required",
                    severity=AlertSeverity.warning,
                    title="Production readiness requires action",
                    summary="At least one production readiness component requires action.",
                    metadata={
                        "action_required_count": readiness.action_required_count,
                        "component_names": [
                            component.name
                            for component in readiness.components
                            if component.status == "action_required"
                        ],
                    },
                )
            )

        records = sqlite_state_store.sync_operational_alerts(candidates, owner_id=owner_id)
        self._emit_lifecycle_events(records, previous_records)
        return self._summary(records)

    def summary(self, *, include_resolved: bool = True) -> OperationalAlertSummary:
        records = sqlite_state_store.list_operational_alerts(
            owner_id=current_owner_id(),
            include_resolved=include_resolved,
        )
        return self._summary(records)

    def _run_loop(self) -> None:
        interval = settings.alert_evaluation_interval_seconds
        while not self._stop_event.wait(interval):
            try:
                self.evaluate()
            except Exception:
                logger.exception("Operational alert evaluation failed")

    @staticmethod
    def _candidate(
        *,
        rule_id: str,
        severity: AlertSeverity,
        title: str,
        summary: str,
        metadata: dict,
    ) -> dict:
        return {
            "fingerprint": rule_id,
            "rule_id": rule_id,
            "severity": severity.value,
            "title": title,
            "summary": summary,
            "metadata": metadata,
        }

    @staticmethod
    def _summary(records: list[dict]) -> OperationalAlertSummary:
        alerts = [OperationalAlert.model_validate(record) for record in records]
        active = [alert for alert in alerts if alert.status == AlertStatus.active]
        return OperationalAlertSummary(
            generated_at=datetime.now(timezone.utc),
            active_count=len(active),
            critical_count=sum(1 for alert in active if alert.severity == AlertSeverity.critical),
            warning_count=sum(1 for alert in active if alert.severity == AlertSeverity.warning),
            resolved_count=sum(1 for alert in alerts if alert.status == AlertStatus.resolved),
            alerts=alerts,
        )

    @staticmethod
    def _emit_lifecycle_events(
        records: list[dict],
        previous_records: dict[str, dict],
    ) -> None:
        for record in records:
            fingerprint = str(record["fingerprint"])
            previous = previous_records.get(fingerprint)
            changed = (
                previous is None
                or previous.get("status") != record.get("status")
                or previous.get("severity") != record.get("severity")
            )
            if not changed:
                continue
            observability_service.record_operational_alert_event(
                alert_id=str(record["alert_id"]),
                rule_id=str(record["rule_id"]),
                severity=str(record["severity"]),
                status=str(record["status"]),
                occurrence_count=int(record["occurrence_count"]),
            )


alerting_service = AlertingService()
