from datetime import datetime

from pydantic import BaseModel

from app.schemas.agent import ParseBillResponse, ParseTaskResponse
from app.schemas.attachment import AttachmentRead, RetentionPolicy
from app.schemas.bill import BillRead
from app.schemas.task import TaskRead


class PrivacySettings(BaseModel):
    local_only_mode: bool = True
    allow_ai_text_processing: bool = True
    save_original_attachments_by_default: bool = False
    attachment_retention_policy: RetentionPolicy = RetentionPolicy.delete_after_recognition
    keep_ocr_text: bool = True
    updated_at: datetime


class PrivacySettingsUpdate(BaseModel):
    local_only_mode: bool | None = None
    allow_ai_text_processing: bool | None = None
    save_original_attachments_by_default: bool | None = None
    keep_ocr_text: bool | None = None


class LocalDataSummary(BaseModel):
    bill_count: int
    task_count: int
    attachment_count: int
    bill_candidate_count: int
    task_candidate_count: int


class DataExportResponse(BaseModel):
    generated_at: datetime
    privacy_settings: PrivacySettings
    bills: list[BillRead]
    tasks: list[TaskRead]
    attachments: list[AttachmentRead]
    bill_candidates: list[ParseBillResponse]
    task_candidates: list[ParseTaskResponse]


class DataClearRequest(BaseModel):
    confirm: bool = False
    include_bills: bool = True
    include_tasks: bool = True
    include_attachments: bool = True
    include_candidates: bool = True
    reset_privacy_settings: bool = False


class DataClearResponse(BaseModel):
    cleared_at: datetime
    before: LocalDataSummary
    after: LocalDataSummary
    privacy_settings: PrivacySettings


class DemoDataSeedRequest(BaseModel):
    confirm: bool = False
    reset_existing: bool = False
    include_attachment: bool = True
    include_candidates: bool = True


class DemoDataSeedResponse(BaseModel):
    seeded_at: datetime
    before: LocalDataSummary
    after: LocalDataSummary
    created_bills: list[BillRead]
    created_tasks: list[TaskRead]
    created_attachment: AttachmentRead | None = None
    created_bill_candidates: list[ParseBillResponse]
    created_task_candidates: list[ParseTaskResponse]
