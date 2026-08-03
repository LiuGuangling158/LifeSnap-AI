from datetime import datetime, timezone

from app.core.config import settings
from app.schemas.bill import BillSource, TransactionType
from app.schemas.bootstrap import AppBootstrapResponse, AppCapabilities
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
            storage_backend="in_memory",
            ocr_provider="stored_text_stub",
            ai_text_parser="rule_based",
            max_attachment_file_size_bytes=attachment_store.max_file_size,
            supported_attachment_content_types=sorted(
                attachment_store.supported_content_types
            ),
            supported_bill_sources=[source.value for source in BillSource],
            supported_task_sources=[source.value for source in TaskSource],
            supported_transaction_types=[
                transaction_type.value for transaction_type in TransactionType
            ],
            idempotency_supported_endpoints=[
                "POST /bills",
                "POST /tasks",
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
                "dashboard_bootstrap": True,
                "demo_data_seed": True,
                "local_snapshot_persistence": True,
                "real_ocr_engine": False,
                "real_llm_parser": False,
                "persistent_database": False,
                "user_accounts": False,
            },
            known_limitations=[
                "Data is stored in process memory, with manual local snapshot save/load support.",
                "OCR uses stored text fallback and manual entry, not a real OCR engine.",
                "AI parsing is rule-based and returns candidates for user confirmation.",
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
