from fastapi import APIRouter, HTTPException, Response, status

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


@router.get("/export/bills.csv")
def export_bills_csv() -> Response:
    return _csv_response(
        data_management_service.export_bills_csv(),
        filename="lifesnap-bills.csv",
    )


@router.get("/export/tasks.csv")
def export_tasks_csv() -> Response:
    return _csv_response(
        data_management_service.export_tasks_csv(),
        filename="lifesnap-tasks.csv",
    )


@router.get("/export/attachments.csv")
def export_attachments_csv() -> Response:
    return _csv_response(
        data_management_service.export_attachments_csv(),
        filename="lifesnap-attachments.csv",
    )


@router.post("/clear", response_model=DataClearResponse)
def clear_local_data(payload: DataClearRequest) -> DataClearResponse:
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Set confirm to true before clearing local data",
        )
    return data_management_service.clear(payload)


def _csv_response(content: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
