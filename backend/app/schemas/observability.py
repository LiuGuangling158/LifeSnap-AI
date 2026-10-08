from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentExecutionTrace(BaseModel):
    trace_id: str = Field(min_length=1, max_length=80)
    occurred_at: datetime
    request_id: str | None = Field(default=None, max_length=128)
    message_id: str = Field(min_length=1, max_length=80)
    intent: str = Field(min_length=1, max_length=80)
    action_type: str = Field(min_length=1, max_length=80)
    model_provider: str = Field(min_length=1, max_length=80)
    model_strategy: str = Field(min_length=1, max_length=120)
    outcome: str = Field(min_length=1, max_length=80)
    latency_ms: float = Field(ge=0)
    function_call_count: int = Field(ge=0)
    knowledge_hit_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentExecutionTraceListResponse(BaseModel):
    generated_at: datetime
    total: int = Field(ge=0)
    items: list[AgentExecutionTrace] = Field(default_factory=list)


class MonitoringSummary(BaseModel):
    generated_at: datetime
    uptime_seconds: float = Field(ge=0)
    request_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    error_rate: float = Field(ge=0)
    average_request_latency_ms: float = Field(ge=0)
    agent_trace_count: int = Field(ge=0)
    agent_average_latency_ms: float = Field(ge=0)
    agent_p95_latency_ms: float = Field(ge=0)
    agent_outcomes: dict[str, int] = Field(default_factory=dict)


class ModelUsageRecord(BaseModel):
    provider: str = Field(min_length=1, max_length=80)
    model: str = Field(min_length=1, max_length=160)
    request_count: int = Field(ge=0)
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    circuit_rejection_count: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_usage_count: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    circuit_open: bool = False
    updated_at: datetime


class ModelUsageSummary(BaseModel):
    generated_at: datetime
    request_count: int = Field(ge=0)
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    retry_count: int = Field(ge=0)
    circuit_rejection_count: int = Field(ge=0)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_usage_count: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    price_configured: bool = False
    active_circuit_count: int = Field(ge=0)
    records: list[ModelUsageRecord] = Field(default_factory=list)


class AlertSeverity(str, Enum):
    warning = "warning"
    critical = "critical"


class AlertStatus(str, Enum):
    active = "active"
    resolved = "resolved"


class OperationalAlert(BaseModel):
    alert_id: str = Field(min_length=1, max_length=80)
    fingerprint: str = Field(min_length=1, max_length=120)
    rule_id: str = Field(min_length=1, max_length=80)
    severity: AlertSeverity
    status: AlertStatus
    title: str = Field(min_length=1, max_length=160)
    summary: str = Field(min_length=1, max_length=320)
    first_seen_at: datetime
    last_seen_at: datetime
    resolved_at: datetime | None = None
    occurrence_count: int = Field(ge=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class OperationalAlertSummary(BaseModel):
    generated_at: datetime
    active_count: int = Field(ge=0)
    critical_count: int = Field(ge=0)
    warning_count: int = Field(ge=0)
    resolved_count: int = Field(ge=0)
    alerts: list[OperationalAlert] = Field(default_factory=list)
