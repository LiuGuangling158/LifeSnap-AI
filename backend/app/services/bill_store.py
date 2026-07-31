from datetime import datetime, timedelta, timezone
from decimal import Decimal
from math import ceil
from uuid import UUID, uuid4

from app.schemas.bill import (
    BillSource,
    BillCreate,
    BillListResponse,
    BillRead,
    BillUpdate,
    CategoryBreakdown,
    DuplicateBillCheckResponse,
    DuplicateBillMatch,
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

    def list(
        self,
        year: int | None = None,
        month: int | None = None,
        category: str | None = None,
        transaction_type: TransactionType | None = None,
        source: BillSource | None = None,
        keyword: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> BillListResponse:
        bills = list(self._bills.values())
        if year is not None:
            bills = [bill for bill in bills if bill.paid_at.year == year]
        if month is not None:
            bills = [bill for bill in bills if bill.paid_at.month == month]
        if category is not None:
            bills = [bill for bill in bills if bill.category == category]
        if transaction_type is not None:
            bills = [bill for bill in bills if bill.transaction_type == transaction_type]
        if source is not None:
            bills = [bill for bill in bills if bill.source == source]
        if keyword is not None:
            normalized_keyword = keyword.casefold()
            bills = [bill for bill in bills if self._matches_keyword(bill, normalized_keyword)]

        sorted_bills = sorted(bills, key=lambda bill: bill.paid_at, reverse=True)
        total = len(sorted_bills)
        start = (page - 1) * page_size
        end = start + page_size

        return BillListResponse(
            items=sorted_bills[start:end],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def _matches_keyword(self, bill: BillRead, keyword: str) -> bool:
        fields = [
            bill.merchant,
            bill.category,
            bill.payment_method or "",
            bill.note or "",
        ]
        return any(keyword in field.casefold() for field in fields)

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

    def check_duplicate(
        self,
        payload: BillCreate,
        time_window_minutes: int = 10,
    ) -> DuplicateBillCheckResponse:
        target_paid_at = self._as_utc(payload.paid_at or datetime.now(timezone.utc))
        time_window = timedelta(minutes=time_window_minutes)
        matches: list[DuplicateBillMatch] = []

        for bill in self._bills.values():
            if bill.amount != payload.amount:
                continue
            if bill.transaction_type != payload.transaction_type:
                continue
            if bill.merchant.casefold() != payload.merchant.casefold():
                continue
            if abs(self._as_utc(bill.paid_at) - target_paid_at) > time_window:
                continue

            matches.append(
                DuplicateBillMatch(
                    bill=bill,
                    reason="same_merchant_amount_type_and_nearby_paid_at",
                )
            )

        return DuplicateBillCheckResponse(
            is_duplicate=bool(matches),
            time_window_minutes=time_window_minutes,
            matches=matches,
        )

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

    def _as_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)


bill_store = InMemoryBillStore()
