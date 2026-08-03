from __future__ import annotations

from datetime import datetime, timezone

from app.schemas.agent import ParseBillResponse, ParseTaskResponse
from app.schemas.attachment import AttachmentRead
from app.schemas.bill import BillRead
from app.schemas.diagnostics import (
    DataQualityDiagnostics,
    DiagnosticIssue,
    DiagnosticSeverity,
)
from app.schemas.task import TaskRead, TaskStatus, TaskType
from app.services.attachment_store import attachment_store
from app.services.bill_candidate_store import bill_candidate_store
from app.services.bill_store import bill_store
from app.services.data_management_service import data_management_service
from app.services.settings_store import settings_store
from app.services.task_candidate_store import task_candidate_store
from app.services.task_store import task_store


class DiagnosticsService:
    def data_quality(
        self,
        *,
        duplicate_time_window_minutes: int = 10,
        issue_limit: int = 50,
    ) -> DataQualityDiagnostics:
        now = datetime.now(timezone.utc)
        issues: list[DiagnosticIssue] = []
        issues.extend(self._privacy_issues())
        issues.extend(self._attachment_issues())
        issues.extend(self._candidate_issues())
        issues.extend(self._duplicate_bill_issues(duplicate_time_window_minutes))
        issues.extend(self._task_issues(now))
        issues.extend(self._recycle_bin_issues())

        sorted_issues = sorted(issues, key=self._issue_sort_key)
        limited_issues = sorted_issues[:issue_limit]
        info_count = self._severity_count(issues, DiagnosticSeverity.info)
        warning_count = self._severity_count(issues, DiagnosticSeverity.warning)
        action_required_count = self._severity_count(
            issues,
            DiagnosticSeverity.action_required,
        )
        return DataQualityDiagnostics(
            generated_at=now,
            status=self._status(warning_count, action_required_count),
            data_summary=data_management_service.summary(),
            issue_count=len(issues),
            info_count=info_count,
            warning_count=warning_count,
            action_required_count=action_required_count,
            issue_limit=issue_limit,
            truncated=len(issues) > issue_limit,
            issues=limited_issues,
        )

    def _privacy_issues(self) -> list[DiagnosticIssue]:
        privacy_settings = settings_store.get_privacy_settings()
        issues: list[DiagnosticIssue] = []
        if not privacy_settings.allow_ai_text_processing:
            issues.append(
                DiagnosticIssue(
                    code="ai_text_processing_disabled",
                    severity=DiagnosticSeverity.warning,
                    message="AI text processing is disabled, so parsing from chat or OCR text will be limited.",
                    entity_type="settings",
                )
            )
        if privacy_settings.save_original_attachments_by_default:
            issues.append(
                DiagnosticIssue(
                    code="original_attachment_retention_enabled",
                    severity=DiagnosticSeverity.info,
                    message="Original attachments are kept by default. This may increase local storage and privacy exposure.",
                    entity_type="settings",
                )
            )
        return issues

    def _attachment_issues(self) -> list[DiagnosticIssue]:
        attachments = attachment_store.all()
        issues: list[DiagnosticIssue] = []
        for attachment in attachments:
            if attachment.ocr_text is None:
                issues.append(self._attachment_missing_ocr_issue(attachment))

        checksum_groups: dict[str, list[AttachmentRead]] = {}
        for attachment in attachments:
            checksum_groups.setdefault(attachment.checksum, []).append(attachment)
        for matches in checksum_groups.values():
            if len(matches) < 2:
                continue
            first = sorted(matches, key=lambda item: item.created_at)[0]
            issues.append(
                DiagnosticIssue(
                    code="duplicate_attachment",
                    severity=DiagnosticSeverity.info,
                    message="Multiple attachments share the same checksum.",
                    entity_type="attachment",
                    entity_id=str(first.id),
                    related_entity_ids=[str(item.id) for item in matches[1:]],
                    metadata={
                        "duplicate_count": len(matches) - 1,
                        "filename": first.filename,
                    },
                )
            )
        return issues

    def _attachment_missing_ocr_issue(self, attachment: AttachmentRead) -> DiagnosticIssue:
        return DiagnosticIssue(
            code="attachment_missing_ocr_text",
            severity=DiagnosticSeverity.warning,
            message="Attachment has no OCR text yet. It may need recognition or manual entry.",
            entity_type="attachment",
            entity_id=str(attachment.id),
            metadata={
                "filename": attachment.filename,
                "content_type": attachment.content_type,
                "source": attachment.source,
            },
        )

    def _candidate_issues(self) -> list[DiagnosticIssue]:
        issues: list[DiagnosticIssue] = []
        bill_candidates = bill_candidate_store.all()
        task_candidates = task_candidate_store.all()
        if bill_candidates:
            issues.append(
                DiagnosticIssue(
                    code="pending_bill_candidates",
                    severity=DiagnosticSeverity.info,
                    message="There are bill candidates waiting for user confirmation.",
                    entity_type="bill_candidate",
                    related_entity_ids=[
                        str(candidate.candidate_id) for candidate in bill_candidates[:10]
                    ],
                    metadata={"candidate_count": len(bill_candidates)},
                )
            )
        if task_candidates:
            issues.append(
                DiagnosticIssue(
                    code="pending_task_candidates",
                    severity=DiagnosticSeverity.info,
                    message="There are task candidates waiting for user confirmation.",
                    entity_type="task_candidate",
                    related_entity_ids=[
                        str(candidate.candidate_id) for candidate in task_candidates[:10]
                    ],
                    metadata={"candidate_count": len(task_candidates)},
                )
            )
        issues.extend(self._candidate_field_issues(bill_candidates, task_candidates))
        return issues

    def _candidate_field_issues(
        self,
        bill_candidates: list[ParseBillResponse],
        task_candidates: list[ParseTaskResponse],
    ) -> list[DiagnosticIssue]:
        issues: list[DiagnosticIssue] = []
        for candidate in bill_candidates:
            if bill_candidate_store.is_confirmable(candidate):
                continue
            issues.append(
                DiagnosticIssue(
                    code="bill_candidate_missing_required_fields",
                    severity=DiagnosticSeverity.action_required,
                    message="Bill candidate is missing amount or merchant and cannot be confirmed yet.",
                    entity_type="bill_candidate",
                    entity_id=str(candidate.candidate_id),
                    metadata={"warnings": candidate.warnings},
                )
            )
        for candidate in task_candidates:
            if task_candidate_store.is_confirmable(candidate):
                continue
            issues.append(
                DiagnosticIssue(
                    code="task_candidate_missing_required_fields",
                    severity=DiagnosticSeverity.action_required,
                    message="Task candidate is missing title or reminder time and cannot be confirmed yet.",
                    entity_type="task_candidate",
                    entity_id=str(candidate.candidate_id),
                    metadata={"warnings": candidate.warnings},
                )
            )
        return issues

    def _duplicate_bill_issues(self, time_window_minutes: int) -> list[DiagnosticIssue]:
        bills = sorted(bill_store.all(), key=lambda bill: bill.paid_at)
        issues: list[DiagnosticIssue] = []
        for index, bill in enumerate(bills):
            for other in bills[index + 1 :]:
                if not self._is_possible_duplicate_bill(
                    bill,
                    other,
                    time_window_minutes,
                ):
                    continue
                issues.append(
                    DiagnosticIssue(
                        code="possible_duplicate_bill",
                        severity=DiagnosticSeverity.warning,
                        message="Two bills have the same merchant, amount, type, and nearby paid time.",
                        entity_type="bill",
                        entity_id=str(bill.id),
                        related_entity_ids=[str(other.id)],
                        metadata={
                            "merchant": bill.merchant,
                            "amount": bill.amount,
                            "transaction_type": bill.transaction_type,
                            "time_window_minutes": time_window_minutes,
                        },
                    )
                )
        return issues

    def _is_possible_duplicate_bill(
        self,
        bill: BillRead,
        other: BillRead,
        time_window_minutes: int,
    ) -> bool:
        if bill.amount != other.amount:
            return False
        if bill.transaction_type != other.transaction_type:
            return False
        if bill.merchant.casefold() != other.merchant.casefold():
            return False
        delta = abs(
            self._as_utc(bill.paid_at)
            - self._as_utc(other.paid_at)
        )
        return delta.total_seconds() <= time_window_minutes * 60

    def _as_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _task_issues(self, now: datetime) -> list[DiagnosticIssue]:
        issues: list[DiagnosticIssue] = []
        for task in task_store.all():
            if task.status != TaskStatus.pending:
                continue
            target_at = self._task_target_at(task)
            if target_at is None:
                issues.append(
                    DiagnosticIssue(
                        code="unscheduled_pending_task",
                        severity=DiagnosticSeverity.info,
                        message="Pending task has no due or reminder time.",
                        entity_type="task",
                        entity_id=str(task.id),
                        metadata={"title": task.title, "category": task.category},
                    )
                )
                continue
            if target_at < now:
                issues.append(
                    DiagnosticIssue(
                        code="overdue_task",
                        severity=DiagnosticSeverity.action_required,
                        message="Pending task is overdue.",
                        entity_type="task",
                        entity_id=str(task.id),
                        metadata={
                            "title": task.title,
                            "target_at": target_at,
                            "task_type": task.task_type,
                            "priority": task.priority,
                        },
                    )
                )
        return issues

    def _task_target_at(self, task: TaskRead) -> datetime | None:
        target_at = task.remind_at if task.task_type == TaskType.reminder else task.due_at
        target_at = target_at or task.due_at or task.remind_at
        if target_at is None:
            return None
        if target_at.tzinfo is None:
            return target_at.replace(tzinfo=timezone.utc)
        return target_at.astimezone(timezone.utc)

    def _recycle_bin_issues(self) -> list[DiagnosticIssue]:
        summary = data_management_service.summary()
        issues: list[DiagnosticIssue] = []
        if summary.deleted_bill_count:
            issues.append(
                DiagnosticIssue(
                    code="deleted_bills_in_recycle_bin",
                    severity=DiagnosticSeverity.info,
                    message="There are deleted bills available for restore.",
                    entity_type="bill",
                    metadata={"deleted_bill_count": summary.deleted_bill_count},
                )
            )
        if summary.deleted_task_count:
            issues.append(
                DiagnosticIssue(
                    code="deleted_tasks_in_recycle_bin",
                    severity=DiagnosticSeverity.info,
                    message="There are deleted tasks available for restore.",
                    entity_type="task",
                    metadata={"deleted_task_count": summary.deleted_task_count},
                )
            )
        return issues

    def _severity_count(
        self,
        issues: list[DiagnosticIssue],
        severity: DiagnosticSeverity,
    ) -> int:
        return len([issue for issue in issues if issue.severity == severity])

    def _status(self, warning_count: int, action_required_count: int) -> str:
        if action_required_count:
            return "action_required"
        if warning_count:
            return "warning"
        return "ok"

    def _issue_sort_key(self, issue: DiagnosticIssue) -> tuple[int, str]:
        severity_order = {
            DiagnosticSeverity.action_required: 0,
            DiagnosticSeverity.warning: 1,
            DiagnosticSeverity.info: 2,
        }
        return (severity_order[issue.severity], issue.code)


diagnostics_service = DiagnosticsService()
