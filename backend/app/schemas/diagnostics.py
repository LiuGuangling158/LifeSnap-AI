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
