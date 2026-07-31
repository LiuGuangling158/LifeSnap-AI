from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.bill import BillSource, TransactionType


class ParseBillRequest(BaseModel):
    text: str = Field(min_length=1, max_length=5000)
    source: BillSource = BillSource.screenshot


class BillCandidateData(BaseModel):
    amount: Decimal | None = None
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    merchant: str | None = Field(default=None, max_length=120)
    category: str = Field(default="其他", min_length=1, max_length=40)
    payment_method: str | None = Field(default=None, max_length=40)
    paid_at: datetime | None = None
    transaction_type: TransactionType = TransactionType.expense
    note: str | None = Field(default=None, max_length=500)
    source: BillSource = BillSource.screenshot


class BillCandidateUpdate(BaseModel):
    amount: Decimal | None = Field(default=None, gt=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    merchant: str | None = Field(default=None, min_length=1, max_length=120)
    category: str | None = Field(default=None, min_length=1, max_length=40)
    payment_method: str | None = Field(default=None, max_length=40)
    paid_at: datetime | None = None
    transaction_type: TransactionType | None = None
    note: str | None = Field(default=None, max_length=500)
    source: BillSource | None = None


class ParseBillResponse(BaseModel):
    candidate_id: UUID
    intent: str = "create_bill"
    confidence: float = Field(ge=0, le=1)
    data: BillCandidateData
    field_confidence: dict[str, float]
    warnings: list[str]
    need_user_confirmation: bool = True
