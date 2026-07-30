from datetime import datetime

from pydantic import BaseModel

from app.schemas.bill import MonthlyBillStatistics
from app.schemas.task import TaskRead


class DashboardSummary(BaseModel):
    generated_at: datetime
    monthly_statistics: MonthlyBillStatistics
    today_tasks: list[TaskRead]
    upcoming_reminders: list[TaskRead]
    today_task_count: int
    upcoming_reminder_count: int

