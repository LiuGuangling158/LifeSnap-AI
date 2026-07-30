from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.schemas.bill import BillCreate, BillRead


class InMemoryBillStore:
    def __init__(self) -> None:
        self._bills: dict[UUID, BillRead] = {}

    def create(self, payload: BillCreate) -> BillRead:
        now = datetime.now(timezone.utc)
        bill = BillRead(
            id=uuid4(),
            created_at=now,
            updated_at=now,
            paid_at=payload.paid_at or now,
            **payload.model_dump(exclude={"paid_at"}),
        )
        self._bills[bill.id] = bill
        return bill

    def list(self) -> list[BillRead]:
        return sorted(self._bills.values(), key=lambda bill: bill.paid_at, reverse=True)


bill_store = InMemoryBillStore()
