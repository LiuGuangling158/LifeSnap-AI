import re
from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import uuid4

from app.schemas.agent import (
    BillCandidateUpdate,
    DiaryCandidateData,
    DiaryCandidateUpdate,
    ParseBillRequest,
    ParseBillResponse,
    ParseDiaryResponse,
    ParseTaskRequest,
    ParseTaskResponse,
    TaskCandidateUpdate,
)
from app.schemas.agent_runtime import AgentKnowledgeHit
from app.schemas.bill import BillSource, TransactionType
from app.schemas.chat import (
    ChatActionType,
    ChatAgentStep,
    ChatAgentStepStatus,
    ChatIntent,
    ChatMessageRequest,
    ChatMessageResponse,
)
from app.schemas.diary import DiaryMood, DiarySource
from app.schemas.task import TaskPriority, TaskSource, TaskType
from app.services.agent_knowledge_base import agent_knowledge_base
from app.services.agent_runtime_service import agent_runtime_service
from app.services.agent_tool_registry import AgentFunctionCallSession, agent_tool_registry
from app.services.bill_candidate_store import bill_candidate_store
from app.services.bill_category_classifier import bill_category_classifier
from app.services.bill_parser import RuleBasedBillParser, bill_parser
from app.services.diary_candidate_store import diary_candidate_store
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
    _context_confirm_keywords = ("确认", "保存", "可以了", "没问题", "对的", "正确", "是的", "确定", "提交", "就这样")
    _context_discard_keywords = ("不保存", "别保存", "取消", "丢弃", "放弃", "不要了", "算了", "删掉")
    _context_update_keywords = (
        "改",
        "修改",
        "补充",
        "更新",
        "设为",
        "设置为",
        "应该是",
        "其实是",
        "不是",
        "填",
        "商户",
        "商家",
        "金额",
        "分类",
        "时间",
        "标题",
        "备注",
        "标签",
        "天气",
        "心情",
        "提醒时间",
        "截止时间",
    )
    _new_record_keywords = ("再记", "另外", "另记", "新建", "新增", "创建", "再加", "还有一笔", "下一笔")
    _time_hint_keywords = (
        "昨天",
        "今天",
        "今晚",
        "明天",
        "后天",
        "下周",
        "下星期",
        "上午",
        "中午",
        "下午",
        "晚上",
        "早上",
        "凌晨",
        "点",
        "时",
        ":",
        "：",
        "月",
        "号",
    )
    _agent_capability_keywords = (
        "知识库",
        "rag",
        "检索增强",
        "function calling",
        "函数调用",
        "工具调用",
        "微调",
        "fine-tuning",
        "fine tuning",
        "大模型",
        "模型",
        "agent",
        "智能体",
    )

    def __init__(self) -> None:
        self._rule_bill_parser = RuleBasedBillParser()
        self._rule_task_parser = RuleBasedTaskParser()

    def handle_message(self, payload: ChatMessageRequest) -> ChatMessageResponse:
        text = payload.message.strip()
        function_session = agent_tool_registry.session()
        preview = self._preview_text(text)
        privacy_settings = function_session.call(
            "privacy_guard",
            {"scope": "chat_message"},
            settings_store.get_privacy_settings,
            lambda settings: "允许文本解析" if settings.allow_ai_text_processing else "阻止文本解析",
        )
        if not privacy_settings.allow_ai_text_processing:
            return self._with_runtime_trace(
                ChatMessageResponse(
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
                ),
                [],
                function_session,
            )

        knowledge_hits = function_session.call(
            "knowledge_search",
            {"query": preview, "limit": 3},
            lambda: agent_knowledge_base.search(text),
            lambda hits: f"命中 {len(hits)} 条知识",
        )

        if self._looks_like_agent_capability_question(text):
            return self._with_runtime_trace(
                self._agent_capability_response(text, knowledge_hits),
                knowledge_hits,
                function_session,
            )

        context_response = self._response_from_candidate_context(text, payload, function_session)
        if context_response is not None:
            return self._with_runtime_trace(context_response, knowledge_hits, function_session)

        external_route, fallback_warnings = external_ai_parser.route_chat(text)
        if external_route is not None:
            return self._with_runtime_trace(
                self._response_from_external_route(text, external_route, knowledge_hits, function_session),
                knowledge_hits,
                function_session,
            )

        unsupported_reply = self._unsupported_reply(text)
        if unsupported_reply is not None and not self._looks_like_simple_bill(text):
            return self._with_runtime_trace(
                self._unsupported_response(
                    reply=unsupported_reply,
                    confidence=0.75,
                    warnings=["unsupported_mvp_intent"] + fallback_warnings,
                ),
                knowledge_hits,
                function_session,
            )

        if self._looks_like_diary_entry(text):
            return self._with_runtime_trace(
                self._diary_candidate_response(
                    text,
                    fallback_warnings=fallback_warnings,
                    function_session=function_session,
                ),
                knowledge_hits,
                function_session,
            )

        if self._looks_like_diary(text):
            return self._with_runtime_trace(
                self._diary_reflection_response(
                    text,
                    fallback_warnings=fallback_warnings,
                    function_session=function_session,
                ),
                knowledge_hits,
                function_session,
            )

        force_rule_based = self._should_force_rule_based_parser(fallback_warnings)
        if self._looks_like_task(text):
            return self._with_runtime_trace(
                self._task_candidate_response(
                    text,
                    fallback_warnings=fallback_warnings,
                    force_rule_based=force_rule_based,
                    function_session=function_session,
                ),
                knowledge_hits,
                function_session,
            )

        if self._looks_like_bill(text):
            return self._with_runtime_trace(
                self._bill_candidate_response(
                    text,
                    fallback_warnings=fallback_warnings,
                    force_rule_based=force_rule_based,
                    function_session=function_session,
                ),
                knowledge_hits,
                function_session,
            )

        return self._with_runtime_trace(
            self._unsupported_response(
                reply="这条消息还没有足够信息生成账单或提醒。你可以补充金额、事项或提醒时间。",
                confidence=0.45,
                warnings=["intent_low_confidence"] + fallback_warnings,
            ),
            knowledge_hits,
            function_session,
        )

    def _with_runtime_trace(
        self,
        response: ChatMessageResponse,
        knowledge_hits: list[AgentKnowledgeHit],
        function_session: AgentFunctionCallSession,
    ) -> ChatMessageResponse:
        response.knowledge_hits = knowledge_hits
        if response.intent != ChatIntent.knowledge_answer and "ai_text_processing_disabled" not in response.warnings:
            if not any(call.name == "route_chat_intent" for call in function_session.traces):
                function_session.record(
                    "route_chat_intent",
                    {"message": self._route_trace_message(function_session, response)},
                    f"intent={response.intent.value}, confidence={response.confidence}",
                )
        response.function_calls = function_session.traces
        response.model_trace = agent_runtime_service.model_trace()
        return response

    def _route_trace_message(
        self,
        function_session: AgentFunctionCallSession,
        response: ChatMessageResponse,
    ) -> str:
        for call in function_session.traces:
            if call.name == "knowledge_search":
                query = call.arguments.get("query")
                if isinstance(query, str) and query.strip():
                    return query
        return self._preview_text(response.reply)

    def _looks_like_agent_capability_question(self, text: str) -> bool:
        normalized = text.casefold()
        specific_keywords = (
            "知识库",
            "rag",
            "检索增强",
            "function calling",
            "函数调用",
            "工具调用",
            "微调",
            "fine-tuning",
            "fine tuning",
            "大模型",
        )
        if any(keyword in normalized for keyword in specific_keywords):
            return True
        return any(subject in normalized for subject in ("agent", "助手", "智能体", "你")) and any(
            keyword in normalized for keyword in ("模型", "工具", "能力", "链路", "怎么工作")
        )

    def _agent_capability_response(
        self,
        text: str,
        knowledge_hits: list[AgentKnowledgeHit],
    ) -> ChatMessageResponse:
        runtime = agent_runtime_service.profile()
        model = runtime.model_profile
        model_text = model.runtime_model or "本地规则解析"
        fine_tune_text = (
            f"已配置微调模型 {model.fine_tuned_model}"
            if model.fine_tuned_model
            else "已准备微调样本导出，配置微调模型后会优先使用"
        )
        reply = (
            "我现在按 RAG 知识库、函数调用和模型策略三段工作："
            f"先检索 {sum(source.document_count for source in runtime.knowledge_sources)} 条本地业务知识，"
            f"再从 {len(runtime.function_tools)} 个内部函数工具里选择要调用的能力，"
            f"最后使用 {model_text} 生成候选或回答。{fine_tune_text}。"
        )
        return ChatMessageResponse(
            message_id=uuid4(),
            reply=reply,
            intent=ChatIntent.knowledge_answer,
            confidence=0.93,
            assistant_tool_id="knowledge_search",
            action_type=ChatActionType.none,
            candidate=None,
            warnings=[],
            agent_steps=[
                self._agent_step("检索知识库", f"命中 {len(knowledge_hits)} 条 LifeSnap 业务知识。"),
                self._agent_step("选择函数", f"当前注册 {len(runtime.function_tools)} 个可调用工具。"),
                self._agent_step("读取模型策略", f"当前策略：{model.strategy}。"),
            ],
            need_user_confirmation=False,
        )

    def _preview_text(self, text: str, max_length: int = 80) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip()
        if len(cleaned) <= max_length:
            return cleaned
        return f"{cleaned[: max_length - 1]}…"

    def _response_from_external_route(
        self,
        text: str,
        route: ExternalChatRoute,
        knowledge_hits: list[AgentKnowledgeHit],
        function_session: AgentFunctionCallSession,
    ) -> ChatMessageResponse:
        if route.intent == ChatIntent.create_diary:
            return self._diary_candidate_response(
                text,
                reply=route.reply,
                route_confidence=route.confidence,
                fallback_warnings=route.warnings,
                function_session=function_session,
            )
        if route.intent == ChatIntent.create_task:
            return self._task_candidate_response(
                text,
                reply=route.reply,
                route_confidence=route.confidence,
                fallback_warnings=route.warnings,
                function_session=function_session,
            )
        if route.intent == ChatIntent.create_bill:
            return self._bill_candidate_response(
                text,
                reply=route.reply,
                route_confidence=route.confidence,
                fallback_warnings=route.warnings,
                function_session=function_session,
            )
        if route.intent == ChatIntent.diary_reflection:
            if self._looks_like_diary_entry(text):
                return self._diary_candidate_response(
                    text,
                    reply=route.reply,
                    route_confidence=min(route.confidence, 0.78),
                    fallback_warnings=route.warnings,
                    function_session=function_session,
                )
            return self._diary_reflection_response(
                text,
                reply=route.reply,
                route_confidence=route.confidence,
                fallback_warnings=route.warnings,
                function_session=function_session,
            )
        if route.intent == ChatIntent.unsupported and self._looks_like_diary(text):
            if self._looks_like_diary_entry(text):
                return self._diary_candidate_response(
                    text,
                    route_confidence=min(route.confidence, 0.7),
                    fallback_warnings=route.warnings,
                    function_session=function_session,
                )
            return self._diary_reflection_response(
                text,
                route_confidence=min(route.confidence, 0.7),
                fallback_warnings=route.warnings,
                function_session=function_session,
            )
        if route.intent == ChatIntent.knowledge_answer:
            return self._agent_capability_response(text, knowledge_hits)

        return self._unsupported_response(
            reply=route.reply or "这条消息暂时不能直接转换成账单或提醒。",
            confidence=route.confidence,
            warnings=route.warnings,
        )

    def _response_from_candidate_context(
        self,
        text: str,
        payload: ChatMessageRequest,
        function_session: AgentFunctionCallSession,
    ) -> ChatMessageResponse | None:
        action_type = payload.context_action_type
        candidate_id = payload.context_candidate_id
        if action_type is None or candidate_id is None or action_type == ChatActionType.none:
            return None
        if self._looks_like_new_record(text) or self._looks_like_different_intent(text, action_type):
            return None

        candidate = self._candidate_for_context(action_type, candidate_id)
        if candidate is None:
            if self._is_context_control_message(text):
                return self._unsupported_response(
                    reply="上一条待确认记录已经不存在，可能已经保存或丢弃。请重新整理一次。",
                    confidence=0.72,
                    warnings=["context_candidate_not_found"],
                )
            return None

        if self._is_discard_message(text):
            return function_session.call(
                "discard_candidate",
                {"candidate_id": str(candidate_id), "action_type": action_type.value},
                lambda: self._discard_context_candidate(action_type, candidate_id),
                self._context_action_result,
            )
        if self._is_confirm_message(text):
            return function_session.call(
                "confirm_candidate",
                {"candidate_id": str(candidate_id), "action_type": action_type.value},
                lambda: self._confirm_context_candidate(action_type, candidate_id, candidate),
                self._context_action_result,
            )

        if action_type == ChatActionType.bill_candidate:
            updates = self._bill_updates_from_text(text, candidate)
            if self._should_apply_context_update(
                text,
                updates,
                bill_candidate_store.is_confirmable(candidate),
            ):
                return function_session.call(
                    "update_candidate",
                    {
                        "candidate_id": str(candidate_id),
                        "action_type": action_type.value,
                        "fields": ",".join(sorted(updates)),
                    },
                    lambda: self._update_bill_context_candidate(candidate_id, updates),
                    self._context_action_result,
                )
        if action_type == ChatActionType.task_candidate:
            updates = self._task_updates_from_text(text, candidate)
            if self._should_apply_context_update(
                text,
                updates,
                task_candidate_store.is_confirmable(candidate),
            ):
                return function_session.call(
                    "update_candidate",
                    {
                        "candidate_id": str(candidate_id),
                        "action_type": action_type.value,
                        "fields": ",".join(sorted(updates)),
                    },
                    lambda: self._update_task_context_candidate(candidate_id, updates),
                    self._context_action_result,
                )
        if action_type == ChatActionType.diary_candidate:
            updates = self._diary_updates_from_text(text, candidate)
            if self._should_apply_context_update(
                text,
                updates,
                diary_candidate_store.is_confirmable(candidate),
            ):
                return function_session.call(
                    "update_candidate",
                    {
                        "candidate_id": str(candidate_id),
                        "action_type": action_type.value,
                        "fields": ",".join(sorted(updates)),
                    },
                    lambda: self._update_diary_context_candidate(candidate_id, updates),
                    self._context_action_result,
                )

        if self._contains_context_update_keyword(text):
            return self._unsupported_response(
                reply="我知道你在补充上一条记录，但没读懂要改哪一项。可以说“金额 28 元”“商家是麦当劳”这类短句。",
                confidence=0.52,
                warnings=["context_update_no_fields"],
            )
        return None

    def _candidate_for_context(self, action_type: ChatActionType, candidate_id):
        if action_type == ChatActionType.bill_candidate:
            return bill_candidate_store.get(candidate_id)
        if action_type == ChatActionType.task_candidate:
            return task_candidate_store.get(candidate_id)
        if action_type == ChatActionType.diary_candidate:
            return diary_candidate_store.get(candidate_id)
        return None

    def _confirm_context_candidate(
        self,
        action_type: ChatActionType,
        candidate_id,
        candidate,
    ) -> ChatMessageResponse:
        if action_type == ChatActionType.bill_candidate:
            if not bill_candidate_store.is_confirmable(candidate):
                return self._context_missing_response(action_type, candidate)
            bill = bill_candidate_store.confirm(candidate_id)
            return self._context_confirmed_response(action_type, candidate_id, created_bill=bill)
        if action_type == ChatActionType.task_candidate:
            if not task_candidate_store.is_confirmable(candidate):
                return self._context_missing_response(action_type, candidate)
            task = task_candidate_store.confirm(candidate_id)
            return self._context_confirmed_response(action_type, candidate_id, created_task=task)
        if action_type == ChatActionType.diary_candidate:
            if not diary_candidate_store.is_confirmable(candidate):
                return self._context_missing_response(action_type, candidate)
            diary = diary_candidate_store.confirm(candidate_id)
            return self._context_confirmed_response(action_type, candidate_id, created_diary=diary)

        return self._unsupported_response(
            reply="这条记录暂时不能通过聊天确认。",
            confidence=0.5,
            warnings=["context_action_not_confirmable"],
        )

    def _discard_context_candidate(
        self,
        action_type: ChatActionType,
        candidate_id,
    ) -> ChatMessageResponse:
        deleted = False
        if action_type == ChatActionType.bill_candidate:
            deleted = bill_candidate_store.delete(candidate_id)
        elif action_type == ChatActionType.task_candidate:
            deleted = task_candidate_store.delete(candidate_id)
        elif action_type == ChatActionType.diary_candidate:
            deleted = diary_candidate_store.delete(candidate_id)

        if not deleted:
            return self._unsupported_response(
                reply="上一条待确认记录已经不存在，可能已经保存或丢弃。",
                confidence=0.72,
                warnings=["context_candidate_not_found"],
            )

        return ChatMessageResponse(
            message_id=uuid4(),
            reply=self._context_discard_reply(action_type),
            intent=self._intent_for_action_type(action_type),
            confidence=0.94,
            assistant_tool_id=action_type.value,
            action_type=action_type,
            candidate_id=candidate_id,
            candidate=None,
            warnings=[],
            agent_steps=[
                self._agent_step("读取上下文", "已找到上一条待确认记录。"),
                self._agent_step("取消候选", "已按你的意思丢弃这条待确认记录。"),
            ],
            need_user_confirmation=False,
            discarded=True,
        )

    def _context_confirmed_response(
        self,
        action_type: ChatActionType,
        candidate_id,
        created_bill=None,
        created_task=None,
        created_diary=None,
    ) -> ChatMessageResponse:
        return ChatMessageResponse(
            message_id=uuid4(),
            reply=self._context_confirm_reply(action_type),
            intent=self._intent_for_action_type(action_type),
            confidence=0.96,
            assistant_tool_id=action_type.value,
            action_type=action_type,
            candidate_id=candidate_id,
            candidate=None,
            warnings=[],
            agent_steps=[
                self._agent_step("读取上下文", "已找到上一条待确认记录。"),
                self._agent_step("收到确认", "已确认你要保存这条记录。"),
                self._agent_step("保存记录", "记录已写入本地数据。"),
            ],
            need_user_confirmation=False,
            created_bill=created_bill,
            created_task=created_task,
            created_diary=created_diary,
        )

    def _context_missing_response(
        self,
        action_type: ChatActionType,
        candidate,
    ) -> ChatMessageResponse:
        detail = self._context_missing_detail(action_type, candidate)
        return ChatMessageResponse(
            message_id=uuid4(),
            reply=f"还不能保存，{detail}。继续告诉我缺的信息就行。",
            intent=self._intent_for_action_type(action_type),
            confidence=candidate.confidence,
            assistant_tool_id=action_type.value,
            action_type=action_type,
            candidate_id=candidate.candidate_id,
            candidate=candidate,
            warnings=candidate.warnings,
            agent_steps=[
                self._agent_step("读取上下文", "已找到上一条待确认记录。"),
                self._agent_step(
                    "等待补充",
                    detail,
                    ChatAgentStepStatus.blocked,
                ),
            ],
            need_user_confirmation=True,
        )

    def _update_bill_context_candidate(
        self,
        candidate_id,
        updates: dict[str, Any],
    ) -> ChatMessageResponse:
        try:
            candidate = bill_candidate_store.update(candidate_id, BillCandidateUpdate(**updates))
        except ValueError:
            candidate = None
        if candidate is None:
            return self._unsupported_response(
                reply="这次补充的信息没有通过账单校验，请换个说法试试。",
                confidence=0.45,
                warnings=["context_candidate_update_invalid"],
            )
        return self._context_updated_response(
            ChatActionType.bill_candidate,
            candidate,
            updates,
            bill_candidate_store.is_confirmable(candidate),
        )

    def _update_task_context_candidate(
        self,
        candidate_id,
        updates: dict[str, Any],
    ) -> ChatMessageResponse:
        try:
            candidate = task_candidate_store.update(candidate_id, TaskCandidateUpdate(**updates))
        except ValueError:
            candidate = None
        if candidate is None:
            return self._unsupported_response(
                reply="这次补充的信息没有通过待办校验，请换个说法试试。",
                confidence=0.45,
                warnings=["context_candidate_update_invalid"],
            )
        return self._context_updated_response(
            ChatActionType.task_candidate,
            candidate,
            updates,
            task_candidate_store.is_confirmable(candidate),
        )

    def _update_diary_context_candidate(
        self,
        candidate_id,
        updates: dict[str, Any],
    ) -> ChatMessageResponse:
        try:
            candidate = diary_candidate_store.update(candidate_id, DiaryCandidateUpdate(**updates))
        except ValueError:
            candidate = None
        if candidate is None:
            return self._unsupported_response(
                reply="这次补充的信息没有通过日记校验，请换个说法试试。",
                confidence=0.45,
                warnings=["context_candidate_update_invalid"],
            )
        return self._context_updated_response(
            ChatActionType.diary_candidate,
            candidate,
            updates,
            diary_candidate_store.is_confirmable(candidate),
        )

    def _context_updated_response(
        self,
        action_type: ChatActionType,
        candidate,
        updates: dict[str, Any],
        confirmable: bool,
    ) -> ChatMessageResponse:
        field_text = self._field_names_text(action_type, updates)
        missing_detail = self._context_missing_detail(action_type, candidate)
        reply = (
            f"已更新{field_text}，再核对一下，没问题就可以保存。"
            if confirmable
            else f"已更新{field_text}，但{missing_detail}。继续补充后再保存。"
        )
        return ChatMessageResponse(
            message_id=uuid4(),
            reply=reply,
            intent=self._intent_for_action_type(action_type),
            confidence=candidate.confidence,
            assistant_tool_id=action_type.value,
            action_type=action_type,
            candidate_id=candidate.candidate_id,
            candidate=candidate,
            warnings=candidate.warnings,
            agent_steps=[
                self._agent_step("读取上下文", "已找到上一条待确认记录。"),
                self._agent_step("理解补充", "识别为对上一条记录的补充或修改。"),
                self._agent_step("更新候选", f"已更新{field_text}。"),
                self._agent_step(
                    "等待确认" if confirmable else "等待补充",
                    "保存前需要你确认候选记录。" if confirmable else missing_detail,
                    ChatAgentStepStatus.needs_confirmation if confirmable else ChatAgentStepStatus.blocked,
                ),
            ],
            need_user_confirmation=True,
            updated_existing_candidate=True,
        )

    def _bill_updates_from_text(
        self,
        text: str,
        candidate: ParseBillResponse,
    ) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        amount = self._rule_bill_parser._extract_amount(text)
        if amount is not None:
            updates["amount"] = amount

        payment_method = self._extract_named_value(text, ("支付方式", "付款方式"))
        if payment_method is None:
            payment_method = self._rule_bill_parser._extract_payment_method(text)
        if payment_method is not None:
            updates["payment_method"] = payment_method[:40]

        transaction_type = self._explicit_transaction_type(text)
        if transaction_type is not None:
            updates["transaction_type"] = transaction_type

        category = self._bill_category_from_text(text, transaction_type or candidate.data.transaction_type)
        if category is not None:
            updates["category"] = category[:40]

        merchant = self._extract_named_value(text, ("商户", "商家", "店名", "店铺", "收款方", "用途"))
        if merchant is None:
            merchant = self._merchant_phrase_from_bill_text(text)
        if merchant is None and (candidate.data.merchant is None or self._looks_like_short_context_patch(text)):
            merchant = self._fallback_merchant_from_bill_text(text)
        if merchant is not None:
            updates["merchant"] = merchant[:120]

        paid_at = self._datetime_from_text(text)
        if paid_at is not None:
            updates["paid_at"] = paid_at

        note = self._extract_named_value(text, ("备注", "说明"))
        if note is not None:
            updates["note"] = note[:500]
        return updates

    def _bill_category_from_text(
        self,
        text: str,
        transaction_type: TransactionType | None = None,
    ) -> str | None:
        category = self._extract_named_value(text, ("分类", "类别"))
        if category is not None:
            return bill_category_classifier.normalize_category(category)
        category_match = bill_category_classifier.classify(text, transaction_type)
        return category_match.category if category_match.category != "其他" else None

    def _explicit_transaction_type(self, text: str) -> TransactionType | None:
        for keywords, transaction_type in (
            (("退款", "退回"), TransactionType.refund),
            (("工资", "收入", "奖金", "收款"), TransactionType.income),
            (("充值", "储值"), TransactionType.top_up),
            (("转账",), TransactionType.transfer),
            (("消费", "支出", "花了", "付款", "支付"), TransactionType.expense),
        ):
            if any(keyword in text for keyword in keywords):
                return transaction_type
        return None

    def _merchant_phrase_from_bill_text(self, text: str) -> str | None:
        match = re.search(r"在\s*([^，,。；;\n]{1,120}?)(?:花了|花|消费|支出|买|点了|点|吃|付款|支付)", text)
        if match is None:
            return None
        return self._clean_patch_value(match.group(1))

    def _fallback_merchant_from_bill_text(self, text: str) -> str | None:
        cleaned = text
        cleaned = re.sub(r"图片附件[:：].*", "", cleaned)
        for pattern in self._rule_bill_parser._amount_patterns:
            cleaned = pattern.sub("", cleaned)
        cleaned = re.sub(
            r"(?:商户|商家|店名|店铺|收款方|用途|金额|分类|类别|支付方式|付款方式|备注|说明)\s*(?:是|为|叫|改成|改为|设为|设置为|：|:)?",
            "",
            cleaned,
        )
        for token in [*settings_store.get_category_settings().bill_categories, "微信支付", "微信", "支付宝", "银行卡", "云闪付"]:
            cleaned = cleaned.replace(token, "")
        cleaned = re.sub(
            r"(支付|付款|花了|花|消费|支出|收入|退款|退回|工资|奖金|转账|充值|储值|元|块|rmb|cny|¥|￥)",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
        for token in self._time_hint_keywords:
            cleaned = cleaned.replace(token, "")
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" ，,。；;：:")
        if not cleaned or len(cleaned) > 120:
            return None
        return cleaned

    def _task_updates_from_text(
        self,
        text: str,
        candidate: ParseTaskResponse,
    ) -> dict[str, Any]:
        parsed = self._rule_task_parser.parse_task(ParseTaskRequest(text=text, source=TaskSource.ai_chat)).data
        updates: dict[str, Any] = {}

        if self._has_task_type_hint(text):
            updates["task_type"] = parsed.task_type

        if self._has_time_hint(text):
            target_at = parsed.remind_at or parsed.due_at or self._datetime_from_text(text)
            if target_at is not None:
                should_remind = parsed.task_type == TaskType.reminder or candidate.data.task_type == TaskType.reminder
                if should_remind:
                    updates["task_type"] = TaskType.reminder
                    updates["remind_at"] = target_at
                else:
                    updates["due_at"] = target_at

        category = self._task_category_from_text(text, parsed.category)
        if category is not None:
            updates["category"] = category[:40]

        if parsed.priority != TaskPriority.medium or any(keyword in text for keyword in ("普通", "中等", "默认优先级")):
            updates["priority"] = parsed.priority

        title = self._extract_named_value(text, ("标题", "事项", "任务", "待办", "提醒内容"))
        if title is None and candidate.data.title is None and parsed.title and not self._looks_like_task_time_only(text):
            title = parsed.title
        if title is not None:
            updates["title"] = title[:120]

        description = self._extract_named_value(text, ("备注", "说明", "描述"))
        if description is not None:
            updates["description"] = description[:500]
        return updates

    def _diary_updates_from_text(
        self,
        text: str,
        candidate: ParseDiaryResponse,
    ) -> dict[str, Any]:
        updates: dict[str, Any] = {}
        entry_date = self._date_from_text(text)
        if entry_date is not None:
            updates["entry_date"] = entry_date

        title = self._extract_named_value(text, ("标题", "题目"))
        if title is None and candidate.data.title is None:
            parsed_title = self._diary_title(self._clean_diary_text(text), self._diary_mood(text))
            title = parsed_title if parsed_title else None
        if title is not None:
            updates["title"] = title[:120]

        content = self._extract_named_value(text, ("正文", "内容"))
        if content is None and candidate.data.content is None and not self._looks_like_diary_metadata_only(text):
            content = self._clean_diary_text(text)
        if content is not None:
            updates["content"] = content[:5000]

        mood = self._explicit_diary_mood(text)
        if mood is not None:
            updates["mood"] = mood

        weather = self._diary_weather(text)
        if weather is not None:
            updates["weather"] = weather

        tags = self._tags_from_text(text)
        if tags is not None:
            updates["tags"] = tags
        return updates

    def _task_category_from_text(self, text: str, parsed_category: str) -> str | None:
        category = self._extract_named_value(text, ("分类", "类别"))
        if category is not None:
            return category
        for item in settings_store.get_category_settings().task_categories:
            if item and item in text:
                return item
        return parsed_category if parsed_category != "生活" else None

    def _has_task_type_hint(self, text: str) -> bool:
        return any(keyword in text for keyword in ("提醒", "闹钟", "待办", "任务", "todo"))

    def _has_time_hint(self, text: str) -> bool:
        return any(keyword in text for keyword in self._time_hint_keywords) or self._rule_task_parser._clock_pattern.search(text) is not None

    def _datetime_from_text(self, text: str) -> datetime | None:
        now = datetime.now().astimezone()
        if "昨天" in text:
            clock = self._rule_task_parser._extract_clock(text) or time(23, 59)
            return datetime.combine(now.date() - timedelta(days=1), clock, tzinfo=now.tzinfo)
        target_at, date_found, clock_found = self._rule_task_parser._extract_target_at(text)
        if target_at is None or not (date_found or clock_found):
            return None
        return target_at

    def _should_apply_context_update(
        self,
        text: str,
        updates: dict[str, Any],
        candidate_confirmable: bool,
    ) -> bool:
        if not updates:
            return False
        if self._contains_context_update_keyword(text):
            return True
        if not candidate_confirmable:
            return True
        return self._looks_like_short_context_patch(text)

    def _looks_like_new_record(self, text: str) -> bool:
        return any(keyword in text for keyword in self._new_record_keywords) and (
            self._looks_like_bill(text)
            or self._looks_like_task(text)
            or self._looks_like_diary_entry(text)
        )

    def _looks_like_different_intent(self, text: str, action_type: ChatActionType) -> bool:
        if action_type != ChatActionType.bill_candidate and self._looks_like_bill(text):
            return True
        if action_type != ChatActionType.task_candidate and self._looks_like_task(text) and not self._contains_context_update_keyword(text):
            return True
        if action_type != ChatActionType.diary_candidate and self._looks_like_diary_entry(text):
            return True
        return False

    def _is_context_control_message(self, text: str) -> bool:
        return self._is_confirm_message(text) or self._is_discard_message(text) or self._contains_context_update_keyword(text)

    def _is_confirm_message(self, text: str) -> bool:
        if self._is_discard_message(text):
            return False
        return any(keyword in text for keyword in self._context_confirm_keywords)

    def _is_discard_message(self, text: str) -> bool:
        return any(keyword in text for keyword in self._context_discard_keywords)

    def _contains_context_update_keyword(self, text: str) -> bool:
        return any(keyword in text for keyword in self._context_update_keywords)

    def _looks_like_short_context_patch(self, text: str) -> bool:
        return len(text) <= 80 and not self._looks_like_new_record(text)

    def _extract_named_value(self, text: str, labels: tuple[str, ...]) -> str | None:
        labels_pattern = "|".join(re.escape(label) for label in labels)
        match = re.search(
            rf"(?:{labels_pattern})\s*(?:是|为|叫|改成|改为|设为|设置为|：|:)?\s*([^，,。；;\n]+)",
            text,
        )
        if match is None:
            return None
        return self._clean_patch_value(match.group(1))

    def _clean_patch_value(self, value: str) -> str | None:
        cleaned = re.sub(r"^(是|为|叫|改成|改为|设为|设置为)", "", value.strip())
        cleaned = cleaned.strip(" '\"“”‘’：:，,。；;")
        return cleaned or None

    def _date_from_text(self, text: str) -> date | None:
        today = date.today()
        if "昨天" in text:
            return today - timedelta(days=1)
        if "明天" in text:
            return today + timedelta(days=1)
        if "今天" in text:
            return today
        full_date_match = re.search(r"(\d{4})\s*[年/-]\s*(\d{1,2})\s*[月/-]\s*(\d{1,2})\s*[日号]?", text)
        if full_date_match is not None:
            try:
                return date(
                    int(full_date_match.group(1)),
                    int(full_date_match.group(2)),
                    int(full_date_match.group(3)),
                )
            except ValueError:
                return None
        month_day_match = re.search(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]?", text)
        if month_day_match is None:
            return None
        try:
            return date(today.year, int(month_day_match.group(1)), int(month_day_match.group(2)))
        except ValueError:
            return None

    def _looks_like_task_time_only(self, text: str) -> bool:
        cleaned = self._rule_task_parser._clock_pattern.sub("", text)
        cleaned = self._rule_task_parser._month_day_pattern.sub("", cleaned)
        for token in [*self._time_hint_keywords, "提醒时间", "截止时间", "时间", "是", "为", "改成", "改为", "设为", "设置为"]:
            cleaned = cleaned.replace(token, "")
        return not cleaned.strip(" ，,。；;：:")

    def _looks_like_diary_metadata_only(self, text: str) -> bool:
        cleaned = text
        for token in ["标题", "题目", "心情", "天气", "标签", "日期", "是", "为", "改成", "改为", "设为", "设置为", *self._time_hint_keywords]:
            cleaned = cleaned.replace(token, "")
        cleaned = re.sub(r"[，,、。；;：:\s]+", "", cleaned)
        return not cleaned

    def _explicit_diary_mood(self, text: str) -> DiaryMood | None:
        mood = self._diary_mood(text)
        if mood != DiaryMood.calm or any(keyword in text for keyword in ("平静", "冷静", "普通", "一般")):
            return mood
        return None

    def _tags_from_text(self, text: str) -> list[str] | None:
        tags_text = self._extract_named_value(text, ("标签", "tag", "tags"))
        if tags_text is None:
            return None
        tags: list[str] = []
        for item in re.split(r"[，,、;；\s]+", tags_text):
            tag = item.strip()
            if tag and tag not in tags:
                tags.append(tag[:40])
            if len(tags) >= 20:
                break
        return tags

    def _intent_for_action_type(self, action_type: ChatActionType) -> ChatIntent:
        if action_type == ChatActionType.bill_candidate:
            return ChatIntent.create_bill
        if action_type == ChatActionType.task_candidate:
            return ChatIntent.create_task
        if action_type == ChatActionType.diary_candidate:
            return ChatIntent.create_diary
        return ChatIntent.unsupported

    def _context_confirm_reply(self, action_type: ChatActionType) -> str:
        return {
            ChatActionType.bill_candidate: "已保存这笔账，可以在账单里查看。",
            ChatActionType.task_candidate: "已保存这件事，可以在待办里查看。",
            ChatActionType.diary_candidate: "已保存这篇日记，可以在日记里查看。",
        }.get(action_type, "已保存记录。")

    def _context_discard_reply(self, action_type: ChatActionType) -> str:
        return {
            ChatActionType.bill_candidate: "好的，这笔账没有保存。",
            ChatActionType.task_candidate: "好的，这件事没有保存。",
            ChatActionType.diary_candidate: "好的，这篇日记没有保存。",
        }.get(action_type, "好的，这条记录没有保存。")

    def _context_missing_detail(self, action_type: ChatActionType, candidate) -> str:
        if action_type == ChatActionType.bill_candidate:
            return self._bill_missing_detail(candidate)
        if action_type == ChatActionType.task_candidate:
            return self._task_missing_detail(candidate)
        if action_type == ChatActionType.diary_candidate:
            missing: list[str] = []
            if candidate.data.entry_date is None:
                missing.append("日期")
            if candidate.data.title is None:
                missing.append("标题")
            if candidate.data.content is None:
                missing.append("正文")
            return f"缺少{'、'.join(missing or ['必要信息'])}，暂时不能确认保存"
        return "缺少必要信息，暂时不能确认保存"

    def _field_names_text(self, action_type: ChatActionType, updates: dict[str, Any]) -> str:
        labels = {
            ChatActionType.bill_candidate: {
                "amount": "金额",
                "merchant": "商家",
                "category": "分类",
                "payment_method": "支付方式",
                "paid_at": "时间",
                "transaction_type": "类型",
                "note": "备注",
            },
            ChatActionType.task_candidate: {
                "title": "标题",
                "description": "备注",
                "category": "分类",
                "task_type": "类型",
                "due_at": "截止时间",
                "remind_at": "提醒时间",
                "priority": "优先级",
            },
            ChatActionType.diary_candidate: {
                "entry_date": "日期",
                "title": "标题",
                "content": "正文",
                "mood": "心情",
                "weather": "天气",
                "tags": "标签",
            },
        }.get(action_type, {})
        names = [labels.get(field, field) for field in updates]
        return "、".join(names or ["信息"])

    def _task_candidate_response(
        self,
        text: str,
        reply: str | None = None,
        route_confidence: float | None = None,
        fallback_warnings: list[str] | None = None,
        force_rule_based: bool = False,
        function_session: AgentFunctionCallSession | None = None,
    ) -> ChatMessageResponse:
        session = function_session or agent_tool_registry.session()
        parser = self._rule_task_parser if force_rule_based else task_parser
        candidate = session.call(
            "parse_task_candidate",
            {
                "text": self._preview_text(text),
                "source": TaskSource.ai_chat.value,
                "parser": "rule_based" if force_rule_based else "configured",
            },
            lambda: task_candidate_store.save(
                parser.parse_task(ParseTaskRequest(text=text, source=TaskSource.ai_chat))
            ),
            lambda item: f"candidate_id={item.candidate_id}, task_type={item.data.task_type.value}",
        )
        confirmable = task_candidate_store.is_confirmable(candidate)
        waiting_status = (
            ChatAgentStepStatus.needs_confirmation
            if confirmable
            else ChatAgentStepStatus.blocked
        )
        return ChatMessageResponse(
            message_id=uuid4(),
            reply=self._task_candidate_reply(candidate, reply, confirmable),
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
                    "等待确认" if confirmable else "等待补充",
                    "保存前需要你确认候选提醒。" if confirmable else self._task_missing_detail(candidate),
                    waiting_status,
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
        function_session: AgentFunctionCallSession | None = None,
    ) -> ChatMessageResponse:
        session = function_session or agent_tool_registry.session()
        parser = self._rule_bill_parser if force_rule_based else bill_parser
        candidate = session.call(
            "parse_bill_candidate",
            {
                "text": self._preview_text(text),
                "source": BillSource.ai_chat.value,
                "parser": "rule_based" if force_rule_based else "configured",
            },
            lambda: bill_candidate_store.save(
                parser.parse_bill(ParseBillRequest(text=text, source=BillSource.ai_chat))
            ),
            lambda item: f"candidate_id={item.candidate_id}, amount={item.data.amount}, category={item.data.category}",
        )
        session.call(
            "classify_bill_category",
            {
                "text": self._preview_text(text),
                "transaction_type": candidate.data.transaction_type.value,
            },
            lambda: bill_category_classifier.classify(text, candidate.data.transaction_type),
            lambda match: f"category={match.category}, confidence={match.confidence}, source={match.source}",
        )
        confirmable = bill_candidate_store.is_confirmable(candidate)
        waiting_status = (
            ChatAgentStepStatus.needs_confirmation
            if confirmable
            else ChatAgentStepStatus.blocked
        )
        return ChatMessageResponse(
            message_id=uuid4(),
            reply=self._bill_candidate_reply(candidate, reply, confirmable),
            intent=ChatIntent.create_bill,
            confidence=self._combined_confidence(candidate.confidence, route_confidence),
            assistant_tool_id="bill_candidate",
            action_type=ChatActionType.bill_candidate,
            candidate_id=candidate.candidate_id,
            candidate=candidate,
            warnings=self._dedupe(candidate.warnings + (fallback_warnings or [])),
            agent_steps=[
                self._agent_step("理解意图", "识别为记账请求。"),
                self._agent_step("整理候选", "已提取金额、收支类型和可识别信息。"),
                self._agent_step(
                    "等待确认" if confirmable else "等待补充",
                    "保存前需要你确认候选账单。" if confirmable else self._bill_missing_detail(candidate),
                    waiting_status,
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
        function_session: AgentFunctionCallSession | None = None,
    ) -> ChatMessageResponse:
        session = function_session or agent_tool_registry.session()
        resolved_reply = session.call(
            "generate_diary_reflection",
            {"text": self._preview_text(text)},
            lambda: reply or self._diary_reflection_reply(text),
            lambda _: "已生成追问",
        )
        return ChatMessageResponse(
            message_id=uuid4(),
            reply=resolved_reply,
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

    def _diary_candidate_response(
        self,
        text: str,
        reply: str | None = None,
        route_confidence: float | None = None,
        fallback_warnings: list[str] | None = None,
        function_session: AgentFunctionCallSession | None = None,
    ) -> ChatMessageResponse:
        session = function_session or agent_tool_registry.session()
        candidate = session.call(
            "parse_diary_candidate",
            {"text": self._preview_text(text)},
            lambda: diary_candidate_store.save(self._parse_diary_candidate(text)),
            lambda item: f"candidate_id={item.candidate_id}, mood={item.data.mood.value}",
        )
        return ChatMessageResponse(
            message_id=uuid4(),
            reply=reply or "我先整理成一篇待确认日记，你确认后再保存到日记本。",
            intent=ChatIntent.create_diary,
            confidence=self._combined_confidence(candidate.confidence, route_confidence),
            assistant_tool_id="diary_candidate",
            action_type=ChatActionType.diary_candidate,
            candidate_id=candidate.candidate_id,
            candidate=candidate,
            warnings=self._dedupe(candidate.warnings + (fallback_warnings or [])),
            agent_steps=[
                self._agent_step("理解意图", "识别为写日记或记录生活片段。"),
                self._agent_step("整理候选", "已整理日期、标题、心情、天气、标签和正文。"),
                self._agent_step(
                    "等待确认",
                    "保存前需要你确认候选日记。",
                    ChatAgentStepStatus.needs_confirmation,
                ),
            ],
            need_user_confirmation=True,
        )

    def _bill_candidate_reply(
        self,
        candidate,
        preferred_reply: str | None,
        confirmable: bool,
    ) -> str:
        if confirmable:
            return preferred_reply or "我先整理成一个待确认账单，你确认或修改后再保存。"
        missing = "、".join(self._bill_missing_fields(candidate))
        return f"我看出这是记账请求，但还缺{missing}。请补充一下，也可以点编辑把字段补齐。"

    def _bill_missing_detail(self, candidate) -> str:
        missing = "、".join(self._bill_missing_fields(candidate))
        return f"缺少{missing}，暂时不能确认保存。"

    def _bill_missing_fields(self, candidate) -> list[str]:
        fields: list[str] = []
        if candidate.data.amount is None:
            fields.append("金额")
        return fields or ["必要字段"]

    def _task_candidate_reply(
        self,
        candidate,
        preferred_reply: str | None,
        confirmable: bool,
    ) -> str:
        if confirmable:
            return preferred_reply or "我先整理成一个待确认事项，你确认或修改后再保存。"
        missing = "、".join(self._task_missing_fields(candidate))
        return f"我看出这是提醒或待办请求，但还缺{missing}。请补充一下，也可以点编辑把字段补齐。"

    def _task_missing_detail(self, candidate) -> str:
        missing = "、".join(self._task_missing_fields(candidate))
        return f"缺少{missing}，暂时不能确认保存。"

    def _task_missing_fields(self, candidate) -> list[str]:
        fields: list[str] = []
        if candidate.data.title is None:
            fields.append("标题")
        if candidate.data.task_type == TaskType.reminder and candidate.data.remind_at is None:
            fields.append("提醒时间")
        return fields or ["必要字段"]

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

    def _context_action_result(self, response: ChatMessageResponse) -> str:
        if response.created_bill or response.created_task or response.created_diary:
            return "候选记录已保存为正式记录"
        if response.discarded:
            return "候选记录已丢弃"
        if response.updated_existing_candidate:
            return "候选记录已更新"
        if response.need_user_confirmation:
            return "候选记录等待确认或补充"
        return "已完成上下文操作"

    def _should_force_rule_based_parser(self, warnings: list[str]) -> bool:
        return any(
            warning
            in {
                "external_ai_parser_failed",
                "external_ai_parser_invalid_response",
                "external_ai_parser_skipped",
                "external_chat_intent_invalid_response",
                "llm_agent_failed",
                "llm_agent_invalid_response",
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
        if any(keyword in text for keyword in ("提醒", "待办", "任务", "记得", "别忘", "todo")):
            return True
        if self._looks_like_bill(text):
            return False
        return any(keyword.casefold() in text.casefold() for keyword in self._task_keywords)

    def _looks_like_diary(self, text: str) -> bool:
        folded = text.casefold()
        return any(keyword.casefold() in folded for keyword in self._diary_keywords)

    def _looks_like_diary_entry(self, text: str) -> bool:
        folded = text.casefold()
        entry_markers = ("写日记", "记日记", "记录今天", "记录一下", "今天的日记", "日记：", "日记:")
        return any(marker.casefold() in folded for marker in entry_markers)

    def _parse_diary_candidate(self, text: str) -> ParseDiaryResponse:
        content = self._clean_diary_text(text)
        entry_date = self._diary_entry_date(text)
        mood = self._diary_mood(text)
        weather = self._diary_weather(text)
        title = self._diary_title(content, mood)
        tags = self._diary_tags(text, mood)
        data = DiaryCandidateData(
            entry_date=entry_date,
            title=title,
            content=content,
            mood=mood,
            weather=weather,
            source=DiarySource.ai_chat,
            tags=tags,
        )
        field_confidence = {
            "entry_date": 0.9,
            "title": 0.75 if title else 0.0,
            "content": 0.86 if len(content) >= 10 else 0.45,
            "mood": 0.72,
            "weather": 0.75 if weather else 0.0,
            "tags": 0.78 if tags else 0.0,
        }
        warnings: list[str] = []
        if len(content) < 10:
            warnings.append("content_too_short")
        if not weather:
            warnings.append("weather_missing")
        if not tags:
            warnings.append("tags_missing")
        confidence = round(
            (field_confidence["entry_date"] + field_confidence["title"] + field_confidence["content"] + field_confidence["mood"]) / 4,
            2,
        )
        return ParseDiaryResponse(
            candidate_id=uuid4(),
            confidence=confidence,
            data=data,
            field_confidence=field_confidence,
            warnings=warnings,
            need_user_confirmation=True,
        )

    def _clean_diary_text(self, text: str) -> str:
        cleaned = text.strip()
        for prefix in ("写日记", "记日记", "记录今天", "记录一下", "今天的日记", "日记：", "日记:"):
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip(" ：:\n")
                break
        return cleaned or text.strip()

    def _diary_entry_date(self, text: str) -> date:
        today = date.today()
        if "昨天" in text:
            return today - timedelta(days=1)
        if "明天" in text:
            return today + timedelta(days=1)
        return today

    def _diary_mood(self, text: str) -> DiaryMood:
        if any(keyword in text for keyword in ("开心", "高兴", "满足", "轻松", "治愈", "快乐")):
            return DiaryMood.happy
        if any(keyword in text for keyword in ("累", "疲惫", "困", "加班")):
            return DiaryMood.tired
        if any(keyword in text for keyword in ("焦虑", "紧张", "担心", "压力")):
            return DiaryMood.anxious
        if any(keyword in text for keyword in ("难过", "失落", "伤心")):
            return DiaryMood.sad
        return DiaryMood.calm

    def _diary_weather(self, text: str) -> str | None:
        for weather in ("晴天", "多云", "阴天", "下雨", "雨天", "下雪", "雪天"):
            if weather in text:
                return "雨天" if weather == "下雨" else "雪天" if weather == "下雪" else weather
        return None

    def _diary_title(self, content: str, mood: DiaryMood) -> str:
        compact = re.sub(r"\s+", " ", content).strip(" ，。,.")
        if compact:
            return compact[:24]
        return {
            DiaryMood.happy: "开心的一天",
            DiaryMood.tired: "有点累的一天",
            DiaryMood.anxious: "需要慢下来的日子",
            DiaryMood.sad: "想被好好安放的一天",
            DiaryMood.calm: "平静的一天",
        }[mood]

    def _diary_tags(self, text: str, mood: DiaryMood) -> list[str]:
        tags: list[str] = []
        mood_tag = {
            DiaryMood.happy: "开心",
            DiaryMood.tired: "疲惫",
            DiaryMood.anxious: "焦虑",
            DiaryMood.sad: "难过",
            DiaryMood.calm: "平静",
        }[mood]
        tags.append(mood_tag)
        keyword_tags = {
            "工作": "工作",
            "学习": "学习",
            "朋友": "朋友",
            "家人": "家庭",
            "运动": "健康",
            "跑步": "健康",
            "咖啡": "生活",
            "复盘": "成长",
            "感谢": "感恩",
        }
        for keyword, tag in keyword_tags.items():
            if keyword in text and tag not in tags:
                tags.append(tag)
        return tags[:6]

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
