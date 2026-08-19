from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, Request, status

from app.schemas.bill import (
    BillStatisticsOverview,
    BillCreate,
    BillListResponse,
    BillRead,
    BillSource,
    BillUpdate,
    DuplicateBillCheckResponse,
    MonthlyBillStatistics,
    TransactionType,
)
from app.services.audit_log_store import audit_log_store
from app.services.bill_store import bill_store
from app.services.idempotency_store import IdempotencyConflictError, idempotency_store

router = APIRouter(prefix="/bills", tags=["bills"])


@router.post("", response_model=BillRead, status_code=status.HTTP_201_CREATED)
def create_bill(
    payload: BillCreate,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> BillRead:
    try:
        bill = idempotency_store.run(
            scope="POST /bills",
            key=idempotency_key,
            fingerprint=payload.model_dump(mode="json"),
            factory=lambda: bill_store.create(payload),
        )
        audit_log_store.record(
            action="bill_created",
            entity_type="bill",
            entity_id=bill.id,
            request=request,
            metadata={
                "source": bill.source,
                "transaction_type": bill.transaction_type,
                "category": bill.category,
            },
        )
        return bill
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.get("", response_model=BillListResponse)
def list_bills(
    year: int | None = Query(default=None, ge=1970),
    month: int | None = Query(default=None, ge=1, le=12),
    category: str | None = Query(default=None, min_length=1, max_length=40),
    transaction_type: TransactionType | None = Query(default=None),
    source: BillSource | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=80),
    paid_from: datetime | None = Query(default=None),
    paid_to: datetime | None = Query(default=None),
    include_deleted: bool = Query(default=False),
    deleted_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> BillListResponse:
    now = datetime.now(timezone.utc)
    target_year = year or (now.year if month is not None else None)
    return bill_store.list(
        year=target_year,
        month=month,
        category=category,
        transaction_type=transaction_type,
        source=source,
        keyword=q,
        paid_from=paid_from,
        paid_to=paid_to,
        include_deleted=include_deleted,
        deleted_only=deleted_only,
        page=page,
        page_size=page_size,
    )


@router.get("/statistics/monthly", response_model=MonthlyBillStatistics)
def get_monthly_bill_statistics(
    year: int | None = Query(default=None, ge=1970),
    month: int | None = Query(default=None, ge=1, le=12),
) -> MonthlyBillStatistics:
    now = datetime.now(timezone.utc)
    target_year = year or now.year
    target_month = month or now.month
    return bill_store.monthly_statistics(target_year, target_month)


@router.get("/statistics/overview", response_model=BillStatisticsOverview)
def get_bill_statistics_overview(
    year: int | None = Query(default=None, ge=1970),
    month: int | None = Query(default=None, ge=1, le=12),
    trend_months: int = Query(default=6, ge=1, le=24),
    top_merchant_limit: int = Query(default=5, ge=1, le=20),
) -> BillStatisticsOverview:
    now = datetime.now(timezone.utc)
    target_year = year or now.year
    target_month = month or now.month
    return bill_store.statistics_overview(
        target_year,
        target_month,
        trend_months=trend_months,
        top_merchant_limit=top_merchant_limit,
    )


@router.post("/check-duplicate", response_model=DuplicateBillCheckResponse)
def check_duplicate_bill(
    payload: BillCreate,
    time_window_minutes: int = Query(default=10, ge=1, le=1440),
) -> DuplicateBillCheckResponse:
    return bill_store.check_duplicate(
        payload,
        time_window_minutes=time_window_minutes,
    )


@router.get("/{bill_id}", response_model=BillRead)
def get_bill(
    bill_id: UUID,
    include_deleted: bool = Query(default=False),
) -> BillRead:
    bill = bill_store.get(bill_id, include_deleted=include_deleted)
    if bill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
    return bill


@router.patch("/{bill_id}", response_model=BillRead)
def update_bill(bill_id: UUID, payload: BillUpdate, request: Request) -> BillRead:
    bill = bill_store.update(bill_id, payload)
    if bill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
    audit_log_store.record(
        action="bill_updated",
        entity_type="bill",
        entity_id=bill_id,
        request=request,
        metadata={"updated_fields": payload.model_dump(exclude_none=True, exclude_unset=True)},
    )
    return bill


@router.post("/{bill_id}/restore", response_model=BillRead)
def restore_bill(
    bill_id: UUID,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> BillRead:
    def restore() -> BillRead:
        bill = bill_store.restore(bill_id)
        if bill is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
        return bill

    try:
        bill = idempotency_store.run(
            scope="POST /bills/restore",
            key=idempotency_key,
            fingerprint={"bill_id": str(bill_id)},
            factory=restore,
        )
        audit_log_store.record(
            action="bill_restored",
            entity_type="bill",
            entity_id=bill_id,
            request=request,
        )
        return bill
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.delete("/{bill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bill(bill_id: UUID, request: Request) -> None:
    deleted = bill_store.delete(bill_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
    audit_log_store.record(
        action="bill_deleted",
        entity_type="bill",
        entity_id=bill_id,
        request=request,
    )
