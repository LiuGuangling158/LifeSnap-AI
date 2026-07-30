from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.bill import (
    BillCreate,
    BillListResponse,
    BillRead,
    BillSource,
    BillUpdate,
    MonthlyBillStatistics,
    TransactionType,
)
from app.services.bill_store import bill_store

router = APIRouter(prefix="/bills", tags=["bills"])


@router.post("", response_model=BillRead, status_code=status.HTTP_201_CREATED)
def create_bill(payload: BillCreate) -> BillRead:
    return bill_store.create(payload)


@router.get("", response_model=BillListResponse)
def list_bills(
    year: int | None = Query(default=None, ge=1970),
    month: int | None = Query(default=None, ge=1, le=12),
    category: str | None = Query(default=None, min_length=1, max_length=40),
    transaction_type: TransactionType | None = Query(default=None),
    source: BillSource | None = Query(default=None),
    q: str | None = Query(default=None, min_length=1, max_length=80),
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


@router.get("/{bill_id}", response_model=BillRead)
def get_bill(bill_id: UUID) -> BillRead:
    bill = bill_store.get(bill_id)
    if bill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
    return bill


@router.patch("/{bill_id}", response_model=BillRead)
def update_bill(bill_id: UUID, payload: BillUpdate) -> BillRead:
    bill = bill_store.update(bill_id, payload)
    if bill is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
    return bill


@router.delete("/{bill_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bill(bill_id: UUID) -> None:
    deleted = bill_store.delete(bill_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bill not found")
