from uuid import UUID, uuid4

from fastapi import APIRouter, Header, HTTPException, status

from app.schemas.bill import BillRead
from app.schemas.chat import (
    ChatActionType,
    ChatConfirmActionRequest,
    ChatConfirmActionResponse,
    ChatMessageRequest,
    ChatMessageResponse,
)
from app.schemas.task import TaskRead
from app.services.bill_candidate_store import bill_candidate_store
from app.services.chat_service import chat_service
from app.services.idempotency_store import IdempotencyConflictError, idempotency_store
from app.services.task_candidate_store import task_candidate_store

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/messages", response_model=ChatMessageResponse)
def send_message(payload: ChatMessageRequest) -> ChatMessageResponse:
    return chat_service.handle_message(payload)


@router.post("/confirm-action", response_model=ChatConfirmActionResponse)
def confirm_action(
    payload: ChatConfirmActionRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> ChatConfirmActionResponse:
    try:
        return idempotency_store.run(
            scope="POST /chat/confirm-action",
            key=idempotency_key,
            fingerprint=payload.model_dump(mode="json"),
            factory=lambda: _confirm_candidate(payload),
        )
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


def _confirm_candidate(payload: ChatConfirmActionRequest) -> ChatConfirmActionResponse:
    if payload.action_type == ChatActionType.bill_candidate:
        return _confirm_bill_candidate(payload.candidate_id)
    if payload.action_type == ChatActionType.task_candidate:
        return _confirm_task_candidate(payload.candidate_id)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Chat action type is not confirmable",
    )


def _confirm_bill_candidate(candidate_id: UUID) -> ChatConfirmActionResponse:
    candidate = bill_candidate_store.get(candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill candidate not found",
        )
    if not bill_candidate_store.is_confirmable(candidate):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bill candidate is missing required fields",
        )

    bill: BillRead | None = bill_candidate_store.confirm(candidate_id)
    if bill is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill candidate not found",
        )

    return ChatConfirmActionResponse(
        message_id=uuid4(),
        reply="Bill candidate confirmed and saved.",
        action_type=ChatActionType.bill_candidate,
        candidate_id=candidate_id,
        created_bill=bill,
    )


def _confirm_task_candidate(candidate_id: UUID) -> ChatConfirmActionResponse:
    candidate = task_candidate_store.get(candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task candidate not found",
        )
    if not task_candidate_store.is_confirmable(candidate):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task candidate is missing required fields",
        )

    task: TaskRead | None = task_candidate_store.confirm(candidate_id)
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task candidate not found",
        )

    return ChatConfirmActionResponse(
        message_id=uuid4(),
        reply="Task candidate confirmed and saved.",
        action_type=ChatActionType.task_candidate,
        candidate_id=candidate_id,
        created_task=task,
    )
