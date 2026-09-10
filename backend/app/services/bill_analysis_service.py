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
    previous_period_label: str
    previous_total_expense: Decimal
    expense_delta: Decimal
    expense_delta_percentage: Decimal | None
    previous_category_amount: Decimal | None
    category_delta: Decimal | None
    category_delta_percentage: Decimal | None
    budget_amount: Decimal
    budget_usage_percentage: Decimal
    budget_remaining: Decimal
    budget_warning_threshold_percent: int
    top_category: str | None
    top_category_amount: Decimal | None
    top_merchant: str | None
    top_merchant_amount: Decimal | None
    top_day: date | None
    top_day_expense: Decimal | None
    comparison_requested: bool
    budget_requested: bool
    detailed_requested: bool


class BillAnalysisService:
    def analyze(self, text: str) -> BillAnalysisResult:
        year, month, period_label = self._resolve_month(text)
        category = self._resolve_category(text)
        overview = bill_store.statistics_overview(year, month, trend_months=6, top_merchant_limit=5)
        monthly = overview.monthly_statistics
        previous_year, previous_month, previous_period_label = self._previous_month(year, month)
        previous_monthly = bill_store.monthly_statistics(previous_year, previous_month)

        matched_category = None
        if category is not None:
            for item in monthly.category_breakdown:
                if item.category.casefold() == category.casefold():
                    matched_category = item
                    break

        previous_category = None
        if category is not None:
            for item in previous_monthly.category_breakdown:
                if item.category.casefold() == category.casefold():
                    previous_category = item
                    break

        top_category = monthly.category_breakdown[0] if monthly.category_breakdown else None
        top_merchant = overview.top_merchants[0] if overview.top_merchants else None
        top_day = max(
            (item for item in overview.daily_breakdown if item.total_expense > 0),
            key=lambda item: item.total_expense,
            default=None,
        )
        budget_settings = settings_store.get_budget_settings()
        category_amount = matched_category.amount if matched_category else None
        previous_category_amount = previous_category.amount if previous_category else None
        category_delta = None
        if category is not None:
            category_delta = (category_amount or Decimal("0")) - (previous_category_amount or Decimal("0"))
        expense_delta = monthly.total_expense - previous_monthly.total_expense
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
            category_amount=category_amount,
            category_count=matched_category.count if matched_category else None,
            category_percentage=matched_category.percentage if matched_category else None,
            previous_period_label=previous_period_label,
            previous_total_expense=previous_monthly.total_expense,
            expense_delta=expense_delta,
            expense_delta_percentage=self._delta_percentage(expense_delta, previous_monthly.total_expense),
            previous_category_amount=previous_category_amount,
            category_delta=category_delta,
            category_delta_percentage=self._delta_percentage(
                category_delta or Decimal("0"),
                previous_category_amount or Decimal("0"),
            )
            if category is not None
            else None,
            budget_amount=budget_settings.monthly_budget,
            budget_usage_percentage=self._percentage(monthly.total_expense, budget_settings.monthly_budget),
            budget_remaining=budget_settings.monthly_budget - monthly.total_expense,
            budget_warning_threshold_percent=budget_settings.warning_threshold_percent,
            top_category=top_category.category if top_category else None,
            top_category_amount=top_category.amount if top_category else None,
            top_merchant=top_merchant.merchant if top_merchant else None,
            top_merchant_amount=top_merchant.amount if top_merchant else None,
            top_day=top_day.date if top_day else None,
            top_day_expense=top_day.total_expense if top_day else None,
            comparison_requested=self._comparison_requested(text),
            budget_requested=self._budget_requested(text),
            detailed_requested=self._detailed_requested(text),
        )

    def reply(self, result: BillAnalysisResult) -> str:
        if result.bill_count == 0:
            reply = f"{result.period_label}还没有保存的账单数据。先记录几笔后，我就能分析支出、收入、分类占比和商户排行。"
            if result.budget_requested or result.detailed_requested:
                reply += f"当前月预算是 {self._money_text(result.budget_amount)}，还没有使用记录。"
            return reply

        if result.category:
            category_amount = result.category_amount or Decimal("0")
            category_count = result.category_count or 0
            percentage = result.category_percentage or Decimal("0")
            sentences = [
                f"{result.period_label}{result.category}支出 {self._money_text(category_amount)}，"
                f"共 {category_count} 笔，占本月总支出 {percentage}%。"
                f"本月全部支出是 {self._money_text(result.total_expense)}，"
                f"收入 {self._money_text(result.total_income)}，净额 {self._money_text(result.net_amount)}。"
            ]
            if result.comparison_requested or result.detailed_requested:
                sentences.append(
                    self._change_text(
                        f"{result.category}支出",
                        category_amount,
                        result.previous_category_amount or Decimal("0"),
                        result.category_delta or Decimal("0"),
                        result.category_delta_percentage,
                        result.previous_period_label,
                    )
                )
            if result.budget_requested or result.detailed_requested:
                sentences.append(self._budget_text(result))
            return "".join(sentences)

        highlights = []
        if result.top_category and result.top_category_amount is not None:
            highlights.append(f"最大分类是 {result.top_category}（{self._money_text(result.top_category_amount)}）")
        if result.top_merchant and result.top_merchant_amount is not None:
            highlights.append(f"最高商户是 {result.top_merchant}（{self._money_text(result.top_merchant_amount)}）")
        highlight_text = "；" + "，".join(highlights) if highlights else ""
        sentences = [
            f"{result.period_label}共有 {result.bill_count} 笔账单，"
            f"支出 {self._money_text(result.total_expense)}，"
            f"收入 {self._money_text(result.total_income)}，"
            f"退款 {self._money_text(result.total_refund)}，"
            f"净额 {self._money_text(result.net_amount)}{highlight_text}。"
        ]
        if result.comparison_requested or result.detailed_requested:
            sentences.append(
                self._change_text(
                    "总支出",
                    result.total_expense,
                    result.previous_total_expense,
                    result.expense_delta,
                    result.expense_delta_percentage,
                    result.previous_period_label,
                )
            )
        if result.top_day and result.top_day_expense is not None and result.detailed_requested:
            sentences.append(
                f"单日支出最高是 {result.top_day.month}月{result.top_day.day}日，{self._money_text(result.top_day_expense)}。"
            )
        if result.budget_requested or result.detailed_requested:
            sentences.append(self._budget_text(result))
        return "".join(sentences)

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

    def _previous_month(self, year: int, month: int) -> tuple[int, int, str]:
        month_index = year * 12 + month - 2
        previous_year = month_index // 12
        previous_month = month_index % 12 + 1
        return previous_year, previous_month, f"{previous_year}年{previous_month}月"

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

    def _percentage(self, amount: Decimal, total: Decimal) -> Decimal:
        if total <= 0:
            return Decimal("0")
        return ((amount / total) * Decimal("100")).quantize(Decimal("0.01"))

    def _delta_percentage(self, delta: Decimal, previous: Decimal) -> Decimal | None:
        if previous == 0:
            return None
        return ((delta / previous) * Decimal("100")).quantize(Decimal("0.01"))

    def _comparison_requested(self, text: str) -> bool:
        return any(keyword in text for keyword in ("趋势", "环比", "比上月", "比上个月", "对比", "相比", "变化", "多了吗", "少了吗"))

    def _budget_requested(self, text: str) -> bool:
        return any(keyword in text for keyword in ("预算", "超支", "剩余", "还剩", "花超", "用掉"))

    def _detailed_requested(self, text: str) -> bool:
        return any(keyword in text for keyword in ("分析", "统计", "情况", "概览", "总结", "排行", "最多", "最大", "花在哪里"))

    def _change_text(
        self,
        subject: str,
        current: Decimal,
        previous: Decimal,
        delta: Decimal,
        delta_percentage: Decimal | None,
        previous_period_label: str,
    ) -> str:
        if previous == 0:
            if current == 0:
                return f"与{previous_period_label}相比，{subject}没有变化。"
            return f"{previous_period_label}没有{subject}记录，本期新增 {self._money_text(current)}。"
        if delta == 0:
            return f"较{previous_period_label}{subject}持平。"
        direction = "多" if delta > 0 else "少"
        percentage = f"（{abs(delta_percentage or Decimal('0'))}%）" if delta_percentage is not None else ""
        return f"较{previous_period_label}{subject}{direction} {self._money_text(abs(delta))}{percentage}。"

    def _budget_text(self, result: BillAnalysisResult) -> str:
        if result.budget_amount <= 0:
            return "还没有设置月预算。"
        if result.budget_remaining >= 0:
            warning = "已接近预算线。" if result.budget_usage_percentage >= result.budget_warning_threshold_percent else ""
            return (
                f"月预算 {self._money_text(result.budget_amount)}，"
                f"已用 {result.budget_usage_percentage}%，剩余 {self._money_text(result.budget_remaining)}。"
                f"{warning}"
            )
        return (
            f"月预算 {self._money_text(result.budget_amount)}，"
            f"已用 {result.budget_usage_percentage}%，已超出 {self._money_text(abs(result.budget_remaining))}。"
        )


bill_analysis_service = BillAnalysisService()
