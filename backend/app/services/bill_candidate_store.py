from uuid import UUID

from app.schemas.agent import BillCandidateData, BillCandidateUpdate, ParseBillResponse
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

    def update(
        self,
        candidate_id: UUID,
        payload: BillCandidateUpdate,
    ) -> ParseBillResponse | None:
        candidate = self.get(candidate_id)
        if candidate is None:
            return None

        data = candidate.data.model_dump()
        data.update(payload.model_dump(exclude_unset=True))
        candidate.data = BillCandidateData(**data)
        candidate.warnings = self._warnings(candidate.data)
        candidate.field_confidence = self._field_confidence(candidate.data)
        candidate.confidence = self._overall_confidence(candidate.field_confidence)
        return self.save(candidate)

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

    def _warnings(self, data: BillCandidateData) -> list[str]:
        warnings: list[str] = []
        if data.amount is None:
            warnings.append("amount_missing")
        if data.merchant is None:
            warnings.append("merchant_missing")
        if data.payment_method is None:
            warnings.append("payment_method_missing")
        if data.category == "其他":
            warnings.append("category_low_confidence")
        return warnings

    def _field_confidence(self, data: BillCandidateData) -> dict[str, float]:
        return {
            "amount": 1.0 if data.amount is not None else 0.0,
            "merchant": 1.0 if data.merchant is not None else 0.0,
            "category": 0.9 if data.category != "其他" else 0.5,
            "payment_method": 1.0 if data.payment_method is not None else 0.0,
            "paid_at": 1.0 if data.paid_at is not None else 0.0,
        }

    def _overall_confidence(self, field_confidence: dict[str, float]) -> float:
        important_fields = ["amount", "merchant", "category", "payment_method"]
        score = sum(field_confidence[field] for field in important_fields) / len(important_fields)
        return round(score, 2)


bill_candidate_store = InMemoryBillCandidateStore()
