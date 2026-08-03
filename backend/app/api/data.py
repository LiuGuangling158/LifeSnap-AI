from fastapi import APIRouter, Body, Header, HTTPException, Request, Response, status

from app.schemas.settings import (
    DataClearRequest,
    DataClearResponse,
    DataExportResponse,
    DataImportRequest,
    DataImportResponse,
    DataSnapshotDeleteRequest,
    DataSnapshotDeleteResponse,
    DataSnapshotLoadRequest,
    DataSnapshotLoadResponse,
    DataSnapshotSaveResponse,
    DataSnapshotStatus,
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


@router.get("/snapshot/status", response_model=DataSnapshotStatus)
def get_local_snapshot_status() -> DataSnapshotStatus:
    return data_management_service.snapshot_status()


@router.post("/snapshot/save", response_model=DataSnapshotSaveResponse)
def save_local_snapshot(request: Request) -> DataSnapshotSaveResponse:
    result = data_management_service.save_snapshot()
    audit_log_store.record(
        action="data_snapshot_saved",
        entity_type="data",
        request=request,
        metadata={
            "snapshot_path": result.snapshot_path,
            "file_size_bytes": result.file_size_bytes,
        },
    )
    return result


@router.post("/snapshot/load", response_model=DataSnapshotLoadResponse)
def load_local_snapshot(
    payload: DataSnapshotLoadRequest,
    request: Request,
) -> DataSnapshotLoadResponse:
    if not payload.dry_run and not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Set confirm to true before loading local snapshot",
        )

    try:
        result = data_management_service.load_snapshot(payload)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Local snapshot not found",
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )

    audit_log_store.record(
        action="data_snapshot_loaded" if not payload.dry_run else "data_snapshot_load_dry_run",
        entity_type="data",
        request=request,
        metadata={
            "snapshot_path": result.snapshot_path,
            "dry_run": payload.dry_run,
            "reset_existing": payload.reset_existing,
            "imported_bill_count": result.import_result.imported_bill_count,
            "imported_task_count": result.import_result.imported_task_count,
        },
    )
    return result


@router.delete("/snapshot", response_model=DataSnapshotDeleteResponse)
def delete_local_snapshot(
    request: Request,
    payload: DataSnapshotDeleteRequest = Body(
        default_factory=DataSnapshotDeleteRequest,
    ),
) -> DataSnapshotDeleteResponse:
    if not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Set confirm to true before deleting local snapshot",
        )
    result = data_management_service.delete_snapshot()
    audit_log_store.record(
        action="data_snapshot_deleted",
        entity_type="data",
        request=request,
        metadata={"snapshot_path": result.snapshot_path, "deleted": result.deleted},
    )
    return result


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


@router.post("/import", response_model=DataImportResponse)
def import_local_data(payload: DataImportRequest, request: Request) -> DataImportResponse:
    if not payload.dry_run and not payload.confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Set confirm to true before importing local data",
        )

    result = data_management_service.import_data(payload)
    audit_log_store.record(
        action="data_imported" if not payload.dry_run else "data_import_dry_run",
        entity_type="data",
        request=request,
        metadata={
            "dry_run": payload.dry_run,
            "reset_existing": payload.reset_existing,
            "include_bills": payload.include_bills,
            "include_tasks": payload.include_tasks,
            "include_attachments": payload.include_attachments,
            "include_candidates": payload.include_candidates,
            "import_privacy_settings": payload.import_privacy_settings,
            "imported_bill_count": result.imported_bill_count,
            "imported_task_count": result.imported_task_count,
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
