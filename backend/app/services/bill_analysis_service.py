from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.schemas.bill import TransactionType
from app.services.bill_category_classifier import bill_category_classifier
from app.services.bill_store import bill_store
from app.services.settings_store import settings_store


@dataclass(frozen=True)
class BillAnalysisResult:
    year: int
    month: int
    period_label: str
    category: str | None
    bill_count: int
    total_expense: Decimal
    total_income: Decimal
    total_refund: Decimal
    net_amount: Decimal
    category_amount: Decimal | None
    category_count: int | None
    category_percentage: Decimal | None
    top_category: str | None
    top_category_amount: Decimal | None
    top_merchant: str | None
    top_merchant_amount: Decimal | None


class BillAnalysisService:
    def analyze(self, text: str) -> BillAnalysisResult:
        year, month, period_label = self._resolve_month(text)
        category = self._resolve_category(text)
        overview = bill_store.statistics_overview(year, month, trend_months=6, top_merchant_limit=5)
        monthly = overview.monthly_statistics

        matched_category = None
        if category is not None:
            for item in monthly.category_breakdown:
                if item.category.casefold() == category.casefold():
                    matched_category = item
                    break

        top_category = monthly.category_breakdown[0] if monthly.category_breakdown else None
        top_merchant = overview.top_merchants[0] if overview.top_merchants else None
        return BillAnalysisResult(
            year=year,
            month=month,
            period_label=period_label,
            category=category,
            bill_count=monthly.bill_count,
            total_expense=monthly.total_expense,
            total_income=monthly.total_income,
            total_refund=monthly.total_refund,
            net_amount=monthly.net_amount,
            category_amount=matched_category.amount if matched_category else None,
            category_count=matched_category.count if matched_category else None,
            category_percentage=matched_category.percentage if matched_category else None,
            top_category=top_category.category if top_category else None,
            top_category_amount=top_category.amount if top_category else None,
            top_merchant=top_merchant.merchant if top_merchant else None,
            top_merchant_amount=top_merchant.amount if top_merchant else None,
        )

    def reply(self, result: BillAnalysisResult) -> str:
        if result.bill_count == 0:
            return f"{result.period_label}还没有保存的账单数据。先记录几笔后，我就能分析支出、收入、分类占比和商户排行。"

        if result.category:
            category_amount = result.category_amount or Decimal("0")
            category_count = result.category_count or 0
            percentage = result.category_percentage or Decimal("0")
            return (
                f"{result.period_label}{result.category}支出 {self._money_text(category_amount)}，"
                f"共 {category_count} 笔，占本月总支出 {percentage}%。"
                f"本月全部支出是 {self._money_text(result.total_expense)}，"
                f"收入 {self._money_text(result.total_income)}，净额 {self._money_text(result.net_amount)}。"
            )

        highlights = []
        if result.top_category and result.top_category_amount is not None:
            highlights.append(f"最大分类是 {result.top_category}（{self._money_text(result.top_category_amount)}）")
        if result.top_merchant and result.top_merchant_amount is not None:
            highlights.append(f"最高商户是 {result.top_merchant}（{self._money_text(result.top_merchant_amount)}）")
        highlight_text = "；" + "，".join(highlights) if highlights else ""
        return (
            f"{result.period_label}共有 {result.bill_count} 笔账单，"
            f"支出 {self._money_text(result.total_expense)}，"
            f"收入 {self._money_text(result.total_income)}，"
            f"退款 {self._money_text(result.total_refund)}，"
            f"净额 {self._money_text(result.net_amount)}{highlight_text}。"
        )

    def trace_summary(self, result: BillAnalysisResult) -> str:
        category = result.category or "全部分类"
        amount = result.category_amount if result.category else result.total_expense
        count = result.category_count if result.category else result.bill_count
        return (
            f"{result.period_label}{category}: "
            f"支出 {self._money_text(amount or Decimal('0'))}, {count or 0} 笔"
        )

    def _resolve_month(self, text: str) -> tuple[int, int, str]:
        today = date.today()
        if "上个月" in text or "上月" in text:
            month_index = today.year * 12 + today.month - 2
            year = month_index // 12
            month = month_index % 12 + 1
            return year, month, f"{year}年{month}月"

        match = re.search(r"(?:(20\d{2})\s*年\s*)?([1-9]|1[0-2])\s*月", text)
        if match:
            year = int(match.group(1)) if match.group(1) else today.year
            month = int(match.group(2))
            return year, month, f"{year}年{month}月"

        return today.year, today.month, f"{today.year}年{today.month}月"

    def _resolve_category(self, text: str) -> str | None:
        folded = text.casefold()
        categories = [
            *settings_store.get_category_settings().bill_categories,
            *(bill.category for bill in bill_store.all()),
        ]
        for category in sorted({item for item in categories if item and item != "其他"}, key=len, reverse=True):
            if category.casefold() in folded:
                return category

        match = bill_category_classifier.classify(text, TransactionType.expense)
        if match.confidence >= 0.7 and match.category != "其他":
            return match.category
        return None

    def _money_text(self, value: Decimal) -> str:
        return f"{value.quantize(Decimal('0.01'))} 元"


bill_analysis_service = BillAnalysisService()
