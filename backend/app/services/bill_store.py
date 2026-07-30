from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.schemas.bill import BillCreate, BillRead, BillUpdate


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

    def get(self, bill_id: UUID) -> BillRead | None:
        return self._bills.get(bill_id)

    def update(self, bill_id: UUID, payload: BillUpdate) -> BillRead | None:
        existing = self.get(bill_id)
        if existing is None:
            return None

        data = existing.model_dump()
        data.update(payload.model_dump(exclude_none=True, exclude_unset=True))
        data["updated_at"] = datetime.now(timezone.utc)

        updated = BillRead(**data)
        self._bills[bill_id] = updated
        return updated


bill_store = InMemoryBillStore()
