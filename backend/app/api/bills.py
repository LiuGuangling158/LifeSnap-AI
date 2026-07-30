from fastapi import APIRouter, status

from app.schemas.bill import BillCreate, BillRead
from app.services.bill_store import bill_store

router = APIRouter(prefix="/bills", tags=["bills"])


@router.post("", response_model=BillRead, status_code=status.HTTP_201_CREATED)
def create_bill(payload: BillCreate) -> BillRead:
    return bill_store.create(payload)


@router.get("", response_model=list[BillRead])
def list_bills() -> list[BillRead]:
    return bill_store.list()

