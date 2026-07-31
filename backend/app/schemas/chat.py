from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.agent import ParseBillResponse, ParseTaskResponse


class ChatIntent(str, Enum):
    create_bill = "create_bill"
    create_task = "create_task"
    unsupported = "unsupported"


class ChatActionType(str, Enum):
    bill_candidate = "bill_candidate"
    task_candidate = "task_candidate"
    none = "none"


class ChatMessageRequest(BaseModel):
    message: str = Field(min_length=1, max_length=5000)


class ChatMessageResponse(BaseModel):
    message_id: UUID
    reply: str
    intent: ChatIntent
    confidence: float = Field(ge=0, le=1)
    action_type: ChatActionType = ChatActionType.none
    candidate_id: UUID | None = None
    candidate: ParseBillResponse | ParseTaskResponse | None = None
    warnings: list[str] = []
    need_user_confirmation: bool = True
