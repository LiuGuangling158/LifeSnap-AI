from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class OcrRecognitionStatus(str, Enum):
    recognized = "recognized"
    manual_required = "manual_required"


class OcrRecognizeRequest(BaseModel):
    attachment_id: UUID


class OcrRecognizeResponse(BaseModel):
    attachment_id: UUID
    status: OcrRecognitionStatus
    text: str | None = None
    confidence: float = Field(ge=0, le=1)
    provider: str = "stored_text_stub"
    warnings: list[str] = []
    manual_entry_required: bool
    recognized_at: datetime
