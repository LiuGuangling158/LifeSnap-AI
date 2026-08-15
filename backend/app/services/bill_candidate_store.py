from __future__ import annotations

import json
from uuid import UUID

from app.core.config import settings
from app.schemas.agent import BillCandidateData, BillCandidateUpdate, ParseBillResponse
from app.schemas.bill import BillCreate, BillRead
from app.services.bill_store import bill_store


class LocalBillCandidateStore:
    def __init__(self) -> None:
        self._candidates: dict[UUID, ParseBillResponse] = {}
        self._load()

    def save(self, candidate: ParseBillResponse) -> ParseBillResponse:
        self._candidates[candidate.candidate_id] = candidate
        self._persist()
        return candidate

    def get(self, candidate_id: UUID) -> ParseBillResponse | None:
        return self._candidates.get(candidate_id)

    def all(self) -> list[ParseBillResponse]:
        return list(self._candidates.values())

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
        payload = self.to_bill_create(candidate)
        if payload is None:
            return None

        bill = bill_store.create(payload)
        del self._candidates[candidate_id]
        self._persist()
        return bill

    def delete(self, candidate_id: UUID) -> bool:
        if candidate_id not in self._candidates:
            return False
        del self._candidates[candidate_id]
        self._persist()
        return True

    def is_confirmable(self, candidate: ParseBillResponse) -> bool:
        return candidate.data.amount is not None and candidate.data.merchant is not None

    def to_bill_create(self, candidate: ParseBillResponse) -> BillCreate | None:
        amount = candidate.data.amount
        merchant = candidate.data.merchant
        if amount is None or merchant is None:
            return None

        return BillCreate(
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

    def clear(self) -> int:
        count = len(self._candidates)
        self._candidates.clear()
        self._persist()
        return count

    def upsert_many(self, candidates: list[ParseBillResponse]) -> int:
        for candidate in candidates:
            self._candidates[candidate.candidate_id] = candidate
        self._persist()
        return len(candidates)

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

    def _load(self) -> None:
        path = settings.local_bill_candidate_path
        if not path.exists():
            return
        try:
            raw_items = json.loads(path.read_text(encoding="utf-8"))
            candidates = [ParseBillResponse.model_validate(item) for item in raw_items]
        except (OSError, ValueError, TypeError):
            return
        self._candidates = {candidate.candidate_id: candidate for candidate in candidates}

    def _persist(self) -> None:
        path = settings.local_bill_candidate_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(
                [
                    candidate.model_dump(mode="json")
                    for candidate in sorted(
                        self._candidates.values(),
                        key=lambda item: str(item.candidate_id),
                    )
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temp_path.replace(path)


bill_candidate_store = LocalBillCandidateStore()
