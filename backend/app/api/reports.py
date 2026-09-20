from datetime import datetime

from fastapi import APIRouter, Query

from app.core.config import settings
from app.schemas.reports import MonthlyFinanceReport
from app.services.report_service import report_service

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/monthly", response_model=MonthlyFinanceReport)
def get_monthly_report(
    year: int | None = Query(default=None, ge=1970),
    month: int | None = Query(default=None, ge=1, le=12),
) -> MonthlyFinanceReport:
    now = datetime.now(settings.business_tzinfo)
    return report_service.monthly_report(year or now.year, month or now.month)
