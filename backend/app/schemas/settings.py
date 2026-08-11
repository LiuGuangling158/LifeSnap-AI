from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.agent import ParseBillResponse, ParseTaskResponse
from app.schemas.attachment import AttachmentRead, RetentionPolicy
from app.schemas.bill import BillRead
from app.schemas.diary import DiaryRead
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
    diary_count: int = 0
    attachment_count: int
    bill_candidate_count: int
    task_candidate_count: int
    deleted_bill_count: int = 0
    deleted_task_count: int = 0
    deleted_diary_count: int = 0


class DataExportResponse(BaseModel):
    generated_at: datetime
    privacy_settings: PrivacySettings
    bills: list[BillRead]
    tasks: list[TaskRead]
    diaries: list[DiaryRead] = Field(default_factory=list)
    attachments: list[AttachmentRead]
    bill_candidates: list[ParseBillResponse]
    task_candidates: list[ParseTaskResponse]


class DataImportRequest(BaseModel):
    confirm: bool = False
    dry_run: bool = False
    reset_existing: bool = False
    include_bills: bool = True
    include_tasks: bool = True
    include_diaries: bool = True
    include_attachments: bool = True
    include_candidates: bool = True
    import_privacy_settings: bool = True
    snapshot: DataExportResponse


class DataImportResponse(BaseModel):
    imported_at: datetime
    dry_run: bool
    reset_existing: bool
    before: LocalDataSummary
    after: LocalDataSummary
    imported_bill_count: int
    imported_task_count: int
    imported_diary_count: int = 0
    imported_attachment_count: int
    imported_bill_candidate_count: int
    imported_task_candidate_count: int
    privacy_settings: PrivacySettings


class DataSnapshotStatus(BaseModel):
    snapshot_path: str
    exists: bool
    file_size_bytes: int | None = None
    updated_at: datetime | None = None
    snapshot_data_summary: LocalDataSummary | None = None
    snapshot_error: str | None = None
    current_data_summary: LocalDataSummary


class DataSnapshotSaveResponse(DataSnapshotStatus):
    saved_at: datetime


class DataSnapshotLoadRequest(BaseModel):
    confirm: bool = False
    dry_run: bool = False
    reset_existing: bool = True
    include_bills: bool = True
    include_tasks: bool = True
    include_diaries: bool = True
    include_attachments: bool = True
    include_candidates: bool = True
    import_privacy_settings: bool = True


class DataSnapshotLoadResponse(BaseModel):
    loaded_at: datetime
    snapshot_path: str
    import_result: DataImportResponse


class DataSnapshotDeleteRequest(BaseModel):
    confirm: bool = False


class DataSnapshotDeleteResponse(BaseModel):
    deleted_at: datetime
    snapshot_path: str
    deleted: bool
    current_data_summary: LocalDataSummary


class DataClearRequest(BaseModel):
    confirm: bool = False
    include_bills: bool = True
    include_tasks: bool = True
    include_diaries: bool = True
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
