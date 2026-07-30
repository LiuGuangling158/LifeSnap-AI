from uuid import UUID

from app.schemas.agent import ParseBillResponse
from app.schemas.bill import BillCreate, BillRead
from app.services.bill_store import bill_store


class InMemoryBillCandidateStore:
    def __init__(self) -> None:
        self._candidates: dict[UUID, ParseBillResponse] = {}

    def save(self, candidate: ParseBillResponse) -> ParseBillResponse:
        self._candidates[candidate.candidate_id] = candidate
        return candidate

    def get(self, candidate_id: UUID) -> ParseBillResponse | None:
        return self._candidates.get(candidate_id)

    def confirm(self, candidate_id: UUID) -> BillRead | None:
        candidate = self.get(candidate_id)
        if candidate is None:
            return None
        if not self.is_confirmable(candidate):
            return None

        amount = candidate.data.amount
        merchant = candidate.data.merchant
        if amount is None or merchant is None:
            return None

        bill = bill_store.create(
            BillCreate(
                amount=amount,
                currency=candidate.data.currency,
                merchant=merchant,
                category=candidate.data.category,
                payment_method=candidate.data.payment_method,
                transaction_type=candidate.data.transaction_type,
                paid_at=candidate.data.paid_at,
                note=candidate.data.note,
                source=candidate.data.source,
            )
        )
        del self._candidates[candidate_id]
        return bill

    def is_confirmable(self, candidate: ParseBillResponse) -> bool:
        return candidate.data.amount is not None and candidate.data.merchant is not None


bill_candidate_store = InMemoryBillCandidateStore()
