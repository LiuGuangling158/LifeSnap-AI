from datetime import date
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, status

from app.schemas.diary import (
    DiaryCreate,
    DiaryListResponse,
    DiaryMood,
    DiaryRead,
    DiaryStatisticsOverview,
    DiaryUpdate,
)
from app.services.audit_log_store import audit_log_store
from app.services.diary_store import DiaryDateConflictError, diary_store
from app.services.idempotency_store import IdempotencyConflictError, idempotency_store

router = APIRouter(prefix="/diaries", tags=["diaries"])


@router.post("", response_model=DiaryRead, status_code=status.HTTP_201_CREATED)
def create_diary(
    payload: DiaryCreate,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> DiaryRead:
    try:
        diary = idempotency_store.run(
            scope="POST /diaries",
            key=idempotency_key,
            fingerprint=payload.model_dump(mode="json"),
            factory=lambda: diary_store.create(payload),
        )
        audit_log_store.record(
            action="diary_created",
            entity_type="diary",
            entity_id=diary.id,
            request=request,
            metadata={
                "entry_date": diary.entry_date,
                "mood": diary.mood,
                "source": diary.source,
            },
        )
        return diary
    except DiaryDateConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.put("/by-date/{entry_date}", response_model=DiaryRead)
def upsert_diary_by_date(
    entry_date: date,
    payload: DiaryCreate,
    request: Request,
) -> DiaryRead:
    if payload.entry_date != entry_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path date must match payload entry_date",
        )
    diary = diary_store.upsert_by_date(entry_date, payload)
    audit_log_store.record(
        action="diary_upserted",
        entity_type="diary",
        entity_id=diary.id,
        request=request,
        metadata={
            "entry_date": diary.entry_date,
            "mood": diary.mood,
            "source": diary.source,
        },
    )
    return diary


@router.get("", response_model=DiaryListResponse)
def list_diaries(
    start_date: date | None = Query(default=None),
    end_date: date | None = Query(default=None),
    mood: DiaryMood | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=120),
    include_deleted: bool = Query(default=False),
    deleted_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> DiaryListResponse:
    return diary_store.list(
        start_date=start_date,
        end_date=end_date,
        mood=mood,
        keyword=q,
        include_deleted=include_deleted,
        deleted_only=deleted_only,
        page=page,
        page_size=page_size,
    )


@router.get("/statistics/overview", response_model=DiaryStatisticsOverview)
def get_diary_statistics_overview() -> DiaryStatisticsOverview:
    return diary_store.statistics_overview()


@router.get("/by-date/{entry_date}", response_model=DiaryRead)
def get_diary_by_date(
    entry_date: date,
    include_deleted: bool = Query(default=False),
) -> DiaryRead:
    diary = diary_store.get_by_date(entry_date, include_deleted=include_deleted)
    if diary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diary not found")
    return diary


@router.get("/{diary_id}", response_model=DiaryRead)
def get_diary(
    diary_id: UUID,
    include_deleted: bool = Query(default=False),
) -> DiaryRead:
    diary = diary_store.get(diary_id, include_deleted=include_deleted)
    if diary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diary not found")
    return diary


@router.patch("/{diary_id}", response_model=DiaryRead)
def update_diary(diary_id: UUID, payload: DiaryUpdate, request: Request) -> DiaryRead:
    try:
        diary = diary_store.update(diary_id, payload)
    except DiaryDateConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if diary is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diary not found")
    audit_log_store.record(
        action="diary_updated",
        entity_type="diary",
        entity_id=diary_id,
        request=request,
        metadata={"updated_fields": payload.model_dump(exclude_none=True, exclude_unset=True)},
    )
    return diary


@router.post("/{diary_id}/restore", response_model=DiaryRead)
def restore_diary(
    diary_id: UUID,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> DiaryRead:
    def restore() -> DiaryRead:
        try:
            diary = diary_store.restore(diary_id)
        except DiaryDateConflictError as exc:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
        if diary is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diary not found")
        return diary

    try:
        diary = idempotency_store.run(
            scope="POST /diaries/restore",
            key=idempotency_key,
            fingerprint={"diary_id": str(diary_id)},
            factory=restore,
        )
        audit_log_store.record(
            action="diary_restored",
            entity_type="diary",
            entity_id=diary_id,
            request=request,
        )
        return diary
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.delete("/{diary_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_diary(diary_id: UUID, request: Request) -> None:
    deleted = diary_store.delete(diary_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Diary not found")
    audit_log_store.record(
        action="diary_deleted",
        entity_type="diary",
        entity_id=diary_id,
        request=request,
    )
