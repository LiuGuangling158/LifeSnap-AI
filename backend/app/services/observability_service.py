from __future__ import annotations

import json
import logging
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.schemas.chat import ChatAgentStepStatus, ChatMessageResponse
from app.schemas.observability import (
    AgentExecutionTrace,
    AgentExecutionTraceListResponse,
    MonitoringSummary,
)
from app.services.sqlite_state_store import sqlite_state_store
from app.services.model_invocation_service import model_invocation_service


_ID_PATH_SEGMENT = re.compile(r"/(?:[0-9a-f]{32}|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})(?=/|$)", re.I)


class ObservabilityService:
    def __init__(self) -> None:
        self._started_at = time.perf_counter()
        self._lock = threading.RLock()
        self._http_counts: dict[tuple[str, str, int], int] = {}
        self._http_latency: dict[tuple[str, str], list[float]] = {}
        self._agent_counts: dict[tuple[str, str, str], int] = {}
        self._agent_latency: list[float] = []
        self._async_queue_backend = "database"
        self._async_queue_configured = True
        self._async_queue_redis_available: bool | None = None
        self._async_queue_signal_failure_count = 0
        self._logger = logging.getLogger("lifesnap.observability")
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.INFO)
            self._logger.propagate = False

    def record_http(
        self,
        *,
        method: str,
        path: str,
        status_code: int,
        duration_ms: float,
        request_id: str | None,
        user_id: str | None,
    ) -> None:
        normalized_path = self._normalize_path(path)
        with self._lock:
            key = (method, normalized_path, status_code)
            self._http_counts[key] = self._http_counts.get(key, 0) + 1
            latency_key = (method, normalized_path)
            self._http_latency.setdefault(latency_key, []).append(duration_ms)
        self._emit(
            {
                "event": "http_request",
                "request_id": request_id,
                "user_id": user_id,
                "method": method,
                "path": normalized_path,
                "status_code": status_code,
                "latency_ms": round(duration_ms, 2),
            }
        )

    def record_agent_response(
        self,
        response: ChatMessageResponse,
        *,
        request_id: str | None,
        owner_id: str,
        duration_ms: float,
    ) -> AgentExecutionTrace:
        model = response.model_trace
        outcome = self._agent_outcome(response)
        trace = AgentExecutionTrace(
            trace_id=uuid4().hex,
            occurred_at=datetime.now(timezone.utc),
            request_id=request_id,
            message_id=str(response.message_id),
            intent=response.intent.value,
            action_type=response.action_type.value,
            model_provider=model.provider if model else "unknown",
            model_strategy=model.strategy if model else "unknown",
            outcome=outcome,
            latency_ms=round(duration_ms, 2),
            function_call_count=len(response.function_calls),
            knowledge_hit_count=len(response.knowledge_hits),
            warning_count=len(response.warnings),
            payload={
                "function_tools": [call.name for call in response.function_calls[:12]],
                "function_statuses": [call.status for call in response.function_calls[:12]],
                "knowledge_source_ids": [hit.source_id for hit in response.knowledge_hits[:8]],
                "agent_step_statuses": [step.status.value for step in response.agent_steps[:10]],
                "agent_release_id": model.release_id if model else None,
                "agent_release_label": model.release_label if model else None,
            },
        )
        sqlite_state_store.append_agent_trace(trace.model_dump(mode="json"), owner_id=owner_id)
        with self._lock:
            key = (trace.intent, trace.outcome, trace.model_strategy)
            self._agent_counts[key] = self._agent_counts.get(key, 0) + 1
            self._agent_latency.append(trace.latency_ms)
        self._emit(
            {
                "event": "agent_execution",
                "trace_id": trace.trace_id,
                "request_id": request_id,
                "user_id": owner_id,
                "intent": trace.intent,
                "outcome": trace.outcome,
                "model_provider": trace.model_provider,
                "model_strategy": trace.model_strategy,
                "latency_ms": trace.latency_ms,
                "function_call_count": trace.function_call_count,
                "knowledge_hit_count": trace.knowledge_hit_count,
                "warning_count": trace.warning_count,
            }
        )
        return trace

    def record_operational_alert_event(
        self,
        *,
        alert_id: str,
        rule_id: str,
        severity: str,
        status: str,
        occurrence_count: int,
    ) -> None:
        """Emit lifecycle events without carrying diagnostic or user content."""
        self._emit(
            {
                "event": "operational_alert",
                "alert_id": alert_id,
                "rule_id": rule_id,
                "severity": severity,
                "status": status,
                "occurrence_count": occurrence_count,
            }
        )

    def record_async_job_event(
        self,
        *,
        job_id: str,
        job_type: str,
        status: str,
        attempt: int,
        max_attempts: int,
        retry_delay_seconds: float | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "event": "async_job",
            "job_id": job_id,
            "job_type": job_type,
            "status": status,
            "attempt": attempt,
            "max_attempts": max_attempts,
        }
        if retry_delay_seconds is not None:
            payload["retry_delay_seconds"] = round(retry_delay_seconds, 3)
        self._emit(payload)

    def record_async_queue_status(
        self,
        *,
        backend: str,
        configured: bool,
        redis_available: bool | None,
        signal_failure_count: int,
    ) -> None:
        """Keep queue transport health visible without logging task payloads."""
        with self._lock:
            self._async_queue_backend = backend
            self._async_queue_configured = configured
            self._async_queue_redis_available = redis_available
            self._async_queue_signal_failure_count = signal_failure_count

    def summary(self, *, owner_id: str) -> MonitoringSummary:
        with self._lock:
            request_count = sum(self._http_counts.values())
            error_count = sum(
                count
                for (_, _, status_code), count in self._http_counts.items()
                if status_code >= 500
            )
            request_latencies = [
                latency
                for latencies in self._http_latency.values()
                for latency in latencies
            ]
        trace_summary = sqlite_state_store.agent_trace_summary(owner_id=owner_id)
        return MonitoringSummary(
            generated_at=datetime.now(timezone.utc),
            uptime_seconds=round(time.perf_counter() - self._started_at, 2),
            request_count=request_count,
            error_count=error_count,
            error_rate=round(error_count / request_count, 4) if request_count else 0.0,
            average_request_latency_ms=round(
                sum(request_latencies) / len(request_latencies), 2
            ) if request_latencies else 0.0,
            agent_trace_count=int(trace_summary["trace_count"]),
            agent_average_latency_ms=float(trace_summary["average_latency_ms"]),
            agent_p95_latency_ms=float(trace_summary["p95_latency_ms"]),
            agent_outcomes=dict(trace_summary["outcomes"]),
        )

    def list_agent_traces(self, *, owner_id: str, limit: int) -> AgentExecutionTraceListResponse:
        items = [
            AgentExecutionTrace.model_validate(item)
            for item in sqlite_state_store.list_agent_traces(owner_id=owner_id, limit=limit)
        ]
        return AgentExecutionTraceListResponse(
            generated_at=datetime.now(timezone.utc),
            total=len(items),
            items=items,
        )

    def prometheus_metrics(self) -> str:
        lines = [
            "# HELP lifesnap_process_uptime_seconds Process uptime in seconds.",
            "# TYPE lifesnap_process_uptime_seconds gauge",
            f"lifesnap_process_uptime_seconds {time.perf_counter() - self._started_at:.3f}",
            "# HELP lifesnap_http_requests_total Total HTTP requests by route and status.",
            "# TYPE lifesnap_http_requests_total counter",
        ]
        with self._lock:
            for (method, path, status_code), count in sorted(self._http_counts.items()):
                lines.append(
                    "lifesnap_http_requests_total"
                    f'{{method="{method}",path="{path}",status="{status_code}"}} {count}'
                )
            lines.extend(
                [
                    "# HELP lifesnap_http_request_duration_seconds HTTP request latency.",
                    "# TYPE lifesnap_http_request_duration_seconds summary",
                ]
            )
            for (method, path), latencies in sorted(self._http_latency.items()):
                total = sum(latencies) / 1000
                labels = f'method="{method}",path="{path}"'
                lines.append(f"lifesnap_http_request_duration_seconds_count{{{labels}}} {len(latencies)}")
                lines.append(f"lifesnap_http_request_duration_seconds_sum{{{labels}}} {total:.6f}")
                lines.append(
                    f"lifesnap_http_request_p95_seconds{{{labels}}} "
                    f"{self._percentile(latencies, 0.95) / 1000:.6f}"
                )
            lines.extend(
                [
                    "# HELP lifesnap_agent_executions_total Agent executions by outcome.",
                    "# TYPE lifesnap_agent_executions_total counter",
                ]
            )
            for (intent, outcome, strategy), count in sorted(self._agent_counts.items()):
                lines.append(
                    "lifesnap_agent_executions_total"
                    f'{{intent="{intent}",outcome="{outcome}",strategy="{strategy}"}} {count}'
                )
            if self._agent_latency:
                lines.extend(
                    [
                        "# HELP lifesnap_agent_execution_p95_seconds Agent execution P95 latency.",
                        "# TYPE lifesnap_agent_execution_p95_seconds gauge",
                        f"lifesnap_agent_execution_p95_seconds {self._percentile(self._agent_latency, 0.95) / 1000:.6f}",
                    ]
                )
        active_alert_counts = {"critical": 0, "warning": 0}
        for alert in sqlite_state_store.list_operational_alerts(include_resolved=False):
            severity = str(alert.get("severity", ""))
            if severity in active_alert_counts:
                active_alert_counts[severity] += 1
        lines.extend(
            [
                "# HELP lifesnap_operational_alerts_active Active application alert states by severity.",
                "# TYPE lifesnap_operational_alerts_active gauge",
                *[
                    f'lifesnap_operational_alerts_active{{severity="{severity}"}} {count}'
                    for severity, count in active_alert_counts.items()
                ],
            ]
        )
        job_metrics = sqlite_state_store.async_job_status_counts()
        job_status_counts = job_metrics["counts"]
        job_statuses = ("queued", "retry_scheduled", "running", "succeeded", "failed", "cancelled")
        lines.extend(
            [
                "# HELP lifesnap_async_jobs Durable asynchronous jobs by current status.",
                "# TYPE lifesnap_async_jobs gauge",
                *[
                    f'lifesnap_async_jobs{{status="{status}"}} {job_status_counts.get(status, 0)}'
                    for status in job_statuses
                ],
            ]
        )
        queue_lag_seconds = 0.0
        oldest_available_at = job_metrics.get("oldest_available_at")
        if oldest_available_at:
            try:
                available_at = datetime.fromisoformat(str(oldest_available_at).replace("Z", "+00:00"))
                queue_lag_seconds = max(
                    0.0,
                    (datetime.now(timezone.utc) - available_at.astimezone(timezone.utc)).total_seconds(),
                )
            except ValueError:
                queue_lag_seconds = 0.0
        lines.extend(
            [
                "# HELP lifesnap_async_job_queue_lag_seconds Age of the oldest dispatchable job.",
                "# TYPE lifesnap_async_job_queue_lag_seconds gauge",
                f"lifesnap_async_job_queue_lag_seconds {queue_lag_seconds:.3f}",
            ]
        )
        with self._lock:
            queue_backend = self._metric_label(self._async_queue_backend)
            queue_configured = self._async_queue_configured
            redis_available = self._async_queue_redis_available
            signal_failures = self._async_queue_signal_failure_count
        redis_availability = 1 if redis_available is True else 0 if redis_available is False else -1
        lines.extend(
            [
                "# HELP lifesnap_async_queue_backend_info Configured asynchronous dispatch backend.",
                "# TYPE lifesnap_async_queue_backend_info gauge",
                f'lifesnap_async_queue_backend_info{{backend="{queue_backend}",configured="{str(queue_configured).lower()}"}} 1',
                "# HELP lifesnap_async_queue_redis_available Redis signal transport health; -1 means not enabled or not yet probed.",
                "# TYPE lifesnap_async_queue_redis_available gauge",
                f"lifesnap_async_queue_redis_available {redis_availability}",
                "# HELP lifesnap_async_queue_signal_failures_total Redis signal publish or consume failures.",
                "# TYPE lifesnap_async_queue_signal_failures_total counter",
                f"lifesnap_async_queue_signal_failures_total {signal_failures}",
            ]
        )
        model_usage = model_invocation_service.summary()
        lines.extend(
            [
                "# HELP lifesnap_model_invocations_total External model calls by provider, model, and outcome.",
                "# TYPE lifesnap_model_invocations_total counter",
                *[
                    f'lifesnap_model_invocations_total{{provider="{self._metric_label(item.provider)}",model="{self._metric_label(item.model)}",outcome="success"}} {item.success_count}'
                    for item in model_usage.records
                ],
                *[
                    f'lifesnap_model_invocations_total{{provider="{self._metric_label(item.provider)}",model="{self._metric_label(item.model)}",outcome="failure"}} {item.failure_count}'
                    for item in model_usage.records
                ],
                "# HELP lifesnap_model_estimated_cost_usd Estimated external model cost in USD.",
                "# TYPE lifesnap_model_estimated_cost_usd counter",
                f"lifesnap_model_estimated_cost_usd {model_usage.estimated_cost_usd:.8f}",
                "# HELP lifesnap_model_circuits_open Open external model circuit breakers.",
                "# TYPE lifesnap_model_circuits_open gauge",
                f"lifesnap_model_circuits_open {model_usage.active_circuit_count}",
            ]
        )
        return "\n".join(lines) + "\n"

    def _agent_outcome(self, response: ChatMessageResponse) -> str:
        statuses = {step.status for step in response.agent_steps}
        if ChatAgentStepStatus.blocked in statuses:
            return "blocked"
        if response.need_user_confirmation:
            return "needs_confirmation"
        return "completed"

    def _normalize_path(self, path: str) -> str:
        return _ID_PATH_SEGMENT.sub("/{id}", path)

    def _percentile(self, values: list[float], percentile: float) -> float:
        ordered = sorted(values)
        index = max(0, round((len(ordered) - 1) * percentile))
        return ordered[index]

    @staticmethod
    def _metric_label(value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def _emit(self, payload: dict[str, Any]) -> None:
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()
        self._logger.info(json.dumps(payload, ensure_ascii=True, separators=(",", ":"), default=str))


observability_service = ObservabilityService()
