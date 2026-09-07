from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.agent import ParseBillResponse, ParseDiaryResponse, ParseTaskResponse
from app.schemas.bill import BillRead
from app.schemas.diary import DiaryRead
from app.schemas.task import TaskRead


class ChatIntent(str, Enum):
    create_bill = "create_bill"
    create_task = "create_task"
    create_diary = "create_diary"
    diary_reflection = "diary_reflection"
    unsupported = "unsupported"


class ChatActionType(str, Enum):
    bill_candidate = "bill_candidate"
    task_candidate = "task_candidate"
    diary_candidate = "diary_candidate"
    none = "none"


class ChatAgentStepStatus(str, Enum):
    completed = "completed"
    needs_confirmation = "needs_confirmation"
    blocked = "blocked"


class ChatAgentStep(BaseModel):
    title: str = Field(min_length=1, max_length=40)
    detail: str = Field(min_length=1, max_length=160)
    status: ChatAgentStepStatus = ChatAgentStepStatus.completed


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    context_action_type: ChatActionType | None = None
    context_candidate_id: UUID | None = None


class ChatMessageResponse(BaseModel):
    message_id: UUID
    reply: str
    intent: ChatIntent
    confidence: float = Field(ge=0, le=1)
    assistant_tool_id: str | None = Field(default=None, max_length=80)
    action_type: ChatActionType = ChatActionType.none
    candidate_id: UUID | None = None
    candidate: ParseBillResponse | ParseTaskResponse | ParseDiaryResponse | None = None
    warnings: list[str] = []
    agent_steps: list[ChatAgentStep] = Field(default_factory=list)
    need_user_confirmation: bool = True
    updated_existing_candidate: bool = False
    discarded: bool = False
    created_bill: BillRead | None = None
    created_task: TaskRead | None = None
    created_diary: DiaryRead | None = None


class ChatConfirmActionRequest(BaseModel):
    action_type: ChatActionType
    candidate_id: UUID


class ChatConfirmActionResponse(BaseModel):
    message_id: UUID
    reply: str
    action_type: ChatActionType
    candidate_id: UUID
    created_bill: BillRead | None = None
    created_task: TaskRead | None = None
    created_diary: DiaryRead | None = None
    warnings: list[str] = []


class ChatDiscardActionRequest(BaseModel):
    action_type: ChatActionType
    candidate_id: UUID


class ChatDiscardActionResponse(BaseModel):
    message_id: UUID
    reply: str
    action_type: ChatActionType
    candidate_id: UUID
    discarded: bool = True
    warnings: list[str] = []
