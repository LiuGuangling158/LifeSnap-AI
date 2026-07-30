from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.schemas.bill import BillCreate, BillRead, BillUpdate
from app.services.bill_store import bill_store

router = APIRouter(prefix="/bills", tags=["bills"])


@router.post("", response_model=BillRead, status_code=status.HTTP_201_CREATED)
def create_bill(payload: BillCreate) -> BillRead:
    return bill_store.create(payload)


@router.get("", response_model=list[BillRead])
def list_bills() -> list[BillRead]:
    return bill_store.list()


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
