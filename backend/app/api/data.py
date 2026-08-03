from fastapi import APIRouter, Header, HTTPException, Request, Response, status

from app.schemas.settings import (
    DataClearRequest,
    DataClearResponse,
    DataExportResponse,
    DemoDataSeedRequest,
    DemoDataSeedResponse,
    LocalDataSummary,
)
from app.services.audit_log_store import audit_log_store
from app.services.data_management_service import data_management_service
from app.services.idempotency_store import IdempotencyConflictError, idempotency_store

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/summary", response_model=LocalDataSummary)
def get_local_data_summary() -> LocalDataSummary:
    return data_management_service.summary()


@router.get("/export", response_model=DataExportResponse)
def export_local_data(request: Request) -> DataExportResponse:
    exported = data_management_service.export()
    audit_log_store.record(
        action="data_exported",
        entity_type="data",
        request=request,
        metadata={"format": "json"},
    )
    return exported


@router.get("/export/bills.csv")
def export_bills_csv(request: Request) -> Response:
    audit_log_store.record(
        action="data_exported",
        entity_type="data",
        request=request,
        metadata={"format": "csv", "dataset": "bills"},
    )
    return _csv_response(
        data_management_service.export_bills_csv(),
        filename="lifesnap-bills.csv",
    )


@router.get("/export/tasks.csv")
def export_tasks_csv(request: Request) -> Response:
    audit_log_store.record(
        action="data_exported",
        entity_type="data",
        request=request,
        metadata={"format": "csv", "dataset": "tasks"},
    )
    return _csv_response(
        data_management_service.export_tasks_csv(),
        filename="lifesnap-tasks.csv",
    )


@router.get("/export/attachments.csv")
def export_attachments_csv(request: Request) -> Response:
    audit_log_store.record(
        action="data_exported",
        entity_type="data",
        request=request,
        metadata={"format": "csv", "dataset": "attachments"},
    )
    return _csv_response(
        data_management_service.export_attachments_csv(),
        filename="lifesnap-attachments.csv",
    )


@router.get("/export/bill-candidates.csv")
def export_bill_candidates_csv(request: Request) -> Response:
    audit_log_store.record(
        action="data_exported",
        entity_type="data",
        request=request,
        metadata={"format": "csv", "dataset": "bill_candidates"},
    )
    return _csv_response(
        data_management_service.export_bill_candidates_csv(),
        filename="lifesnap-bill-candidates.csv",
    )


@router.get("/export/task-candidates.csv")
def export_task_candidates_csv(request: Request) -> Response:
    audit_log_store.record(
        action="data_exported",
        entity_type="data",
        request=request,
        metadata={"format": "csv", "dataset": "task_candidates"},
    )
    return _csv_response(
        data_management_service.export_task_candidates_csv(),
        filename="lifesnap-task-candidates.csv",
    )


@router.post("/clear", response_model=DataClearResponse)
def clear_local_data(payload: DataClearRequest, request: Request) -> DataClearResponse:
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Set confirm to true before clearing local data",
        )
    result = data_management_service.clear(payload)
    audit_log_store.record(
        action="data_cleared",
        entity_type="data",
        request=request,
        metadata={
            "include_bills": payload.include_bills,
            "include_tasks": payload.include_tasks,
            "include_attachments": payload.include_attachments,
            "include_candidates": payload.include_candidates,
            "reset_privacy_settings": payload.reset_privacy_settings,
            "after_bill_count": result.after.bill_count,
            "after_task_count": result.after.task_count,
        },
    )
    return result


@router.post("/seed-demo", response_model=DemoDataSeedResponse)
def seed_demo_data(
    payload: DemoDataSeedRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> DemoDataSeedResponse:
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Set confirm to true before seeding demo data",
        )

    try:
        result = idempotency_store.run(
            scope="POST /data/seed-demo",
            key=idempotency_key,
            fingerprint=payload.model_dump(mode="json"),
            factory=lambda: data_management_service.seed_demo_data(payload),
        )
        audit_log_store.record(
            action="demo_data_seeded",
            entity_type="data",
            request=request,
            metadata={
                "reset_existing": payload.reset_existing,
                "include_attachment": payload.include_attachment,
                "include_candidates": payload.include_candidates,
                "created_bill_count": len(result.created_bills),
                "created_task_count": len(result.created_tasks),
            },
        )
        return result
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def _csv_response(content: str, filename: str) -> Response:
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
