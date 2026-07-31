from fastapi import APIRouter, HTTPException, status

from app.schemas.settings import (
    DataClearRequest,
    DataClearResponse,
    DataExportResponse,
    LocalDataSummary,
)
from app.services.data_management_service import data_management_service

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/summary", response_model=LocalDataSummary)
def get_local_data_summary() -> LocalDataSummary:
    return data_management_service.summary()


@router.get("/export", response_model=DataExportResponse)
def export_local_data() -> DataExportResponse:
    return data_management_service.export()


@router.post("/clear", response_model=DataClearResponse)
def clear_local_data(payload: DataClearRequest) -> DataClearResponse:
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Set confirm to true before clearing local data",
        )
    return data_management_service.clear(payload)
