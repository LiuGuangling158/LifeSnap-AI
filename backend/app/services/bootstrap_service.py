from datetime import datetime, timezone

from app.core.config import settings
from app.schemas.bill import BillSource, TransactionType
from app.schemas.bootstrap import AppBootstrapResponse, AppCapabilities
from app.schemas.diary import DiaryMood, DiarySource
from app.schemas.task import TaskSource
from app.services.attachment_store import attachment_store
from app.services.dashboard_service import dashboard_service
from app.services.data_management_service import data_management_service
from app.services.settings_store import settings_store


class BootstrapService:
    def capabilities(self) -> AppCapabilities:
        return AppCapabilities(
            app_name=settings.app_name,
            app_version=settings.app_version,
            api_status="ok",
            generated_at=datetime.now(timezone.utc),
            storage_backend="local_json_for_app_state",
            ocr_provider=settings.ocr_provider_name,
            ai_text_parser=settings.ai_parser_provider_name,
            max_attachment_file_size_bytes=attachment_store.max_file_size,
            supported_attachment_content_types=sorted(
                attachment_store.supported_content_types
            ),
            supported_bill_sources=[source.value for source in BillSource],
            supported_task_sources=[source.value for source in TaskSource],
            supported_diary_sources=[source.value for source in DiarySource],
            supported_diary_moods=[mood.value for mood in DiaryMood],
            supported_transaction_types=[
                transaction_type.value for transaction_type in TransactionType
            ],
            idempotency_supported_endpoints=[
                "POST /bills",
                "POST /tasks",
                "POST /diaries",
                "POST /diaries/{diary_id}/restore",
                "POST /tasks/{task_id}/complete",
                "POST /tasks/{task_id}/snooze",
                "POST /agent/bill-candidates/{candidate_id}/confirm",
                "POST /agent/task-candidates/{candidate_id}/confirm",
                "POST /chat/confirm-action",
                "POST /chat/discard-action",
                "POST /data/seed-demo",
            ],
            feature_flags={
                "manual_bills": True,
                "bill_statistics": True,
                "attachments": True,
                "stored_text_ocr_fallback": True,
                "bill_candidates": True,
                "task_candidates": True,
                "chat_actions": True,
                "external_chat_intent_routing": settings.real_ai_parser_enabled,
                "dashboard_bootstrap": True,
                "diaries": True,
                "demo_data_seed": True,
                "local_snapshot_persistence": True,
                "bill_json_persistence": True,
                "task_json_persistence": True,
                "diary_json_persistence": True,
                "settings_json_persistence": True,
                "candidate_json_persistence": True,
                "attachment_json_persistence": True,
                "original_attachment_file_persistence": True,
                "audit_json_persistence": True,
                "idempotency_json_persistence": True,
                "real_ocr_engine": settings.real_ocr_enabled,
                "real_llm_parser": settings.real_ai_parser_enabled,
                "persistent_database": False,
                "user_accounts": False,
            },
            known_limitations=[
                "Bills, tasks and diary entries are persisted to local JSON files under backend/data.",
                "Privacy settings are persisted to a local JSON file under backend/data.",
                "Bill and task candidates are persisted to local JSON files under backend/data.",
                "Attachment metadata and retained original files are persisted under backend/data.",
                "Idempotency keys are persisted to local JSON for retry protection across restarts.",
                "Snapshot export includes attachment metadata but not retained original file bytes.",
                (
                    "OCR uses the configured external HTTP provider when LIFESNAP_OCR_ENDPOINT is set; "
                    "otherwise it falls back to stored text and manual entry."
                ),
                (
                    "AI parsing uses the configured external HTTP provider when "
                    "LIFESNAP_AI_PARSE_ENDPOINT is set; otherwise it falls back to rule-based parsing. "
                    "Chat intent routing uses the same provider with kind=chat_intent."
                ),
                "Local JSON storage is intended for single-user local use, not concurrent multi-user production traffic.",
                "Authentication and multi-user accounts are not implemented yet.",
            ],
        )

    def bootstrap(
        self,
        year: int | None = None,
        month: int | None = None,
        upcoming_days: int = 7,
        today_limit: int = 10,
        reminder_limit: int = 10,
        recent_bill_limit: int = 5,
        candidate_limit: int = 5,
    ) -> AppBootstrapResponse:
        return AppBootstrapResponse(
            generated_at=datetime.now(timezone.utc),
            capabilities=self.capabilities(),
            privacy_settings=settings_store.get_privacy_settings(),
            data_summary=data_management_service.summary(),
            dashboard=dashboard_service.summary(
                year=year,
                month=month,
                upcoming_days=upcoming_days,
                today_limit=today_limit,
                reminder_limit=reminder_limit,
                recent_bill_limit=recent_bill_limit,
                candidate_limit=candidate_limit,
            ),
        )


bootstrap_service = BootstrapService()
