from datetime import datetime, timezone

from app.schemas.settings import (
    DataClearRequest,
    DataClearResponse,
    DataExportResponse,
    LocalDataSummary,
)
from app.services.attachment_store import attachment_store
from app.services.bill_candidate_store import bill_candidate_store
from app.services.bill_store import bill_store
from app.services.idempotency_store import idempotency_store
from app.services.settings_store import settings_store
from app.services.task_candidate_store import task_candidate_store
from app.services.task_store import task_store


class DataManagementService:
    def summary(self) -> LocalDataSummary:
        return LocalDataSummary(
            bill_count=len(bill_store.all()),
            task_count=len(task_store.all()),
            attachment_count=len(attachment_store.all()),
            bill_candidate_count=len(bill_candidate_store.all()),
            task_candidate_count=len(task_candidate_store.all()),
        )

    def export(self) -> DataExportResponse:
        return DataExportResponse(
            generated_at=datetime.now(timezone.utc),
            privacy_settings=settings_store.get_privacy_settings(),
            bills=bill_store.all(),
            tasks=task_store.all(),
            attachments=attachment_store.all(),
            bill_candidates=bill_candidate_store.all(),
            task_candidates=task_candidate_store.all(),
        )

    def clear(self, payload: DataClearRequest) -> DataClearResponse:
        before = self.summary()

        if payload.include_bills:
            bill_store.clear()
        if payload.include_tasks:
            task_store.clear()
        if payload.include_attachments:
            attachment_store.clear()
        if payload.include_candidates:
            bill_candidate_store.clear()
            task_candidate_store.clear()
        if payload.reset_privacy_settings:
            settings_store.reset_privacy_settings()
        if (
            payload.include_bills
            or payload.include_tasks
            or payload.include_attachments
            or payload.include_candidates
            or payload.reset_privacy_settings
        ):
            idempotency_store.clear()

        return DataClearResponse(
            cleared_at=datetime.now(timezone.utc),
            before=before,
            after=self.summary(),
            privacy_settings=settings_store.get_privacy_settings(),
        )


data_management_service = DataManagementService()
