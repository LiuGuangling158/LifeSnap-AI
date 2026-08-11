from datetime import datetime

from pydantic import BaseModel

from app.schemas.dashboard import DashboardSummary
from app.schemas.settings import LocalDataSummary, PrivacySettings


class AppCapabilities(BaseModel):
    app_name: str
    app_version: str
    api_status: str
    generated_at: datetime
    storage_backend: str
    ocr_provider: str
    ai_text_parser: str
    max_attachment_file_size_bytes: int
    supported_attachment_content_types: list[str]
    supported_bill_sources: list[str]
    supported_task_sources: list[str]
    supported_diary_sources: list[str]
    supported_diary_moods: list[str]
    supported_transaction_types: list[str]
    idempotency_supported_endpoints: list[str]
    feature_flags: dict[str, bool]
    known_limitations: list[str]


class AppBootstrapResponse(BaseModel):
    generated_at: datetime
    capabilities: AppCapabilities
    privacy_settings: PrivacySettings
    data_summary: LocalDataSummary
    dashboard: DashboardSummary
