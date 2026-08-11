from datetime import datetime, timezone
from typing import TypeVar

from app.schemas.dashboard import DashboardSummary
from app.schemas.settings import LocalDataSummary
from app.services.attachment_store import attachment_store
from app.services.bill_candidate_store import bill_candidate_store
from app.services.bill_store import bill_store
from app.services.diary_store import diary_store
from app.services.task_candidate_store import task_candidate_store
from app.services.task_store import task_store

T = TypeVar("T")


class DashboardService:
    def summary(
        self,
        year: int | None = None,
        month: int | None = None,
        upcoming_days: int = 7,
        today_limit: int = 10,
        reminder_limit: int = 10,
        recent_bill_limit: int = 5,
        candidate_limit: int = 5,
    ) -> DashboardSummary:
        now = datetime.now(timezone.utc)
        target_year = year or now.year
        target_month = month or now.month

        monthly_statistics = bill_store.monthly_statistics(target_year, target_month)
        recent_bills = bill_store.list(page=1, page_size=recent_bill_limit).items
        today_tasks = task_store.today_tasks(now, limit=today_limit)
        upcoming_reminders = task_store.upcoming_reminders(
            now,
            days=upcoming_days,
            limit=reminder_limit,
        )
        pending_bill_candidates = self._latest(
            bill_candidate_store.all(),
            limit=candidate_limit,
        )
        pending_task_candidates = self._latest(
            task_candidate_store.all(),
            limit=candidate_limit,
        )

        return DashboardSummary(
            generated_at=now,
            data_summary=LocalDataSummary(
                bill_count=len(bill_store.all()),
                task_count=len(task_store.all()),
                diary_count=len(diary_store.all()),
                attachment_count=len(attachment_store.all()),
                bill_candidate_count=len(bill_candidate_store.all()),
                task_candidate_count=len(task_candidate_store.all()),
                deleted_bill_count=bill_store.deleted_count(),
                deleted_task_count=task_store.deleted_count(),
                deleted_diary_count=diary_store.deleted_count(),
            ),
            monthly_statistics=monthly_statistics,
            recent_bills=recent_bills,
            today_tasks=today_tasks,
            upcoming_reminders=upcoming_reminders,
            pending_bill_candidates=pending_bill_candidates,
            pending_task_candidates=pending_task_candidates,
            recent_bill_count=len(recent_bills),
            today_task_count=len(today_tasks),
            upcoming_reminder_count=len(upcoming_reminders),
            pending_bill_candidate_count=len(pending_bill_candidates),
            pending_task_candidate_count=len(pending_task_candidates),
        )

    def _latest(self, values: list[T], limit: int) -> list[T]:
        return list(reversed(values))[:limit]


dashboard_service = DashboardService()
