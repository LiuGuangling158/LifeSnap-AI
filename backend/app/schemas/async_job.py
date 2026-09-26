from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AsyncJobType(str, Enum):
    agent_quality_evaluation = "agent_quality_evaluation"
    rag_reindex = "rag_reindex"


class AsyncJobStatus(str, Enum):
    queued = "queued"
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
    started_at: datetime | None = None
    completed_at: datetime | None = None
    attempt: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=1, ge=1, le=5)
    result: dict[str, Any] | None = None
    error_code: str | None = Field(default=None, max_length=80)
    error_message: str | None = Field(default=None, max_length=500)

