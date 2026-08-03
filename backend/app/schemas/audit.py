from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AuditEvent(BaseModel):
    event_id: UUID
    occurred_at: datetime
    action: str
    entity_type: str
    entity_id: str | None = None
    request_id: str | None = None
    method: str | None = None
    path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AuditEventListResponse(BaseModel):
    items: list[AuditEvent]
    total: int
    page: int
    page_size: int
    total_pages: int
