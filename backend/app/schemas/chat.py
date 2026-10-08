from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.agent import ParseBillResponse, ParseDiaryResponse, ParseTaskResponse
from app.schemas.agent_runtime import AgentFunctionCallTrace, AgentKnowledgeHit, AgentModelTrace
from app.schemas.bill import BillRead
from app.schemas.diary import DiaryRead
from app.schemas.task import TaskRead


class ChatIntent(str, Enum):
    create_bill = "create_bill"
    create_task = "create_task"
    create_diary = "create_diary"
    diary_reflection = "diary_reflection"
    analyze_bills = "analyze_bills"
    knowledge_answer = "knowledge_answer"
    unsupported = "unsupported"


class ChatActionType(str, Enum):
    bill_candidate = "bill_candidate"
    task_candidate = "task_candidate"
    diary_candidate = "diary_candidate"
    none = "none"


class CandidateSessionStatus(str, Enum):
    active = "active"
    confirmed = "confirmed"
    discarded = "discarded"


class CandidateSessionRead(BaseModel):
    session_id: UUID
    candidate_id: UUID
    action_type: ChatActionType
    revision: int = Field(ge=1)
    status: CandidateSessionStatus
    created_at: datetime
    updated_at: datetime


class ChatAgentStepStatus(str, Enum):
    completed = "completed"
    needs_confirmation = "needs_confirmation"
    blocked = "blocked"


class ChatAgentStep(BaseModel):
    title: str = Field(min_length=1, max_length=40)
    detail: str = Field(min_length=1, max_length=160)
    status: ChatAgentStepStatus = ChatAgentStepStatus.completed


class ChatAgentDecision(str, Enum):
    candidate_ready = "candidate_ready"
    analysis_ready = "analysis_ready"
    answer_ready = "answer_ready"
    reflection_ready = "reflection_ready"
    clarification_needed = "clarification_needed"
    privacy_blocked = "privacy_blocked"
    candidate_updated = "candidate_updated"
    candidate_discarded = "candidate_discarded"
    record_saved = "record_saved"


class ChatAgentReasoningBasis(str, Enum):
    rag_retrieval = "rag_retrieval"
    function_tools = "function_tools"
    external_model = "external_model"
    local_rules = "local_rules"
    privacy_guard = "privacy_guard"
    human_confirmation = "human_confirmation"


class ChatAgentGuardrail(str, Enum):
    confirmation_required = "confirmation_required"
    read_only_response = "read_only_response"
    privacy_blocked = "privacy_blocked"
    local_fallback = "local_fallback"


class ChatAgentExplanation(BaseModel):
    """Privacy-safe, user-facing summary of the Agent's decision path."""

    decision: ChatAgentDecision
    reasoning_basis: list[ChatAgentReasoningBasis] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    requires_confirmation: bool
    guardrail: ChatAgentGuardrail


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    context_action_type: ChatActionType | None = None
    context_candidate_id: UUID | None = None
    context_session_id: UUID | None = None
    context_candidate_revision: int | None = Field(default=None, ge=1)


class ChatBillAnalysisDailyPoint(BaseModel):
    date: date
    total_expense: Decimal
    total_income: Decimal
    cumulative_expense: Decimal
    budget_usage_percentage: Decimal


class ChatBillAnalysisTrendPoint(BaseModel):
    label: str
    year: int
    month: int
    total_expense: Decimal
    total_income: Decimal
    net_amount: Decimal


class ChatBillAnalysisCategoryPoint(BaseModel):
    category: str
    amount: Decimal
    count: int
    percentage: Decimal


class ChatBillAnalysis(BaseModel):
    period_label: str
    category: str | None = None
    bill_count: int
    total_expense: Decimal
    total_income: Decimal
    total_refund: Decimal
    net_amount: Decimal
    category_amount: Decimal | None = None
    category_count: int | None = None
    category_percentage: Decimal | None = None
    previous_period_label: str
    previous_total_expense: Decimal
    expense_delta: Decimal
    expense_delta_percentage: Decimal | None = None
    previous_category_amount: Decimal | None = None
    category_delta: Decimal | None = None
    category_delta_percentage: Decimal | None = None
    budget_amount: Decimal
    budget_usage_percentage: Decimal
    budget_remaining: Decimal
    budget_warning_threshold_percent: int
    top_category: str | None = None
    top_category_amount: Decimal | None = None
    top_merchant: str | None = None
    top_merchant_amount: Decimal | None = None
    top_day: date | None = None
    top_day_expense: Decimal | None = None
    daily_points: list[ChatBillAnalysisDailyPoint] = Field(default_factory=list)
    monthly_trend: list[ChatBillAnalysisTrendPoint] = Field(default_factory=list)
    category_breakdown: list[ChatBillAnalysisCategoryPoint] = Field(default_factory=list)
    ai_assessment: str = ""


class ChatMessageResponse(BaseModel):
    message_id: UUID
    trace_id: str | None = Field(default=None, max_length=80)
    reply: str
    intent: ChatIntent
    confidence: float = Field(ge=0, le=1)
    assistant_tool_id: str | None = Field(default=None, max_length=80)
    action_type: ChatActionType = ChatActionType.none
    candidate_id: UUID | None = None
    candidate: ParseBillResponse | ParseTaskResponse | ParseDiaryResponse | None = None
    candidate_session: CandidateSessionRead | None = None
    analysis: ChatBillAnalysis | None = None
    warnings: list[str] = []
    agent_steps: list[ChatAgentStep] = Field(default_factory=list)
    explanation: ChatAgentExplanation | None = None
    knowledge_hits: list[AgentKnowledgeHit] = Field(default_factory=list)
    function_calls: list[AgentFunctionCallTrace] = Field(default_factory=list)
    model_trace: AgentModelTrace | None = None
    need_user_confirmation: bool = True
    updated_existing_candidate: bool = False
    discarded: bool = False
    created_bill: BillRead | None = None
    created_task: TaskRead | None = None
    created_diary: DiaryRead | None = None


class ChatConfirmActionRequest(BaseModel):
    action_type: ChatActionType
    candidate_id: UUID
    candidate_session_id: UUID | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class ChatConfirmActionResponse(BaseModel):
    message_id: UUID
    reply: str
    action_type: ChatActionType
    candidate_id: UUID
    candidate_session: CandidateSessionRead | None = None
    created_bill: BillRead | None = None
    created_task: TaskRead | None = None
    created_diary: DiaryRead | None = None
    warnings: list[str] = []


class ChatDiscardActionRequest(BaseModel):
    action_type: ChatActionType
    candidate_id: UUID
    candidate_session_id: UUID | None = None
    expected_revision: int | None = Field(default=None, ge=1)


class ChatDiscardActionResponse(BaseModel):
    message_id: UUID
    reply: str
    action_type: ChatActionType
    candidate_id: UUID
    candidate_session: CandidateSessionRead | None = None
    discarded: bool = True
    warnings: list[str] = []


class ChatCandidateUpdateRequest(BaseModel):
    action_type: ChatActionType
    candidate_session_id: UUID | None = None
    expected_revision: int | None = Field(default=None, ge=1)
    updates: dict[str, object] = Field(default_factory=dict)


class ChatCandidateUpdateResponse(BaseModel):
    candidate: ParseBillResponse | ParseTaskResponse | ParseDiaryResponse
    candidate_session: CandidateSessionRead
