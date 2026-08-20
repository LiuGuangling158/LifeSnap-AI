from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.settings import LocalDataSummary


class DiagnosticSeverity(str, Enum):
    info = "info"
    warning = "warning"
    action_required = "action_required"


class DiagnosticIssue(BaseModel):
    code: str
    severity: DiagnosticSeverity
    message: str
    entity_type: str | None = None
    entity_id: str | None = None
    related_entity_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DataQualityDiagnostics(BaseModel):
    generated_at: datetime
    status: str
    data_summary: LocalDataSummary
    issue_count: int
    info_count: int
    warning_count: int
    action_required_count: int
    issue_limit: int
    truncated: bool
    issues: list[DiagnosticIssue]


class IntegrationCheck(BaseModel):
    name: str
    provider: str
    status: str
    configured: bool
    ready: bool
    endpoint_configured: bool
    api_key_configured: bool
    timeout_seconds: float | None = None
    capabilities: list[str] = Field(default_factory=list)
    privacy_blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    next_action: str | None = None


class IntegrationDiagnostics(BaseModel):
    generated_at: datetime
    status: str
    check_count: int
    ready_count: int
    blocked_count: int
    fallback_count: int
    checks: list[IntegrationCheck]
