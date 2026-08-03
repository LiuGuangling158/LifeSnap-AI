from fastapi import APIRouter, Query

from app.schemas.bootstrap import AppBootstrapResponse, AppCapabilities
from app.services.bootstrap_service import bootstrap_service

router = APIRouter(prefix="/app", tags=["app"])


@router.get("/capabilities", response_model=AppCapabilities)
def get_app_capabilities() -> AppCapabilities:
    return bootstrap_service.capabilities()


@router.get("/bootstrap", response_model=AppBootstrapResponse)
def get_app_bootstrap(
    year: int | None = Query(default=None, ge=1970),
    month: int | None = Query(default=None, ge=1, le=12),
    upcoming_days: int = Query(default=7, ge=1, le=31),
    today_limit: int = Query(default=10, ge=1, le=50),
    reminder_limit: int = Query(default=10, ge=1, le=50),
    recent_bill_limit: int = Query(default=5, ge=1, le=50),
    candidate_limit: int = Query(default=5, ge=1, le=50),
) -> AppBootstrapResponse:
    return bootstrap_service.bootstrap(
        year=year,
        month=month,
        upcoming_days=upcoming_days,
        today_limit=today_limit,
        reminder_limit=reminder_limit,
        recent_bill_limit=recent_bill_limit,
        candidate_limit=candidate_limit,
    )
