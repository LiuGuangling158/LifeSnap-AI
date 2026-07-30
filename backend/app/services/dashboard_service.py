from datetime import datetime, timezone

from app.schemas.dashboard import DashboardSummary
from app.services.bill_store import bill_store
from app.services.task_store import task_store


class DashboardService:
    def summary(
        self,
        year: int | None = None,
        month: int | None = None,
        upcoming_days: int = 7,
        today_limit: int = 10,
        reminder_limit: int = 10,
    ) -> DashboardSummary:
        now = datetime.now(timezone.utc)
        target_year = year or now.year
        target_month = month or now.month

        monthly_statistics = bill_store.monthly_statistics(target_year, target_month)
        today_tasks = task_store.today_tasks(now, limit=today_limit)
        upcoming_reminders = task_store.upcoming_reminders(
            now,
            days=upcoming_days,
            limit=reminder_limit,
        )

        return DashboardSummary(
            generated_at=now,
            monthly_statistics=monthly_statistics,
            today_tasks=today_tasks,
            upcoming_reminders=upcoming_reminders,
            today_task_count=len(today_tasks),
            upcoming_reminder_count=len(upcoming_reminders),
        )


dashboard_service = DashboardService()

