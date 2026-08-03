from fastapi import APIRouter, Query

from app.schemas.diagnostics import DataQualityDiagnostics
from app.services.diagnostics_service import diagnostics_service

router = APIRouter(prefix="/diagnostics", tags=["diagnostics"])


@router.get("/data-quality", response_model=DataQualityDiagnostics)
def get_data_quality_diagnostics(
    duplicate_time_window_minutes: int = Query(default=10, ge=1, le=1440),
    issue_limit: int = Query(default=50, ge=1, le=200),
) -> DataQualityDiagnostics:
    return diagnostics_service.data_quality(
        duplicate_time_window_minutes=duplicate_time_window_minutes,
        issue_limit=issue_limit,
    )
