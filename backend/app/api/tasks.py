from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, status

from app.schemas.task import (
    TaskCreate,
    TaskListResponse,
    TaskRead,
    TaskSnoozeRequest,
    TaskStatisticsOverview,
    TaskStatus,
    TaskType,
    TaskUpdate,
)
from app.services.audit_log_store import audit_log_store
from app.services.idempotency_store import IdempotencyConflictError, idempotency_store
from app.services.task_store import task_store

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> TaskRead:
    try:
        task = idempotency_store.run(
            scope="POST /tasks",
            key=idempotency_key,
            fingerprint=payload.model_dump(mode="json"),
            factory=lambda: task_store.create(payload),
        )
        audit_log_store.record(
            action="task_created",
            entity_type="task",
            entity_id=task.id,
            request=request,
            metadata={
                "source": task.source,
                "task_type": task.task_type,
                "category": task.category,
                "priority": task.priority,
            },
        )
        return task
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("", response_model=TaskListResponse)
def list_tasks(
    status_filter: TaskStatus | None = Query(default=None, alias="status"),
    task_type: TaskType | None = Query(default=None),
    category: str | None = Query(default=None, min_length=1, max_length=40),
    due_from: datetime | None = Query(default=None),
    due_to: datetime | None = Query(default=None),
    include_deleted: bool = Query(default=False),
    deleted_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> TaskListResponse:
    return task_store.list(
        status=status_filter,
        task_type=task_type,
        category=category,
        due_from=due_from,
        due_to=due_to,
        include_deleted=include_deleted,
        deleted_only=deleted_only,
        page=page,
        page_size=page_size,
    )


@router.get("/statistics/overview", response_model=TaskStatisticsOverview)
def get_task_statistics_overview(
    upcoming_days: int = Query(default=7, ge=1, le=90),
    item_limit: int = Query(default=10, ge=1, le=50),
) -> TaskStatisticsOverview:
    return task_store.statistics_overview(
        upcoming_days=upcoming_days,
        item_limit=item_limit,
    )


@router.get("/{task_id}", response_model=TaskRead)
def get_task(
    task_id: UUID,
    include_deleted: bool = Query(default=False),
) -> TaskRead:
    task = task_store.get(task_id, include_deleted=include_deleted)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    return task


@router.patch("/{task_id}", response_model=TaskRead)
def update_task(task_id: UUID, payload: TaskUpdate, request: Request) -> TaskRead:
    task = task_store.update(task_id, payload)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    audit_log_store.record(
        action="task_updated",
        entity_type="task",
        entity_id=task_id,
        request=request,
        metadata={"updated_fields": payload.model_dump(exclude_none=True, exclude_unset=True)},
    )
    return task


@router.post("/{task_id}/complete", response_model=TaskRead)
def complete_task(
    task_id: UUID,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> TaskRead:
    def complete() -> TaskRead:
        task = task_store.complete(task_id)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return task

    try:
        task = idempotency_store.run(
            scope="POST /tasks/complete",
            key=idempotency_key,
            fingerprint={"task_id": str(task_id)},
            factory=complete,
        )
        audit_log_store.record(
            action="task_completed",
            entity_type="task",
            entity_id=task_id,
            request=request,
        )
        return task
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/{task_id}/snooze", response_model=TaskRead)
def snooze_task(
    task_id: UUID,
    payload: TaskSnoozeRequest,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> TaskRead:
    def snooze() -> TaskRead:
        existing = task_store.get(task_id)
        if existing is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        if existing.status != TaskStatus.pending:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only pending tasks can be snoozed",
            )
        if payload.snooze_until is None and payload.minutes is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide snooze_until or minutes",
            )
        if payload.snooze_until is not None and payload.minutes is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Provide only one of snooze_until or minutes",
            )

        task = task_store.snooze(
            task_id,
            snooze_until=payload.snooze_until,
            minutes=payload.minutes,
        )
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return task

    try:
        task = idempotency_store.run(
            scope="POST /tasks/snooze",
            key=idempotency_key,
            fingerprint={
                "task_id": str(task_id),
                "payload": payload.model_dump(mode="json"),
            },
            factory=snooze,
        )
        audit_log_store.record(
            action="task_snoozed",
            entity_type="task",
            entity_id=task_id,
            request=request,
            metadata={"minutes": payload.minutes, "snooze_until": payload.snooze_until},
        )
        return task
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/{task_id}/restore", response_model=TaskRead)
def restore_task(
    task_id: UUID,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> TaskRead:
    def restore() -> TaskRead:
        task = task_store.restore(task_id)
        if task is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return task

    try:
        task = idempotency_store.run(
            scope="POST /tasks/restore",
            key=idempotency_key,
            fingerprint={"task_id": str(task_id)},
            factory=restore,
        )
        audit_log_store.record(
            action="task_restored",
            entity_type="task",
            entity_id=task_id,
            request=request,
        )
        return task
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.delete("/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(task_id: UUID, request: Request) -> None:
    deleted = task_store.delete(task_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    audit_log_store.record(
        action="task_deleted",
        entity_type="task",
        entity_id=task_id,
        request=request,
    )
