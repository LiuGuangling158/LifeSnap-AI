from fastapi import APIRouter, Query

from app.schemas.dashboard import DashboardSummary
from app.services.dashboard_service import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def get_dashboard_summary(
    year: int | None = Query(default=None, ge=1970),
    month: int | None = Query(default=None, ge=1, le=12),
    upcoming_days: int = Query(default=7, ge=1, le=31),
    today_limit: int = Query(default=10, ge=1, le=50),
    reminder_limit: int = Query(default=10, ge=1, le=50),
    recent_bill_limit: int = Query(default=5, ge=1, le=50),
    candidate_limit: int = Query(default=5, ge=1, le=50),
) -> DashboardSummary:
    return dashboard_service.summary(
        year=year,
        month=month,
        upcoming_days=upcoming_days,
        today_limit=today_limit,
        reminder_limit=reminder_limit,
        recent_bill_limit=recent_bill_limit,
        candidate_limit=candidate_limit,
    )
