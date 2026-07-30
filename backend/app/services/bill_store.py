from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

from app.schemas.bill import (
    BillCreate,
    BillRead,
    BillUpdate,
    CategoryBreakdown,
    MonthlyBillStatistics,
    TransactionType,
)


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

    def list(self, year: int | None = None, month: int | None = None) -> list[BillRead]:
        bills = list(self._bills.values())
        if year is not None:
            bills = [bill for bill in bills if bill.paid_at.year == year]
        if month is not None:
            bills = [bill for bill in bills if bill.paid_at.month == month]

        return sorted(bills, key=lambda bill: bill.paid_at, reverse=True)

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

    def delete(self, bill_id: UUID) -> bool:
        if bill_id not in self._bills:
            return False

        del self._bills[bill_id]
        return True

    def monthly_statistics(self, year: int, month: int) -> MonthlyBillStatistics:
        monthly_bills = [
            bill
            for bill in self._bills.values()
            if bill.paid_at.year == year and bill.paid_at.month == month
        ]

        total_expense = Decimal("0")
        total_income = Decimal("0")
        total_refund = Decimal("0")
        category_amounts: dict[str, Decimal] = {}
        category_counts: dict[str, int] = {}

        for bill in monthly_bills:
            if bill.transaction_type == TransactionType.expense:
                total_expense += bill.amount
                category_amounts[bill.category] = (
                    category_amounts.get(bill.category, Decimal("0")) + bill.amount
                )
                category_counts[bill.category] = category_counts.get(bill.category, 0) + 1
            elif bill.transaction_type == TransactionType.income:
                total_income += bill.amount
            elif bill.transaction_type == TransactionType.refund:
                total_refund += bill.amount

        category_breakdown = [
            CategoryBreakdown(
                category=category,
                amount=amount,
                count=category_counts[category],
            )
            for category, amount in category_amounts.items()
        ]
        category_breakdown.sort(key=lambda item: item.amount, reverse=True)

        return MonthlyBillStatistics(
            year=year,
            month=month,
            bill_count=len(monthly_bills),
            total_expense=total_expense,
            total_income=total_income,
            total_refund=total_refund,
            net_amount=total_income + total_refund - total_expense,
            category_breakdown=category_breakdown,
        )


bill_store = InMemoryBillStore()
