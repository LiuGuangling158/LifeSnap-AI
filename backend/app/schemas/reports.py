from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.bill import (
    CategoryBreakdown,
    MerchantBreakdown,
    MonthlyBillStatistics,
    MonthlyBillTrendItem,
)


class BudgetRuleStatus(BaseModel):
    category: str
    budget: Decimal
    spent: Decimal
    remaining: Decimal
    usage_percentage: Decimal
    status: str


class ReportAlert(BaseModel):
    alert_id: str
    severity: str
    title: str
    message: str
    category: str | None = None


class SpendingAnomaly(BaseModel):
    anomaly_id: str
    kind: str
    title: str
    message: str
    amount: Decimal
    occurred_on: date
    bill_id: UUID | None = None


class MonthlyFinanceReport(BaseModel):
    generated_at: datetime
    year: int
    month: int
    monthly_statistics: MonthlyBillStatistics
    monthly_trend: list[MonthlyBillTrendItem] = Field(default_factory=list)
    top_merchants: list[MerchantBreakdown] = Field(default_factory=list)
    category_breakdown: list[CategoryBreakdown] = Field(default_factory=list)
    monthly_budget: Decimal
    budget_usage_percentage: Decimal
    budget_remaining: Decimal
    warning_threshold_percent: int
    category_budget_statuses: list[BudgetRuleStatus] = Field(default_factory=list)
    alerts: list[ReportAlert] = Field(default_factory=list)
    anomalies: list[SpendingAnomaly] = Field(default_factory=list)
    insights: list[str] = Field(default_factory=list)
