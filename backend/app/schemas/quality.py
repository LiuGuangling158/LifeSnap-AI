from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class AgentQualityFeedbackCreate(BaseModel):
    message_id: UUID
    verdict: Literal["accepted", "corrected", "rejected"]
    expected_intent: str | None = Field(default=None, max_length=80)
    expected_category: str | None = Field(default=None, max_length=80)
    note: str | None = Field(default=None, max_length=500)


class AgentQualityFeedbackRead(AgentQualityFeedbackCreate):
    feedback_id: UUID
    created_at: datetime


class AgentQualityAdmission(BaseModel):
    policy_id: str = Field(default="agent-admission-v1", min_length=1, max_length=80)
    dataset_version: str = Field(default="v1", min_length=1, max_length=40)
    minimum_pass_rate: float = Field(default=1.0, ge=0, le=1)
    admitted: bool = False
    critical_case_count: int = Field(default=0, ge=0)
    failed_critical_case_ids: list[str] = Field(default_factory=list)
    failure_reasons: list[str] = Field(default_factory=list)


class AgentQualityRegression(BaseModel):
    """Comparison with the last compatible evaluation baseline."""

    baseline_run_id: UUID | None = None
    baseline_pass_rate: float | None = Field(default=None, ge=0, le=1)
    pass_rate_delta: float | None = Field(default=None, ge=-1, le=1)
    newly_failed_case_ids: list[str] = Field(default_factory=list)
    resolved_case_ids: list[str] = Field(default_factory=list)
    regressed: bool = False


class AgentQualityEvaluationCase(BaseModel):
    case_id: str
    passed: bool
    expected_intent: str
    actual_intent: str
    expected_category: str | None = None
    actual_category: str | None = None
    missing_function_tools: list[str] = Field(default_factory=list)
    critical: bool = False
    expected_confirmation: bool | None = None
    actual_confirmation: bool | None = None


class AgentQualityEvaluationRun(BaseModel):
    run_id: UUID
    created_at: datetime
    total_cases: int
    passed_cases: int
    pass_rate: float
    model_strategy: str
    cases: list[AgentQualityEvaluationCase] = Field(default_factory=list)
    dataset_id: str = Field(default="agent-admission", min_length=1, max_length=80)
    dataset_version: str = Field(default="v1", min_length=1, max_length=40)
    execution_mode: Literal["offline", "live"] = "offline"
    admission: AgentQualityAdmission = Field(default_factory=AgentQualityAdmission)
    regression: AgentQualityRegression = Field(default_factory=AgentQualityRegression)


class AgentQualitySummary(BaseModel):
    generated_at: datetime
    feedback_count: int
    accepted_count: int
    corrected_count: int
    rejected_count: int
    acceptance_rate: float | None = None
    correction_rate: float | None = None
    latest_evaluation: AgentQualityEvaluationRun | None = None
