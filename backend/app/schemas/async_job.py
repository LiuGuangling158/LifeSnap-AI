from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AsyncJobType(str, Enum):
    agent_quality_evaluation = "agent_quality_evaluation"
    agent_quality_evaluation_live = "agent_quality_evaluation_live"
    rag_reindex = "rag_reindex"


class AsyncJobStatus(str, Enum):
    queued = "queued"
    retry_scheduled = "retry_scheduled"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    cancelled = "cancelled"


class AsyncJobRead(BaseModel):
    job_id: UUID
    job_type: AsyncJobType
    status: AsyncJobStatus
    created_at: datetime
    updated_at: datetime
    available_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    lease_expires_at: datetime | None = None
    attempt: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=1, ge=1, le=5)
    idempotency_key: str | None = Field(default=None, max_length=128)
    result: dict[str, Any] | None = None
    error_code: str | None = Field(default=None, max_length=80)
    error_message: str | None = Field(default=None, max_length=500)


class AsyncJobEventRead(BaseModel):
    event_id: UUID
    job_id: UUID
    occurred_at: datetime
    event_type: str = Field(min_length=1, max_length=80)
    status: AsyncJobStatus
    attempt: int = Field(ge=0)
    error_code: str | None = Field(default=None, max_length=80)

