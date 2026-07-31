from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class AttachmentSource(str, Enum):
    screenshot = "screenshot"
    album = "album"
    upload = "upload"


class RetentionPolicy(str, Enum):
    delete_after_recognition = "delete_after_recognition"
    keep_until_user_delete = "keep_until_user_delete"


class AttachmentRead(BaseModel):
    id: UUID
    filename: str
    content_type: str
    file_size: int
    checksum: str
    duplicate_of: UUID | None = None
    source: AttachmentSource
    storage_type: str = "memory"
    retention_policy: RetentionPolicy
    original_saved: bool
    ocr_text: str | None = None
    created_at: datetime
    updated_at: datetime


class AttachmentOcrTextUpdate(BaseModel):
    ocr_text: str = Field(min_length=1, max_length=10000)


class AttachmentDuplicateResponse(BaseModel):
    attachment_id: UUID
    checksum: str
    is_duplicate: bool
    duplicate_of: UUID | None = None
    duplicate_count: int
    matches: list[AttachmentRead]
