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


class AgentQualityEvaluationCase(BaseModel):
    case_id: str
    passed: bool
    expected_intent: str
    actual_intent: str
    expected_category: str | None = None
    actual_category: str | None = None
    missing_function_tools: list[str] = Field(default_factory=list)


class AgentQualityEvaluationRun(BaseModel):
    run_id: UUID
    created_at: datetime
    total_cases: int
    passed_cases: int
    pass_rate: float
    model_strategy: str
    cases: list[AgentQualityEvaluationCase] = Field(default_factory=list)


class AgentQualitySummary(BaseModel):
    generated_at: datetime
    feedback_count: int
    accepted_count: int
    corrected_count: int
    rejected_count: int
    acceptance_rate: float | None = None
    correction_rate: float | None = None
    latest_evaluation: AgentQualityEvaluationRun | None = None
