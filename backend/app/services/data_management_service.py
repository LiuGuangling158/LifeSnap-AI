import csv
from io import StringIO
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

    def export_bills_csv(self) -> str:
        return self._write_csv(
            [
                "id",
                "amount",
                "currency",
                "merchant",
                "category",
                "payment_method",
                "transaction_type",
                "paid_at",
                "note",
                "source",
                "created_at",
                "updated_at",
            ],
            [
                {
                    "id": bill.id,
                    "amount": bill.amount,
                    "currency": bill.currency,
                    "merchant": bill.merchant,
                    "category": bill.category,
                    "payment_method": bill.payment_method,
                    "transaction_type": bill.transaction_type,
                    "paid_at": bill.paid_at,
                    "note": bill.note,
                    "source": bill.source,
                    "created_at": bill.created_at,
                    "updated_at": bill.updated_at,
                }
                for bill in bill_store.all()
            ],
        )

    def export_tasks_csv(self) -> str:
        return self._write_csv(
            [
                "id",
                "title",
                "description",
                "category",
                "task_type",
                "status",
                "due_at",
                "remind_at",
                "priority",
                "source",
                "created_at",
                "updated_at",
                "completed_at",
            ],
            [
                {
                    "id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "category": task.category,
                    "task_type": task.task_type,
                    "status": task.status,
                    "due_at": task.due_at,
                    "remind_at": task.remind_at,
                    "priority": task.priority,
                    "source": task.source,
                    "created_at": task.created_at,
                    "updated_at": task.updated_at,
                    "completed_at": task.completed_at,
                }
                for task in task_store.all()
            ],
        )

    def export_attachments_csv(self) -> str:
        return self._write_csv(
            [
                "id",
                "filename",
                "content_type",
                "file_size",
                "checksum",
                "duplicate_of",
                "source",
                "storage_type",
                "retention_policy",
                "original_saved",
                "has_ocr_text",
                "created_at",
                "updated_at",
            ],
            [
                {
                    "id": attachment.id,
                    "filename": attachment.filename,
                    "content_type": attachment.content_type,
                    "file_size": attachment.file_size,
                    "checksum": attachment.checksum,
                    "duplicate_of": attachment.duplicate_of,
                    "source": attachment.source,
                    "storage_type": attachment.storage_type,
                    "retention_policy": attachment.retention_policy,
                    "original_saved": attachment.original_saved,
                    "has_ocr_text": attachment.ocr_text is not None,
                    "created_at": attachment.created_at,
                    "updated_at": attachment.updated_at,
                }
                for attachment in attachment_store.all()
            ],
        )

    def export_bill_candidates_csv(self) -> str:
        return self._write_csv(
            [
                "candidate_id",
                "intent",
                "confidence",
                "amount",
                "currency",
                "merchant",
                "category",
                "payment_method",
                "paid_at",
                "transaction_type",
                "note",
                "source",
                "amount_confidence",
                "merchant_confidence",
                "category_confidence",
                "payment_method_confidence",
                "paid_at_confidence",
                "warnings",
                "need_user_confirmation",
            ],
            [
                {
                    "candidate_id": candidate.candidate_id,
                    "intent": candidate.intent,
                    "confidence": candidate.confidence,
                    "amount": candidate.data.amount,
                    "currency": candidate.data.currency,
                    "merchant": candidate.data.merchant,
                    "category": candidate.data.category,
                    "payment_method": candidate.data.payment_method,
                    "paid_at": candidate.data.paid_at,
                    "transaction_type": candidate.data.transaction_type,
                    "note": candidate.data.note,
                    "source": candidate.data.source,
                    "amount_confidence": candidate.field_confidence.get("amount"),
                    "merchant_confidence": candidate.field_confidence.get("merchant"),
                    "category_confidence": candidate.field_confidence.get("category"),
                    "payment_method_confidence": candidate.field_confidence.get(
                        "payment_method"
                    ),
                    "paid_at_confidence": candidate.field_confidence.get("paid_at"),
                    "warnings": candidate.warnings,
                    "need_user_confirmation": candidate.need_user_confirmation,
                }
                for candidate in bill_candidate_store.all()
            ],
        )

    def export_task_candidates_csv(self) -> str:
        return self._write_csv(
            [
                "candidate_id",
                "intent",
                "confidence",
                "title",
                "description",
                "category",
                "task_type",
                "due_at",
                "remind_at",
                "priority",
                "source",
                "title_confidence",
                "category_confidence",
                "task_type_confidence",
                "due_at_confidence",
                "remind_at_confidence",
                "priority_confidence",
                "warnings",
                "need_user_confirmation",
            ],
            [
                {
                    "candidate_id": candidate.candidate_id,
                    "intent": candidate.intent,
                    "confidence": candidate.confidence,
                    "title": candidate.data.title,
                    "description": candidate.data.description,
                    "category": candidate.data.category,
                    "task_type": candidate.data.task_type,
                    "due_at": candidate.data.due_at,
                    "remind_at": candidate.data.remind_at,
                    "priority": candidate.data.priority,
                    "source": candidate.data.source,
                    "title_confidence": candidate.field_confidence.get("title"),
                    "category_confidence": candidate.field_confidence.get("category"),
                    "task_type_confidence": candidate.field_confidence.get("task_type"),
                    "due_at_confidence": candidate.field_confidence.get("due_at"),
                    "remind_at_confidence": candidate.field_confidence.get("remind_at"),
                    "priority_confidence": candidate.field_confidence.get("priority"),
                    "warnings": candidate.warnings,
                    "need_user_confirmation": candidate.need_user_confirmation,
                }
                for candidate in task_candidate_store.all()
            ],
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

    def _write_csv(self, fieldnames: list[str], rows: list[dict[str, object]]) -> str:
        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    fieldname: self._csv_value(row.get(fieldname))
                    for fieldname in fieldnames
                }
            )
        return output.getvalue()

    def _csv_value(self, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, list):
            return ";".join(str(item) for item in value)
        if hasattr(value, "value"):
            return str(value.value)
        return str(value)


data_management_service = DataManagementService()
