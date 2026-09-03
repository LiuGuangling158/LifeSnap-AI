from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.agent import ParseBillResponse, ParseTaskResponse
from app.schemas.bill import BillRead
from app.schemas.task import TaskRead


class ChatIntent(str, Enum):
    create_bill = "create_bill"
    create_task = "create_task"
    diary_reflection = "diary_reflection"
    unsupported = "unsupported"


class ChatActionType(str, Enum):
    bill_candidate = "bill_candidate"
    task_candidate = "task_candidate"
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


class ChatMessageResponse(BaseModel):
    message_id: UUID
    reply: str
    intent: ChatIntent
    confidence: float = Field(ge=0, le=1)
    assistant_tool_id: str | None = Field(default=None, max_length=80)
    action_type: ChatActionType = ChatActionType.none
    candidate_id: UUID | None = None
    candidate: ParseBillResponse | ParseTaskResponse | None = None
    warnings: list[str] = []
    agent_steps: list[ChatAgentStep] = Field(default_factory=list)
    need_user_confirmation: bool = True


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
