from datetime import datetime

from pydantic import BaseModel

from app.schemas.agent import ParseBillResponse, ParseTaskResponse
from app.schemas.bill import BillRead, MonthlyBillStatistics
from app.schemas.settings import LocalDataSummary
from app.schemas.task import TaskRead


class DashboardSummary(BaseModel):
    generated_at: datetime
    data_summary: LocalDataSummary
    monthly_statistics: MonthlyBillStatistics
    recent_bills: list[BillRead]
    today_tasks: list[TaskRead]
    upcoming_reminders: list[TaskRead]
    pending_bill_candidates: list[ParseBillResponse]
    pending_task_candidates: list[ParseTaskResponse]
    recent_bill_count: int
    today_task_count: int
    upcoming_reminder_count: int
    pending_bill_candidate_count: int
    pending_task_candidate_count: int
