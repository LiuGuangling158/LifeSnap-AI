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
    chunk_id: str | None = Field(default=None, max_length=120)
    retrieval_method: str = Field(default="bm25", max_length=40)
    lexical_score: float | None = Field(default=None, ge=0, le=1)
    semantic_score: float | None = Field(default=None, ge=0, le=1)


class AgentRagProfile(BaseModel):
    strategy: str = Field(min_length=1, max_length=80)
    embedding_configured: bool
    embedding_ready: bool
    privacy_allows_external_embedding: bool
    embedding_model: str | None = Field(default=None, max_length=160)
    chunk_count: int = Field(ge=0)
    indexed_chunk_count: int = Field(ge=0)
    last_indexed_at: datetime | None = None
    last_error: str | None = Field(default=None, max_length=160)


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
    reasoning_effort: str | None = Field(default=None, max_length=40)
    external_model_configured: bool = False
    external_model_ready: bool = False
    local_fallback_active: bool = True
    endpoint_configured: bool = False
    api_key_configured: bool = False
    privacy_blockers: list[str] = Field(default_factory=list)
    credential_blockers: list[str] = Field(default_factory=list)
    next_action: str | None = Field(default=None, max_length=220)
    function_calling_mode: str = Field(default="local_trace_only", max_length=80)
    rag_enabled: bool = True
    function_calling_enabled: bool = True


class AgentKnowledgeSource(BaseModel):
    source_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=80)
    description: str = Field(min_length=1, max_length=180)
    document_count: int = Field(ge=0)
    tags: list[str] = Field(default_factory=list)


class AgentKnowledgeDocument(BaseModel):
    source_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1, max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=8)
    keywords: list[str] = Field(default_factory=list, max_length=24)
    source: str = Field(default="builtin", max_length=40)
    enabled: bool = True
    updated_at: datetime | None = None


class AgentKnowledgeDocumentInput(BaseModel):
    source_id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=80)
    content: str = Field(min_length=1, max_length=2000)
    tags: list[str] = Field(default_factory=list, max_length=8)
    keywords: list[str] = Field(default_factory=list, max_length=24)
    enabled: bool = True


class AgentKnowledgeVersionSummary(BaseModel):
    version_id: str = Field(min_length=1, max_length=80)
    action: str = Field(min_length=1, max_length=40)
    created_at: datetime
    admin_count: int = Field(ge=0)
    active_count: int = Field(ge=0)
    document_titles: list[str] = Field(default_factory=list, max_length=8)


class AgentKnowledgeBaseResponse(BaseModel):
    generated_at: datetime
    total: int = Field(ge=0)
    builtin_count: int = Field(ge=0)
    admin_count: int = Field(ge=0)
    active_count: int = Field(ge=0)
    documents: list[AgentKnowledgeDocument]
    versions: list[AgentKnowledgeVersionSummary] = Field(default_factory=list)
    retrieval: AgentRagProfile


class AgentKnowledgeBaseUpdateRequest(BaseModel):
    documents: list[AgentKnowledgeDocumentInput] = Field(default_factory=list, max_length=50)


class AgentKnowledgeBaseResetRequest(BaseModel):
    confirm: bool = False


class AgentKnowledgeRollbackRequest(BaseModel):
    version_id: str = Field(min_length=1, max_length=80)


class AgentAdminKeyRevealResponse(BaseModel):
    available: bool
    admin_key: str | None = Field(default=None, max_length=240)
    detail: str = Field(min_length=1, max_length=180)


class AgentAdminSessionCreateRequest(BaseModel):
    admin_key: str = Field(min_length=1, max_length=240)


class AgentAdminSessionResponse(BaseModel):
    authenticated: bool = True
    token: str = Field(min_length=1)
    token_type: str = Field(default="Bearer", max_length=20)
    role: str = Field(default="admin", max_length=40)
    expires_at: datetime
    expires_in_seconds: int = Field(ge=1)


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
    rag_profile: AgentRagProfile
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
