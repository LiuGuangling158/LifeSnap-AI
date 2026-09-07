from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class AgentKnowledgeHit(BaseModel):
    source_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=80)
    snippet: str = Field(min_length=1, max_length=240)
    score: float = Field(ge=0, le=1)
    tags: list[str] = Field(default_factory=list)


class AgentFunctionCallTrace(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=80)
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: str = Field(min_length=1, max_length=180)
    status: str = Field(default="completed", max_length=40)


class AgentModelTrace(BaseModel):
    provider: str = Field(min_length=1, max_length=80)
    strategy: str = Field(min_length=1, max_length=80)
    runtime_model: str | None = Field(default=None, max_length=160)
    base_model: str | None = Field(default=None, max_length=160)
    fine_tuned_model: str | None = Field(default=None, max_length=160)
    fine_tuning_status: str = Field(min_length=1, max_length=80)
    response_format: str | None = Field(default=None, max_length=80)
    rag_enabled: bool = True
    function_calling_enabled: bool = True


class AgentKnowledgeSource(BaseModel):
    source_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=180)
    document_count: int = Field(ge=0)
    tags: list[str] = Field(default_factory=list)


class AgentFunctionToolCapability(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=180)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    requires_confirmation: bool = False
    side_effect: str = Field(default="read", max_length=40)


class AgentRuntimeProfile(BaseModel):
    rag_enabled: bool = True
    function_calling_enabled: bool = True
    fine_tuning_ready: bool = True
    knowledge_sources: list[AgentKnowledgeSource]
    function_tools: list[AgentFunctionToolCapability]
    model_profile: AgentModelTrace


class AgentFineTuningExample(BaseModel):
    purpose: str = Field(min_length=1, max_length=80)
    messages: list[dict[str, str]]


class AgentFineTuningDatasetResponse(BaseModel):
    generated_at: datetime
    total: int = Field(ge=0)
    examples: list[AgentFineTuningExample]
