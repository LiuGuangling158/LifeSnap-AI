from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class TransactionType(str, Enum):
    expense = "expense"
    income = "income"
    refund = "refund"
    transfer = "transfer"
    top_up = "top_up"


class BillSource(str, Enum):
    manual = "manual"
    screenshot = "screenshot"
    album = "album"
    ai_chat = "ai_chat"


class BillCreate(BaseModel):
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="CNY", min_length=3, max_length=3)
    merchant: str = Field(min_length=1, max_length=120)
    category: str = Field(default="其他", min_length=1, max_length=40)
    payment_method: str | None = Field(default=None, max_length=40)
    transaction_type: TransactionType = TransactionType.expense
    paid_at: datetime | None = None
    note: str | None = Field(default=None, max_length=500)
    source: BillSource = BillSource.manual


class BillRead(BillCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime

