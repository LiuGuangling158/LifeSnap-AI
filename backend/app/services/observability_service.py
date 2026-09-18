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


_ID_PATH_SEGMENT = re.compile(r"/(?:[0-9a-f]{32}|[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12})(?=/|$)", re.I)


class ObservabilityService:
    def __init__(self) -> None:
        self._started_at = time.perf_counter()
        self._lock = threading.RLock()
        self._http_counts: dict[tuple[str, str, int], int] = {}
        self._http_latency: dict[tuple[str, str], list[float]] = {}
        self._agent_counts: dict[tuple[str, str, str], int] = {}
        self._agent_latency: list[float] = []
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

    def _emit(self, payload: dict[str, Any]) -> None:
        payload["timestamp"] = datetime.now(timezone.utc).isoformat()
        self._logger.info(json.dumps(payload, ensure_ascii=True, separators=(",", ":"), default=str))


observability_service = ObservabilityService()
