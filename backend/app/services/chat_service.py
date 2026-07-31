import re
from uuid import uuid4

from app.schemas.agent import ParseBillRequest, ParseTaskRequest
from app.schemas.bill import BillSource
from app.schemas.chat import (
    ChatActionType,
    ChatIntent,
    ChatMessageRequest,
    ChatMessageResponse,
)
from app.schemas.task import TaskSource
from app.services.bill_candidate_store import bill_candidate_store
from app.services.bill_parser import bill_parser
from app.services.settings_store import settings_store
from app.services.task_candidate_store import task_candidate_store
from app.services.task_parser import task_parser


class RuleBasedChatService:
    _money_pattern = re.compile(r"(\d+(?:\.\d{1,2})?)\s*(元|块|rmb|cny|¥)")
    _bill_keywords = (
        "记一笔",
        "记账",
        "账单",
        "消费",
        "花了",
        "支出",
        "收入",
        "早餐",
        "午餐",
        "晚餐",
        "咖啡",
        "打车",
    )
    _task_keywords = (
        "提醒",
        "待办",
        "任务",
        "记得",
        "别忘",
        "明天",
        "后天",
        "下周",
        "点",
        "todo",
    )
    _unsupported_reasons = {
        "订阅": "订阅管理还不在 MVP 范围内，可以先把这笔扣费记成普通账单。",
        "会员": "会员和周期扣费管理暂时不自动创建，可以先保存为普通账单或备注。",
        "保修": "保修记录暂时不在 MVP 范围内，可以先把购买信息记成普通账单。",
        "退货": "退货期管理暂时不自动创建，可以先改为普通待办或手动记录。",
        "报销": "报销流程暂时不自动处理，可以先保存为普通账单并在备注里标记。",
        "查询": "跨记录自然语言查询暂时不在 MVP 范围内，可以先使用账单列表和统计接口。",
        "统计": "复杂统计问答暂时不在 MVP 范围内，可以先查看月度统计。",
    }

    def handle_message(self, payload: ChatMessageRequest) -> ChatMessageResponse:
        text = payload.message.strip()
        if not settings_store.get_privacy_settings().allow_ai_text_processing:
            return ChatMessageResponse(
                message_id=uuid4(),
                reply="AI text processing is disabled in privacy settings.",
                intent=ChatIntent.unsupported,
                confidence=1.0,
                action_type=ChatActionType.none,
                candidate=None,
                warnings=["ai_text_processing_disabled"],
                need_user_confirmation=False,
            )

        unsupported_reply = self._unsupported_reply(text)
        if unsupported_reply is not None and not self._looks_like_simple_bill(text):
            return ChatMessageResponse(
                message_id=uuid4(),
                reply=unsupported_reply,
                intent=ChatIntent.unsupported,
                confidence=0.75,
                action_type=ChatActionType.none,
                candidate=None,
                warnings=["unsupported_mvp_intent"],
                need_user_confirmation=False,
            )

        if self._looks_like_task(text):
            candidate = task_candidate_store.save(
                task_parser.parse_task(
                    ParseTaskRequest(text=text, source=TaskSource.ai_chat)
                )
            )
            return ChatMessageResponse(
                message_id=uuid4(),
                reply="我先整理成一个待确认事项，你确认或修改后再保存。",
                intent=ChatIntent.create_task,
                confidence=candidate.confidence,
                action_type=ChatActionType.task_candidate,
                candidate_id=candidate.candidate_id,
                candidate=candidate,
                warnings=candidate.warnings,
                need_user_confirmation=True,
            )

        if self._looks_like_bill(text):
            candidate = bill_candidate_store.save(
                bill_parser.parse_bill(
                    ParseBillRequest(text=text, source=BillSource.ai_chat)
                )
            )
            return ChatMessageResponse(
                message_id=uuid4(),
                reply="我先整理成一个待确认账单，你确认或修改后再保存。",
                intent=ChatIntent.create_bill,
                confidence=candidate.confidence,
                action_type=ChatActionType.bill_candidate,
                candidate_id=candidate.candidate_id,
                candidate=candidate,
                warnings=candidate.warnings,
                need_user_confirmation=True,
            )

        return ChatMessageResponse(
            message_id=uuid4(),
            reply="这条消息还没有足够信息生成账单或提醒。你可以补充金额、事项或提醒时间。",
            intent=ChatIntent.unsupported,
            confidence=0.45,
            action_type=ChatActionType.none,
            candidate=None,
            warnings=["intent_low_confidence"],
            need_user_confirmation=False,
        )

    def _looks_like_bill(self, text: str) -> bool:
        return self._looks_like_simple_bill(text) or any(
            keyword.casefold() in text.casefold() for keyword in self._bill_keywords
        )

    def _looks_like_simple_bill(self, text: str) -> bool:
        return self._money_pattern.search(text.casefold()) is not None

    def _looks_like_task(self, text: str) -> bool:
        return any(keyword.casefold() in text.casefold() for keyword in self._task_keywords)

    def _unsupported_reply(self, text: str) -> str | None:
        for keyword, reply in self._unsupported_reasons.items():
            if keyword in text:
                return reply
        return None


chat_service = RuleBasedChatService()
