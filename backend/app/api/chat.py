from fastapi import APIRouter

from app.schemas.chat import ChatMessageRequest, ChatMessageResponse
from app.services.chat_service import chat_service

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/messages", response_model=ChatMessageResponse)
def send_message(payload: ChatMessageRequest) -> ChatMessageResponse:
    return chat_service.handle_message(payload)
