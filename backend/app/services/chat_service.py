import re
from uuid import uuid4

from app.schemas.agent import ParseBillRequest, ParseTaskRequest
from app.schemas.bill import BillSource
from app.schemas.chat import (
    ChatActionType,
    ChatAgentStep,
    ChatAgentStepStatus,
    ChatIntent,
    ChatMessageRequest,
    ChatMessageResponse,
)
from app.schemas.task import TaskSource
from app.services.bill_candidate_store import bill_candidate_store
from app.services.bill_parser import RuleBasedBillParser, bill_parser
from app.services.external_ai_parser import ExternalChatRoute, external_ai_parser
from app.services.settings_store import settings_store
from app.services.task_candidate_store import task_candidate_store
from app.services.task_parser import RuleBasedTaskParser, task_parser


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
    _diary_keywords = (
        "日记",
        "心情",
        "开心",
        "感谢",
        "学到",
        "感受",
        "复盘",
        "今天发生",
        "记录今天",
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

    def __init__(self) -> None:
        self._rule_bill_parser = RuleBasedBillParser()
        self._rule_task_parser = RuleBasedTaskParser()

    def handle_message(self, payload: ChatMessageRequest) -> ChatMessageResponse:
        text = payload.message.strip()
        if not settings_store.get_privacy_settings().allow_ai_text_processing:
            return ChatMessageResponse(
                message_id=uuid4(),
                reply="AI text processing is disabled in privacy settings.",
                intent=ChatIntent.unsupported,
                confidence=1.0,
                assistant_tool_id=None,
                action_type=ChatActionType.none,
                candidate=None,
                warnings=["ai_text_processing_disabled"],
                agent_steps=[
                    self._agent_step(
                        "隐私检查",
                        "当前设置不允许 AI 文本处理，已停止解析。",
                        ChatAgentStepStatus.blocked,
                    )
                ],
                need_user_confirmation=False,
            )

        external_route, fallback_warnings = external_ai_parser.route_chat(text)
        if external_route is not None:
            return self._response_from_external_route(text, external_route)

        unsupported_reply = self._unsupported_reply(text)
        if unsupported_reply is not None and not self._looks_like_simple_bill(text):
            return self._unsupported_response(
                reply=unsupported_reply,
                confidence=0.75,
                warnings=["unsupported_mvp_intent"] + fallback_warnings,
            )

        if self._looks_like_diary(text):
            return self._diary_reflection_response(text, fallback_warnings=fallback_warnings)

        force_rule_based = self._should_force_rule_based_parser(fallback_warnings)
        if self._looks_like_task(text):
            return self._task_candidate_response(
                text,
                fallback_warnings=fallback_warnings,
                force_rule_based=force_rule_based,
            )

        if self._looks_like_bill(text):
            return self._bill_candidate_response(
                text,
                fallback_warnings=fallback_warnings,
                force_rule_based=force_rule_based,
            )

        return self._unsupported_response(
            reply="这条消息还没有足够信息生成账单或提醒。你可以补充金额、事项或提醒时间。",
            confidence=0.45,
            warnings=["intent_low_confidence"] + fallback_warnings,
        )

    def _response_from_external_route(
        self,
        text: str,
        route: ExternalChatRoute,
    ) -> ChatMessageResponse:
        if route.intent == ChatIntent.create_task:
            return self._task_candidate_response(
                text,
                reply=route.reply,
                route_confidence=route.confidence,
                fallback_warnings=route.warnings,
            )
        if route.intent == ChatIntent.create_bill:
            return self._bill_candidate_response(
                text,
                reply=route.reply,
                route_confidence=route.confidence,
                fallback_warnings=route.warnings,
            )
        if route.intent == ChatIntent.diary_reflection:
            return self._diary_reflection_response(
                text,
                reply=route.reply,
                route_confidence=route.confidence,
                fallback_warnings=route.warnings,
            )
        if route.intent == ChatIntent.unsupported and self._looks_like_diary(text):
            return self._diary_reflection_response(
                text,
                route_confidence=min(route.confidence, 0.7),
                fallback_warnings=route.warnings,
            )

        return self._unsupported_response(
            reply=route.reply or "这条消息暂时不能直接转换成账单或提醒。",
            confidence=route.confidence,
            warnings=route.warnings,
        )

    def _task_candidate_response(
        self,
        text: str,
        reply: str | None = None,
        route_confidence: float | None = None,
        fallback_warnings: list[str] | None = None,
        force_rule_based: bool = False,
    ) -> ChatMessageResponse:
        parser = self._rule_task_parser if force_rule_based else task_parser
        candidate = task_candidate_store.save(
            parser.parse_task(ParseTaskRequest(text=text, source=TaskSource.ai_chat))
        )
        return ChatMessageResponse(
            message_id=uuid4(),
            reply=reply or "我先整理成一个待确认事项，你确认或修改后再保存。",
            intent=ChatIntent.create_task,
            confidence=self._combined_confidence(candidate.confidence, route_confidence),
            assistant_tool_id="task_candidate",
            action_type=ChatActionType.task_candidate,
            candidate_id=candidate.candidate_id,
            candidate=candidate,
            warnings=self._dedupe(candidate.warnings + (fallback_warnings or [])),
            agent_steps=[
                self._agent_step("理解意图", "识别为提醒或待办请求。"),
                self._agent_step("整理候选", "已提取标题、时间、分类和优先级。"),
                self._agent_step(
                    "等待确认",
                    "保存前需要你确认候选提醒。",
                    ChatAgentStepStatus.needs_confirmation,
                ),
            ],
            need_user_confirmation=True,
        )

    def _bill_candidate_response(
        self,
        text: str,
        reply: str | None = None,
        route_confidence: float | None = None,
        fallback_warnings: list[str] | None = None,
        force_rule_based: bool = False,
    ) -> ChatMessageResponse:
        parser = self._rule_bill_parser if force_rule_based else bill_parser
        candidate = bill_candidate_store.save(
            parser.parse_bill(ParseBillRequest(text=text, source=BillSource.ai_chat))
        )
        return ChatMessageResponse(
            message_id=uuid4(),
            reply=reply or "我先整理成一个待确认账单，你确认或修改后再保存。",
            intent=ChatIntent.create_bill,
            confidence=self._combined_confidence(candidate.confidence, route_confidence),
            assistant_tool_id="bill_candidate",
            action_type=ChatActionType.bill_candidate,
            candidate_id=candidate.candidate_id,
            candidate=candidate,
            warnings=self._dedupe(candidate.warnings + (fallback_warnings or [])),
            agent_steps=[
                self._agent_step("理解意图", "识别为记账请求。"),
                self._agent_step("整理候选", "已提取金额、商户、分类和时间。"),
                self._agent_step(
                    "等待确认",
                    "保存前需要你确认候选账单。",
                    ChatAgentStepStatus.needs_confirmation,
                ),
            ],
            need_user_confirmation=True,
        )

    def _diary_reflection_response(
        self,
        text: str,
        reply: str | None = None,
        route_confidence: float | None = None,
        fallback_warnings: list[str] | None = None,
    ) -> ChatMessageResponse:
        return ChatMessageResponse(
            message_id=uuid4(),
            reply=reply or self._diary_reflection_reply(text),
            intent=ChatIntent.diary_reflection,
            confidence=route_confidence or 0.72,
            assistant_tool_id="diary_reflection",
            action_type=ChatActionType.none,
            candidate=None,
            warnings=self._dedupe(fallback_warnings or []),
            agent_steps=[
                self._agent_step("理解意图", "识别为日记追问或心情整理。"),
                self._agent_step("生成引导", "已准备一个更具体的问题帮助补全日记。"),
            ],
            need_user_confirmation=False,
        )

    def _unsupported_response(
        self,
        reply: str,
        confidence: float,
        warnings: list[str],
    ) -> ChatMessageResponse:
        return ChatMessageResponse(
            message_id=uuid4(),
            reply=reply,
            intent=ChatIntent.unsupported,
            confidence=confidence,
            assistant_tool_id=None,
            action_type=ChatActionType.none,
            candidate=None,
            warnings=self._dedupe(warnings),
            agent_steps=[
                self._agent_step("理解意图", "没有匹配到可执行的生活操作。"),
                self._agent_step(
                    "停止执行",
                    "需要更多信息，或该能力暂未进入当前版本。",
                    ChatAgentStepStatus.blocked,
                ),
            ],
            need_user_confirmation=False,
        )

    def _combined_confidence(
        self,
        candidate_confidence: float,
        route_confidence: float | None,
    ) -> float:
        if route_confidence is None:
            return candidate_confidence
        return round(min(candidate_confidence, route_confidence), 2)

    def _should_force_rule_based_parser(self, warnings: list[str]) -> bool:
        return any(
            warning
            in {
                "external_ai_parser_failed",
                "external_ai_parser_invalid_response",
                "external_ai_parser_skipped",
                "external_chat_intent_invalid_response",
            }
            for warning in warnings
        )

    def _looks_like_bill(self, text: str) -> bool:
        return self._looks_like_simple_bill(text) or any(
            keyword.casefold() in text.casefold() for keyword in self._bill_keywords
        )

    def _looks_like_simple_bill(self, text: str) -> bool:
        return self._money_pattern.search(text.casefold()) is not None

    def _looks_like_task(self, text: str) -> bool:
        return any(keyword.casefold() in text.casefold() for keyword in self._task_keywords)

    def _looks_like_diary(self, text: str) -> bool:
        folded = text.casefold()
        return any(keyword.casefold() in folded for keyword in self._diary_keywords)

    def _diary_reflection_reply(self, text: str) -> str:
        if "感谢" in text:
            return "可以从一个具体的人开始写：今天谁让你觉得被帮助或被理解了？那一刻发生了什么？"
        if "开心" in text:
            return "先抓住今天最开心的一幕吧：它发生在什么时候，你当时为什么会觉得轻松或满足？"
        if "学到" in text or "新东西" in text:
            return "今天学到的新东西可以写成三句：我遇到了什么、我明白了什么、明天我想怎么用它。"
        if "心情" in text or "感受" in text:
            return "我可以陪你把今天的心情理清楚。先告诉我，今天让你情绪变化最大的一件事是什么？"
        return "我可以陪你补全今天的日记。先说一个最想留下的小片段，我会继续帮你追问细节。"

    def _agent_step(
        self,
        title: str,
        detail: str,
        status: ChatAgentStepStatus = ChatAgentStepStatus.completed,
    ) -> ChatAgentStep:
        return ChatAgentStep(title=title, detail=detail, status=status)

    def _unsupported_reply(self, text: str) -> str | None:
        for keyword, reply in self._unsupported_reasons.items():
            if keyword in text:
                return reply
        return None

    def _dedupe(self, warnings: list[str]) -> list[str]:
        deduped: list[str] = []
        for warning in warnings:
            if warning not in deduped:
                deduped.append(warning)
        return deduped


chat_service = RuleBasedChatService()
