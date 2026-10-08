from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AgentReleaseState(str, Enum):
    candidate = "candidate"
    active = "active"
    superseded = "superseded"


class AgentReleaseSnapshot(BaseModel):
    app_version: str = Field(min_length=1, max_length=80)
    runtime_fingerprint: str = Field(min_length=16, max_length=128)
    model_provider: str = Field(min_length=1, max_length=80)
    model_strategy: str = Field(min_length=1, max_length=120)
    runtime_model: str | None = Field(default=None, max_length=160)
    knowledge_version_id: str | None = Field(default=None, max_length=80)
    quality_run_id: str = Field(min_length=1, max_length=80)
    quality_dataset_version: str = Field(min_length=1, max_length=40)
    quality_pass_rate: float = Field(ge=0, le=1)
    rag_dataset_version: str | None = Field(default=None, max_length=40)
    rag_recall_at_k: float | None = Field(default=None, ge=0, le=1)
    rag_citation_accuracy: float | None = Field(default=None, ge=0, le=1)
    rag_abstention_accuracy: float | None = Field(default=None, ge=0, le=1)


class AgentRelease(BaseModel):
    release_id: str = Field(min_length=1, max_length=80)
    label: str = Field(min_length=1, max_length=80)
    note: str | None = Field(default=None, max_length=240)
    state: AgentReleaseState
    created_at: datetime
    activated_at: datetime | None = None
    superseded_at: datetime | None = None
    snapshot: AgentReleaseSnapshot


class AgentReleaseCreateRequest(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    note: str | None = Field(default=None, max_length=240)


class AgentReleaseListResponse(BaseModel):
    generated_at: datetime
    active_release_id: str | None = None
    releases: list[AgentRelease] = Field(default_factory=list)
