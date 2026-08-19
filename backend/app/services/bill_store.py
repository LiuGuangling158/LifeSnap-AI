from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from math import ceil
from uuid import UUID, uuid4

from app.core.config import settings
from app.schemas.bill import (
    BillStatisticsOverview,
    BillSource,
    BillCreate,
    BillListResponse,
    BillRead,
    BillUpdate,
    CategoryBreakdown,
    DailyBillStatistics,
    DuplicateBillCheckResponse,
    DuplicateBillMatch,
    MerchantBreakdown,
    MonthlyBillStatistics,
    MonthlyBillTrendItem,
    TransactionType,
)


class LocalBillStore:
    def __init__(self) -> None:
        self._bills: dict[UUID, BillRead] = {}
        self._load()

    def create(self, payload: BillCreate) -> BillRead:
        now = datetime.now(timezone.utc)
        bill = BillRead(
            id=uuid4(),
            created_at=now,
            updated_at=now,
            deleted_at=None,
            paid_at=payload.paid_at or now,
            **payload.model_dump(exclude={"paid_at"}),
        )
        self._bills[bill.id] = bill
        self._persist()
        return bill

    def list(
        self,
        year: int | None = None,
        month: int | None = None,
        category: str | None = None,
        transaction_type: TransactionType | None = None,
        source: BillSource | None = None,
        keyword: str | None = None,
        paid_from: datetime | None = None,
        paid_to: datetime | None = None,
        include_deleted: bool = False,
        deleted_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> BillListResponse:
        bills = self.all(
            include_deleted=include_deleted,
            deleted_only=deleted_only,
        )
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
        if paid_from is not None:
            paid_from_utc = self._as_utc(paid_from)
            bills = [bill for bill in bills if self._as_utc(bill.paid_at) >= paid_from_utc]
        if paid_to is not None:
            paid_to_utc = self._as_utc(paid_to)
            bills = [bill for bill in bills if self._as_utc(bill.paid_at) <= paid_to_utc]

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

    def get(self, bill_id: UUID, include_deleted: bool = False) -> BillRead | None:
        bill = self._bills.get(bill_id)
        if bill is None:
            return None
        if bill.deleted_at is not None and not include_deleted:
            return None
        return bill

    def all(
        self,
        include_deleted: bool = False,
        deleted_only: bool = False,
    ) -> list[BillRead]:
        bills = list(self._bills.values())
        if deleted_only:
            return [bill for bill in bills if bill.deleted_at is not None]
        if include_deleted:
            return bills
        return [bill for bill in bills if bill.deleted_at is None]

    def deleted_count(self) -> int:
        return len(self.all(deleted_only=True))

    def update(self, bill_id: UUID, payload: BillUpdate) -> BillRead | None:
        existing = self.get(bill_id)
        if existing is None:
            return None

        data = existing.model_dump()
        data.update(payload.model_dump(exclude_none=True, exclude_unset=True))
        data["updated_at"] = datetime.now(timezone.utc)

        updated = BillRead(**data)
        self._bills[bill_id] = updated
        self._persist()
        return updated

    def delete(self, bill_id: UUID) -> bool:
        existing = self._bills.get(bill_id)
        if existing is None:
            return False

        if existing.deleted_at is None:
            now = datetime.now(timezone.utc)
            data = existing.model_dump()
            data["updated_at"] = now
            data["deleted_at"] = now
            self._bills[bill_id] = BillRead(**data)
            self._persist()
        return True

    def restore(self, bill_id: UUID) -> BillRead | None:
        existing = self._bills.get(bill_id)
        if existing is None:
            return None
        if existing.deleted_at is None:
            return existing

        data = existing.model_dump()
        data["updated_at"] = datetime.now(timezone.utc)
        data["deleted_at"] = None
        restored = BillRead(**data)
        self._bills[bill_id] = restored
        self._persist()
        return restored

    def clear(self) -> int:
        count = len(self._bills)
        self._bills.clear()
        self._persist()
        return count

    def upsert_many(self, bills: list[BillRead]) -> int:
        for bill in bills:
            self._bills[bill.id] = bill
        self._persist()
        return len(bills)

    def check_duplicate(
        self,
        payload: BillCreate,
        time_window_minutes: int = 10,
    ) -> DuplicateBillCheckResponse:
        target_paid_at = self._as_utc(payload.paid_at or datetime.now(timezone.utc))
        time_window = timedelta(minutes=time_window_minutes)
        matches: list[DuplicateBillMatch] = []

        for bill in self.all():
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
        monthly_bills = self._bills_for_month(year, month)
        totals = self._totals(monthly_bills)
        category_breakdown = self._category_breakdown(monthly_bills, totals["total_expense"])
        return MonthlyBillStatistics(
            year=year,
            month=month,
            bill_count=len(monthly_bills),
            total_expense=totals["total_expense"],
            total_income=totals["total_income"],
            total_refund=totals["total_refund"],
            net_amount=totals["net_amount"],
            category_breakdown=category_breakdown,
        )

    def statistics_overview(
        self,
        year: int,
        month: int,
        trend_months: int = 6,
        top_merchant_limit: int = 5,
    ) -> BillStatisticsOverview:
        monthly_bills = self._bills_for_month(year, month)
        return BillStatisticsOverview(
            generated_at=datetime.now(timezone.utc),
            year=year,
            month=month,
            monthly_statistics=self.monthly_statistics(year, month),
            daily_breakdown=self._daily_breakdown(year, month, monthly_bills),
            monthly_trend=self._monthly_trend(year, month, trend_months),
            top_merchants=self._top_merchants(monthly_bills, top_merchant_limit),
        )

    def _bills_for_month(self, year: int, month: int) -> list[BillRead]:
        return [
            bill
            for bill in self.all()
            if bill.paid_at.year == year and bill.paid_at.month == month
        ]

    def _totals(self, bills: list[BillRead]) -> dict[str, Decimal]:
        total_expense = Decimal("0")
        total_income = Decimal("0")
        total_refund = Decimal("0")

        for bill in bills:
            if bill.transaction_type == TransactionType.expense:
                total_expense += bill.amount
            elif bill.transaction_type == TransactionType.income:
                total_income += bill.amount
            elif bill.transaction_type == TransactionType.refund:
                total_refund += bill.amount

        return {
            "total_expense": total_expense,
            "total_income": total_income,
            "total_refund": total_refund,
            "net_amount": total_income + total_refund - total_expense,
        }

    def _category_breakdown(
        self,
        bills: list[BillRead],
        total_expense: Decimal,
    ) -> list[CategoryBreakdown]:
        category_amounts: dict[str, Decimal] = {}
        category_counts: dict[str, int] = {}
        for bill in bills:
            if bill.transaction_type != TransactionType.expense:
                continue
            category_amounts[bill.category] = (
                category_amounts.get(bill.category, Decimal("0")) + bill.amount
            )
            category_counts[bill.category] = category_counts.get(bill.category, 0) + 1

        category_breakdown = [
            CategoryBreakdown(
                category=category,
                amount=amount,
                count=category_counts[category],
                percentage=self._percentage(amount, total_expense),
            )
            for category, amount in category_amounts.items()
        ]
        category_breakdown.sort(key=lambda item: item.amount, reverse=True)
        return category_breakdown

    def _daily_breakdown(
        self,
        year: int,
        month: int,
        bills: list[BillRead],
    ) -> list[DailyBillStatistics]:
        days = self._days_in_month(year, month)
        bills_by_date: dict[date, list[BillRead]] = {}
        for bill in bills:
            paid_date = bill.paid_at.date()
            bills_by_date.setdefault(paid_date, []).append(bill)

        breakdown: list[DailyBillStatistics] = []
        for day in range(1, days + 1):
            current_date = date(year, month, day)
            daily_bills = bills_by_date.get(current_date, [])
            totals = self._totals(daily_bills)
            breakdown.append(
                DailyBillStatistics(
                    date=current_date,
                    bill_count=len(daily_bills),
                    total_expense=totals["total_expense"],
                    total_income=totals["total_income"],
                    total_refund=totals["total_refund"],
                    net_amount=totals["net_amount"],
                )
            )
        return breakdown

    def _monthly_trend(
        self,
        year: int,
        month: int,
        trend_months: int,
    ) -> list[MonthlyBillTrendItem]:
        trend: list[MonthlyBillTrendItem] = []
        for trend_year, trend_month in self._month_sequence(year, month, trend_months):
            bills = self._bills_for_month(trend_year, trend_month)
            totals = self._totals(bills)
            trend.append(
                MonthlyBillTrendItem(
                    year=trend_year,
                    month=trend_month,
                    bill_count=len(bills),
                    total_expense=totals["total_expense"],
                    total_income=totals["total_income"],
                    total_refund=totals["total_refund"],
                    net_amount=totals["net_amount"],
                )
            )
        return trend

    def _top_merchants(
        self,
        bills: list[BillRead],
        limit: int,
    ) -> list[MerchantBreakdown]:
        merchant_amounts: dict[str, Decimal] = {}
        merchant_counts: dict[str, int] = {}
        for bill in bills:
            if bill.transaction_type != TransactionType.expense:
                continue
            merchant_amounts[bill.merchant] = (
                merchant_amounts.get(bill.merchant, Decimal("0")) + bill.amount
            )
            merchant_counts[bill.merchant] = merchant_counts.get(bill.merchant, 0) + 1

        total_expense = sum(merchant_amounts.values(), Decimal("0"))
        merchants = [
            MerchantBreakdown(
                merchant=merchant,
                amount=amount,
                count=merchant_counts[merchant],
                percentage=self._percentage(amount, total_expense),
            )
            for merchant, amount in merchant_amounts.items()
        ]
        merchants.sort(key=lambda item: item.amount, reverse=True)
        return merchants[:limit]

    def _percentage(self, amount: Decimal, total: Decimal) -> Decimal:
        if total == 0:
            return Decimal("0")
        return ((amount / total) * Decimal("100")).quantize(Decimal("0.01"))

    def _days_in_month(self, year: int, month: int) -> int:
        if month == 12:
            next_month = date(year + 1, 1, 1)
        else:
            next_month = date(year, month + 1, 1)
        return (next_month - date(year, month, 1)).days

    def _month_sequence(
        self,
        year: int,
        month: int,
        count: int,
    ) -> list[tuple[int, int]]:
        month_index = year * 12 + (month - 1)
        start_index = month_index - count + 1
        return [
            (index // 12, index % 12 + 1)
            for index in range(start_index, month_index + 1)
        ]

    def _as_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _load(self) -> None:
        path = settings.local_bill_path
        if not path.exists():
            return
        try:
            raw_items = json.loads(path.read_text(encoding="utf-8"))
            bills = [BillRead.model_validate(item) for item in raw_items]
        except (OSError, ValueError, TypeError):
            return
        self._bills = {bill.id: bill for bill in bills}

    def _persist(self) -> None:
        path = settings.local_bill_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(
                [
                    bill.model_dump(mode="json")
                    for bill in sorted(
                        self._bills.values(),
                        key=lambda item: (item.paid_at, item.created_at),
                        reverse=True,
                    )
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temp_path.replace(path)


bill_store = LocalBillStore()
