from datetime import datetime
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
