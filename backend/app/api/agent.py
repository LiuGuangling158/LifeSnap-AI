from fastapi import APIRouter

from app.schemas.agent import ParseBillRequest, ParseBillResponse
from app.services.bill_parser import bill_parser

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/parse-bill", response_model=ParseBillResponse)
def parse_bill(payload: ParseBillRequest) -> ParseBillResponse:
    return bill_parser.parse_bill(payload)

