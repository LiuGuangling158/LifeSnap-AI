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
    trace_id: str | None = Field(default=None, max_length=80)
    trace_snapshot: dict[str, str | None] = Field(default_factory=dict)
    review_status: Literal["pending", "promoted", "dismissed"] = "pending"
    review_note: str | None = Field(default=None, max_length=500)
    reviewed_at: datetime | None = None
    promoted_case_id: str | None = Field(default=None, max_length=80)


class AgentQualityFeedbackReviewRequest(BaseModel):
    disposition: Literal["promote", "dismiss"]
    evaluation_prompt: str | None = Field(default=None, max_length=500)
    expected_intent: str | None = Field(default=None, max_length=80)
    expected_category: str | None = Field(default=None, max_length=80)
    review_note: str | None = Field(default=None, max_length=500)


class AgentQualityFeedbackListResponse(BaseModel):
    generated_at: datetime
    total: int = Field(ge=0)
    items: list[AgentQualityFeedbackRead] = Field(default_factory=list)


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
    latency_ms: float | None = Field(default=None, ge=0)
    model_strategy: str | None = Field(default=None, max_length=120)
    external_model_ready: bool | None = None


class RagQualityEvaluationCase(BaseModel):
    case_id: str
    passed: bool
    expected_source_ids: list[str] = Field(default_factory=list)
    actual_source_ids: list[str] = Field(default_factory=list)
    expected_top_source_id: str | None = None
    actual_top_source_id: str | None = None
    expected_no_hit: bool = False
    recall_at_k: float | None = Field(default=None, ge=0, le=1)
    citation_correct: bool | None = None
    abstention_correct: bool | None = None
    critical: bool = False
    retrieval_method: str | None = Field(default=None, max_length=120)
    latency_ms: float | None = Field(default=None, ge=0)


class RagQualityEvaluationSummary(BaseModel):
    dataset_id: str = Field(default="rag-retrieval", min_length=1, max_length=80)
    dataset_version: str = Field(default="v1", min_length=1, max_length=40)
    policy_id: str = Field(default="rag-retrieval-v1", min_length=1, max_length=80)
    top_k: int = Field(default=3, ge=1, le=10)
    total_cases: int = Field(default=0, ge=0)
    passed_cases: int = Field(default=0, ge=0)
    pass_rate: float = Field(default=0, ge=0, le=1)
    recall_at_k: float | None = Field(default=None, ge=0, le=1)
    citation_accuracy: float | None = Field(default=None, ge=0, le=1)
    abstention_accuracy: float | None = Field(default=None, ge=0, le=1)
    critical_case_count: int = Field(default=0, ge=0)
    failed_critical_case_ids: list[str] = Field(default_factory=list)
    cases: list[RagQualityEvaluationCase] = Field(default_factory=list)


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
    duration_ms: float | None = Field(default=None, ge=0)
    online_model_ready: bool | None = None
    online_model_provider: str | None = Field(default=None, max_length=80)
    online_model: str | None = Field(default=None, max_length=160)
    admission: AgentQualityAdmission = Field(default_factory=AgentQualityAdmission)
    regression: AgentQualityRegression = Field(default_factory=AgentQualityRegression)
    rag_evaluation: RagQualityEvaluationSummary | None = None


class AgentQualitySummary(BaseModel):
    generated_at: datetime
    feedback_count: int
    accepted_count: int
    corrected_count: int
    rejected_count: int
    pending_feedback_count: int = Field(default=0, ge=0)
    promoted_feedback_case_count: int = Field(default=0, ge=0)
    acceptance_rate: float | None = None
    correction_rate: float | None = None
    latest_evaluation: AgentQualityEvaluationRun | None = None
    latest_live_evaluation: AgentQualityEvaluationRun | None = None
    recent_evaluations: list[AgentQualityEvaluationRun] = Field(default_factory=list)
