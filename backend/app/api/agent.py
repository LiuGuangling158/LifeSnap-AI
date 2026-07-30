from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.schemas.bill import BillRead
from app.schemas.agent import ParseBillRequest, ParseBillResponse
from app.services.bill_candidate_store import bill_candidate_store
from app.services.bill_parser import bill_parser

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/parse-bill", response_model=ParseBillResponse)
def parse_bill(payload: ParseBillRequest) -> ParseBillResponse:
    candidate = bill_parser.parse_bill(payload)
    return bill_candidate_store.save(candidate)


@router.get("/bill-candidates/{candidate_id}", response_model=ParseBillResponse)
def get_bill_candidate(candidate_id: UUID) -> ParseBillResponse:
    candidate = bill_candidate_store.get(candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill candidate not found",
        )
    return candidate


@router.post("/bill-candidates/{candidate_id}/confirm", response_model=BillRead)
def confirm_bill_candidate(candidate_id: UUID) -> BillRead:
    candidate = bill_candidate_store.get(candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill candidate not found",
        )
    if not bill_candidate_store.is_confirmable(candidate):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bill candidate is missing required fields",
        )

    bill = bill_candidate_store.confirm(candidate_id)
    if bill is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill candidate not found",
        )
    return bill
