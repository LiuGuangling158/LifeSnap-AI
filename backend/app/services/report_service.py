from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from statistics import median

from app.core.config import settings
from app.schemas.bill import TransactionType
from app.schemas.reports import (
    BudgetRuleStatus,
    MonthlyFinanceReport,
    ReportAlert,
    SpendingAnomaly,
)
from app.services.bill_store import bill_store
from app.services.settings_store import settings_store


class ReportService:
    def monthly_report(self, year: int, month: int) -> MonthlyFinanceReport:
        overview = bill_store.statistics_overview(
            year,
            month,
            trend_months=6,
            top_merchant_limit=6,
        )
        budget = settings_store.get_budget_settings()
        expense = overview.monthly_statistics.total_expense
        usage = self._percentage(expense, budget.monthly_budget)
        category_amounts = {
            item.category: item.amount
            for item in overview.monthly_statistics.category_breakdown
        }
        rule_statuses = self._category_budget_statuses(
            budget.category_budgets,
            category_amounts,
            budget.warning_threshold_percent,
        )
        alerts = self._alerts(
            expense=expense,
            monthly_budget=budget.monthly_budget,
            usage=usage,
            threshold=budget.warning_threshold_percent,
            category_rules=rule_statuses,
        )
        anomalies = self._anomalies(year, month)
        return MonthlyFinanceReport(
            generated_at=datetime.now(timezone.utc),
            year=year,
            month=month,
            monthly_statistics=overview.monthly_statistics,
            monthly_trend=overview.monthly_trend,
            top_merchants=overview.top_merchants,
            category_breakdown=overview.monthly_statistics.category_breakdown,
            monthly_budget=budget.monthly_budget,
            budget_usage_percentage=usage,
            budget_remaining=budget.monthly_budget - expense,
            warning_threshold_percent=budget.warning_threshold_percent,
            category_budget_statuses=rule_statuses,
            alerts=alerts,
            anomalies=anomalies,
            insights=self._insights(overview, usage, budget.monthly_budget, anomalies),
        )

    def _category_budget_statuses(
        self,
        category_budgets: dict[str, Decimal],
        category_amounts: dict[str, Decimal],
        threshold: int,
    ) -> list[BudgetRuleStatus]:
        statuses: list[BudgetRuleStatus] = []
        for category, amount in sorted(category_budgets.items()):
            budget = Decimal(amount)
            spent = category_amounts.get(category, Decimal("0"))
            usage = self._percentage(spent, budget)
            status = "on_track"
            if budget > 0 and usage >= 100:
                status = "over_budget"
            elif budget > 0 and usage >= threshold:
                status = "warning"
            statuses.append(
                BudgetRuleStatus(
                    category=category,
                    budget=budget,
                    spent=spent,
                    remaining=budget - spent,
                    usage_percentage=usage,
                    status=status,
                )
            )
        return statuses

    def _alerts(
        self,
        expense: Decimal,
        monthly_budget: Decimal,
        usage: Decimal,
        threshold: int,
        category_rules: list[BudgetRuleStatus],
    ) -> list[ReportAlert]:
        alerts: list[ReportAlert] = []
        if monthly_budget > 0 and usage >= 100:
            alerts.append(
                ReportAlert(
                    alert_id="monthly-budget-over",
                    severity="critical",
                    title="Monthly budget exceeded",
                    message=f"Expense {expense} exceeds the monthly budget by {expense - monthly_budget}.",
                )
            )
        elif monthly_budget > 0 and usage >= threshold:
            alerts.append(
                ReportAlert(
                    alert_id="monthly-budget-warning",
                    severity="warning",
                    title="Monthly budget warning",
                    message=f"Expense has reached {usage}% of the monthly budget.",
                )
            )
        for rule in category_rules:
            if rule.status == "over_budget":
                alerts.append(
                    ReportAlert(
                        alert_id=f"category-over-{rule.category}",
                        severity="critical",
                        title=f"{rule.category} budget exceeded",
                        message=f"{rule.category} has exceeded its category budget by {abs(rule.remaining)}.",
                        category=rule.category,
                    )
                )
            elif rule.status == "warning":
                alerts.append(
                    ReportAlert(
                        alert_id=f"category-warning-{rule.category}",
                        severity="warning",
                        title=f"{rule.category} budget warning",
                        message=f"{rule.category} has reached {rule.usage_percentage}% of its budget.",
                        category=rule.category,
                    )
                )
        return alerts

    def _anomalies(self, year: int, month: int) -> list[SpendingAnomaly]:
        expenses = [
            bill
            for bill in bill_store.all()
            if bill.transaction_type == TransactionType.expense
            and bill.paid_at.astimezone(settings.business_tzinfo).year == year
            and bill.paid_at.astimezone(settings.business_tzinfo).month == month
        ]
        if len(expenses) < 3:
            return []
        baseline = median([bill.amount for bill in expenses])
        threshold = max(Decimal("100"), baseline * Decimal("3"))
        anomalies: list[SpendingAnomaly] = []
        for bill in sorted(expenses, key=lambda item: item.amount, reverse=True):
            if bill.amount < threshold:
                continue
            local_date = bill.paid_at.astimezone(settings.business_tzinfo).date()
            merchant = bill.merchant or bill.category or "Unspecified merchant"
            anomalies.append(
                SpendingAnomaly(
                    anomaly_id=f"bill-{bill.id}",
                    kind="large_transaction",
                    title="Large expense detected",
                    message=f"{merchant} was {bill.amount}, above the {threshold} local review threshold.",
                    amount=bill.amount,
                    occurred_on=local_date,
                    bill_id=bill.id,
                )
            )
        daily_totals: dict[date, Decimal] = defaultdict(lambda: Decimal("0"))
        for bill in expenses:
            daily_totals[bill.paid_at.astimezone(settings.business_tzinfo).date()] += bill.amount
        average = sum(daily_totals.values(), Decimal("0")) / Decimal(len(daily_totals))
        daily_threshold = max(Decimal("300"), average * Decimal("2"))
        for day, amount in daily_totals.items():
            if amount < daily_threshold:
                continue
            anomalies.append(
                SpendingAnomaly(
                    anomaly_id=f"day-{day.isoformat()}",
                    kind="daily_spike",
                    title="Daily spending spike",
                    message=f"Expense on {day.isoformat()} reached {amount}, above the {daily_threshold} local review threshold.",
                    amount=amount,
                    occurred_on=day,
                )
            )
        return sorted(anomalies, key=lambda item: (item.amount, item.occurred_on), reverse=True)[:6]

    def _insights(self, overview, usage: Decimal, monthly_budget: Decimal, anomalies) -> list[str]:
        insights: list[str] = []
        categories = overview.monthly_statistics.category_breakdown
        if categories:
            top = categories[0]
            insights.append(
                f"Top spending category is {top.category} at {top.amount}, accounting for {top.percentage}% of expense."
            )
        trend = overview.monthly_trend
        if len(trend) >= 2:
            current, previous = trend[-1], trend[-2]
            delta = current.total_expense - previous.total_expense
            direction = "increased" if delta > 0 else "decreased" if delta < 0 else "was unchanged"
            insights.append(
                f"Expense {direction} by {abs(delta)} compared with the previous month."
            )
        if monthly_budget > 0:
            insights.append(f"Monthly budget usage is {usage}%.")
        if anomalies:
            insights.append(f"{len(anomalies)} transaction or daily-spike item(s) need review.")
        return insights

    def _percentage(self, value: Decimal, total: Decimal) -> Decimal:
        if total <= 0:
            return Decimal("0")
        return (value / total * Decimal("100")).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )


report_service = ReportService()
