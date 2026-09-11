from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from pydantic import ValidationError

from app.core.config import settings
from app.schemas.agent import (
    BillCandidateData,
    ParseBillRequest,
    ParseBillResponse,
    ParseTaskRequest,
    ParseTaskResponse,
    TaskCandidateData,
)
from app.schemas.chat import ChatIntent
from app.schemas.task import TaskPriority, TaskType
from app.services.agent_knowledge_base import agent_knowledge_base
from app.services.agent_tool_registry import agent_tool_registry
from app.services.bill_category_classifier import bill_category_classifier
from app.services.settings_store import settings_store


@dataclass(frozen=True)
class ExternalChatRoute:
    intent: ChatIntent
    confidence: float
    reply: str | None
    warnings: list[str]


class ExternalAiParserService:
    _bill_categories = (
        "餐饮",
        "交通",
        "购物",
        "日用",
        "娱乐",
        "医疗",
        "学习",
        "住房",
        "通讯",
        "旅行",
        "人情",
        "订阅",
        "工资",
        "退款",
        "转账",
        "其他",
    )

    def route_chat(self, text: str) -> tuple[ExternalChatRoute | None, list[str]]:
        if not settings.real_ai_parser_enabled:
            return None, []

        skipped_warnings = self._privacy_skip_warnings()
        if skipped_warnings:
            return None, skipped_warnings

        response_body, request_warnings = self._request("chat_intent", text, "ai_chat")
        if response_body is None:
            return None, request_warnings

        try:
            intent = ChatIntent(str(response_body.get("intent")))
        except ValueError:
            return None, [*request_warnings, "external_chat_intent_invalid_response"]

        return (
            ExternalChatRoute(
                intent=intent,
                confidence=self._confidence(response_body.get("confidence"), 0.65),
                reply=self._optional_text(response_body.get("reply")),
                warnings=self._dedupe(request_warnings + self._response_warnings(response_body)),
            ),
            [],
        )

    def parse_bill(
        self,
        payload: ParseBillRequest,
    ) -> tuple[ParseBillResponse | None, list[str]]:
        if not settings.real_ai_parser_enabled:
            return None, []

        skipped_warnings = self._privacy_skip_warnings()
        if skipped_warnings:
            return None, skipped_warnings

        response_body, request_warnings = self._request(
            "bill",
            payload.text,
            payload.source.value,
        )
        if response_body is None:
            return None, request_warnings

        try:
            raw_data = self._response_data(response_body)
            raw_data["source"] = payload.source.value
            data = BillCandidateData.model_validate(raw_data)
            data, category_confidence = self._refine_bill_category(payload.text, data)
        except (TypeError, ValueError, ValidationError):
            return None, self._dedupe([*request_warnings, "external_ai_parser_invalid_response"])

        fallback_field_confidence = self._bill_field_confidence(data)
        if category_confidence is not None:
            fallback_field_confidence["category"] = category_confidence
        field_confidence = self._field_confidence(
            response_body.get("field_confidence"),
            fallback_field_confidence,
        )
        if category_confidence is not None:
            field_confidence["category"] = max(
                field_confidence.get("category", 0.0),
                category_confidence,
            )
        warnings = self._dedupe(
            request_warnings + self._bill_warnings(data) + self._response_warnings(response_body)
        )
        return (
            ParseBillResponse(
                candidate_id=uuid4(),
                confidence=self._confidence(
                    response_body.get("confidence"),
                    self._bill_overall_confidence(field_confidence),
                ),
                data=data,
                field_confidence=field_confidence,
                warnings=warnings,
                need_user_confirmation=True,
            ),
            [],
        )

    def parse_task(
        self,
        payload: ParseTaskRequest,
    ) -> tuple[ParseTaskResponse | None, list[str]]:
        if not settings.real_ai_parser_enabled:
            return None, []

        skipped_warnings = self._privacy_skip_warnings()
        if skipped_warnings:
            return None, skipped_warnings

        response_body, request_warnings = self._request(
            "task",
            payload.text,
            payload.source.value,
        )
        if response_body is None:
            return None, request_warnings

        try:
            raw_data = self._response_data(response_body)
            raw_data["source"] = payload.source.value
            data = TaskCandidateData.model_validate(raw_data)
        except (TypeError, ValueError, ValidationError):
            return None, self._dedupe([*request_warnings, "external_ai_parser_invalid_response"])

        field_confidence = self._field_confidence(
            response_body.get("field_confidence"),
            self._task_field_confidence(data),
        )
        warnings = self._dedupe(
            request_warnings + self._task_warnings(data) + self._response_warnings(response_body)
        )
        return (
            ParseTaskResponse(
                candidate_id=uuid4(),
                confidence=self._confidence(
                    response_body.get("confidence"),
                    self._task_overall_confidence(field_confidence, data.task_type),
                ),
                data=data,
                field_confidence=field_confidence,
                warnings=warnings,
                need_user_confirmation=True,
            ),
            [],
        )

    def _privacy_skip_warnings(self) -> list[str]:
        privacy_settings = settings_store.get_privacy_settings()
        if privacy_settings.local_only_mode:
            return ["local_only_mode_enabled", "external_ai_parser_skipped"]
        if not privacy_settings.allow_ai_text_processing:
            return ["ai_text_processing_disabled", "external_ai_parser_skipped"]
        return []

    def _request(
        self,
        kind: str,
        text: str,
        source: str,
    ) -> tuple[dict[str, Any] | None, list[str]]:
        if settings.real_llm_agent_enabled:
            return self._request_llm_agent(kind, text, source)
        return self._request_external_parser(kind, text, source)

    def _request_external_parser(
        self,
        kind: str,
        text: str,
        source: str,
    ) -> tuple[dict[str, Any] | None, list[str]]:
        endpoint = settings.external_ai_parser_endpoint
        if endpoint is None:
            return None, []

        request_body = self._provider_payload(kind, text, source)
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if settings.external_ai_parser_api_key:
            headers["Authorization"] = f"Bearer {settings.external_ai_parser_api_key}"

        request = Request(
            endpoint,
            data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(
                request,
                timeout=settings.external_ai_parser_timeout_seconds,
            ) as response:
                response_text = response.read().decode("utf-8")
            response_body = json.loads(response_text)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            return None, ["external_ai_parser_failed"]

        if not isinstance(response_body, dict):
            return None, ["external_ai_parser_invalid_response"]
        return response_body, []

    def _request_llm_agent(
        self,
        kind: str,
        text: str,
        source: str,
    ) -> tuple[dict[str, Any] | None, list[str]]:
        endpoint = self._llm_chat_completions_url(settings.llm_agent_base_url)
        if endpoint is None or settings.llm_agent_runtime_model is None:
            return None, []
        api_key = settings.llm_agent_api_key_for_kind(kind)

        messages = [
            {"role": "system", "content": self._llm_system_prompt(kind)},
            {
                "role": "user",
                "content": json.dumps(
                    self._llm_user_payload(kind, text, source),
                    ensure_ascii=False,
                ),
            },
        ]
        request_body = self._llm_request_body(kind, messages, include_tools=True)
        response_body, request_warnings = self._post_llm_agent_json(endpoint, request_body, api_key)
        if response_body is None and request_body.get("tools"):
            fallback_body = self._llm_request_body(kind, messages, include_tools=False)
            response_body, fallback_warnings = self._post_llm_agent_json(endpoint, fallback_body, api_key)
            if response_body is None:
                return None, request_warnings or fallback_warnings
            request_warnings = ["llm_agent_function_calling_unavailable"]
        if response_body is None:
            return None, request_warnings

        try:
            response_body = self._complete_llm_tool_calls(
                endpoint,
                kind,
                text,
                messages,
                response_body,
                api_key,
            )
            content = self._llm_response_content(response_body)
            return self._json_object_from_text(content), request_warnings
        except (ValueError, TypeError, KeyError, json.JSONDecodeError):
            return None, ["llm_agent_invalid_response", "external_ai_parser_invalid_response"]

    def _llm_request_body(
        self,
        kind: str,
        messages: list[dict[str, Any]],
        *,
        include_tools: bool,
    ) -> dict[str, Any]:
        request_body: dict[str, Any] = {
            "model": settings.llm_agent_runtime_model,
            "messages": messages,
            "temperature": settings.llm_agent_temperature,
        }
        self._apply_llm_provider_options(request_body)
        if settings.llm_agent_response_format.casefold() == "json_object":
            request_body["response_format"] = {"type": "json_object"}
        if include_tools:
            tools = agent_tool_registry.llm_tool_definitions(kind)
            if tools:
                request_body["tools"] = tools
                request_body["tool_choice"] = "auto"
        return request_body

    def _apply_llm_provider_options(self, request_body: dict[str, Any]) -> None:
        if not settings.deepseek_llm_agent_enabled:
            return

        request_body["stream"] = False
        reasoning_effort = self._deepseek_reasoning_effort(settings.llm_agent_reasoning_effort)
        request_body["reasoning_effort"] = reasoning_effort
        request_body["thinking"] = {
            "type": "disabled" if reasoning_effort == "none" else "enabled"
        }

    def _deepseek_reasoning_effort(self, raw_value: str | None) -> str:
        if raw_value is None:
            return "none"
        value = raw_value.strip().casefold()
        aliases = {"minimal": "low", "medium": "high", "xhigh": "high"}
        value = aliases.get(value, value)
        if value not in {"none", "low", "high", "max"}:
            return "none"
        return value

    def _post_llm_agent_json(
        self,
        endpoint: str,
        request_body: dict[str, Any],
        api_key: str | None,
    ) -> tuple[dict[str, Any] | None, list[str]]:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        request = Request(
            endpoint,
            data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(request, timeout=settings.llm_agent_timeout_seconds) as response:
                response_text = response.read().decode("utf-8")
            response_body = json.loads(response_text)
        except (HTTPError, URLError, TimeoutError, OSError, ValueError):
            return None, ["llm_agent_failed", "external_ai_parser_failed"]

        if not isinstance(response_body, dict):
            return None, ["llm_agent_invalid_response", "external_ai_parser_invalid_response"]
        return response_body, []

    def _complete_llm_tool_calls(
        self,
        endpoint: str,
        kind: str,
        original_text: str,
        messages: list[dict[str, Any]],
        response_body: dict[str, Any],
        api_key: str | None,
    ) -> dict[str, Any]:
        assistant_message = self._llm_response_message(response_body)
        tool_calls = self._llm_tool_calls(assistant_message)
        if not tool_calls:
            return response_body

        tool_messages = self._llm_tool_messages(tool_calls, original_text)
        if not tool_messages:
            return response_body

        follow_up_messages = [
            *messages,
            self._assistant_tool_call_message(assistant_message, tool_calls),
            *tool_messages,
        ]
        follow_up_body = self._llm_request_body(kind, follow_up_messages, include_tools=False)
        follow_up_response, _ = self._post_llm_agent_json(endpoint, follow_up_body, api_key)
        if follow_up_response is None:
            raise ValueError("LLM tool-call follow-up failed.")
        return follow_up_response

    def _assistant_tool_call_message(
        self,
        message: dict[str, Any],
        tool_calls: list[dict[str, Any]],
    ) -> dict[str, Any]:
        content = message.get("content")
        return {
            "role": "assistant",
            "content": content if isinstance(content, str) else None,
            "tool_calls": tool_calls,
        }

    def _llm_tool_calls(self, message: dict[str, Any]) -> list[dict[str, Any]]:
        raw_tool_calls = message.get("tool_calls")
        if not isinstance(raw_tool_calls, list):
            return []

        tool_calls: list[dict[str, Any]] = []
        for raw_call in raw_tool_calls[:4]:
            if not isinstance(raw_call, dict):
                continue
            function = raw_call.get("function")
            if not isinstance(function, dict):
                continue
            call_id = raw_call.get("id")
            name = function.get("name")
            if not isinstance(call_id, str) or not isinstance(name, str):
                continue
            arguments = function.get("arguments")
            tool_calls.append(
                {
                    "id": call_id,
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": arguments if isinstance(arguments, str) else "{}",
                    },
                }
            )
        return tool_calls

    def _llm_tool_messages(
        self,
        tool_calls: list[dict[str, Any]],
        original_text: str,
    ) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        for tool_call in tool_calls:
            function = tool_call["function"]
            name = function["name"]
            arguments = self._tool_call_arguments(function.get("arguments"))
            result = self._execute_llm_read_tool(name, arguments, original_text)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )
        return messages

    def _tool_call_arguments(self, raw_arguments: Any) -> dict[str, Any]:
        if not isinstance(raw_arguments, str) or not raw_arguments.strip():
            return {}
        try:
            parsed = json.loads(raw_arguments)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        return parsed

    def _execute_llm_read_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        original_text: str,
    ) -> dict[str, Any]:
        if name == "knowledge_search":
            query = self._optional_text(arguments.get("query")) or original_text
            limit = self._tool_limit(arguments.get("limit"), default=3, maximum=5)
            hits = agent_knowledge_base.search(query, limit=limit)
            return {"hits": [hit.model_dump(mode="json") for hit in hits]}

        if name == "classify_bill_category":
            text = self._optional_text(arguments.get("text")) or original_text
            transaction_type = self._optional_text(arguments.get("transaction_type"))
            match = bill_category_classifier.classify(text, transaction_type)
            return {
                "category": match.category,
                "confidence": match.confidence,
                "source": match.source,
                "matched_keywords": list(match.matched_keywords),
            }

        if name == "analyze_bills":
            return {
                "analysis_available": True,
                "privacy": "financial_values_redacted_for_external_model",
                "instruction": "Return intent analyze_bills. The backend will compute charts and assessment locally.",
            }

        return {"error": "unsupported_agent_tool", "name": name}

    def _tool_limit(self, raw_value: Any, *, default: int, maximum: int) -> int:
        try:
            value = int(raw_value)
        except (TypeError, ValueError):
            return default
        return max(1, min(maximum, value))

    def _provider_payload(self, kind: str, text: str, source: str) -> dict[str, Any]:
        return {
            "schema_version": "lifesnap.ai.parse.v1",
            "kind": kind,
            "text": text,
            "source": source,
            "locale": "zh-CN",
            "current_datetime": datetime.now().astimezone().isoformat(),
        }

    def _llm_user_payload(self, kind: str, text: str, source: str) -> dict[str, Any]:
        payload = self._provider_payload(kind, text, source)
        payload["retrieved_knowledge"] = [
            hit.model_dump(mode="json") for hit in agent_knowledge_base.search(text, limit=3)
        ]
        payload["mvp_scope"] = {
            "allowed_intents": [
                "create_bill",
                "create_task",
                "create_diary",
                "diary_reflection",
                "analyze_bills",
                "knowledge_answer",
                "unsupported",
            ],
            "unsupported_examples": ["subscription_auto_create", "warranty_auto_create", "non_bill_cross_record_search"],
            "confirmation_required": True,
        }
        payload["output_contract"] = self._llm_output_contract(kind)
        return payload

    def _llm_output_contract(self, kind: str) -> dict[str, Any]:
        if kind == "chat_intent":
            return {
                "intent": "create_bill | create_task | create_diary | diary_reflection | analyze_bills | knowledge_answer | unsupported",
                "confidence": "number from 0 to 1",
                "reply": "short Chinese reply or clarification question",
                "warnings": "array of stable warning strings",
            }
        if kind == "bill":
            return {
                "confidence": "number from 0 to 1",
                "data": {
                    "amount": "decimal string or null",
                    "currency": "CNY",
                    "merchant": "merchant/payee string or null",
                    "category": "one of allowed categories",
                    "payment_method": "payment method string or null",
                    "paid_at": "ISO 8601 datetime with timezone or null",
                    "transaction_type": "expense | income | refund | transfer | top_up",
                    "note": "short Chinese note or null",
                },
                "field_confidence": {
                    "amount": "number from 0 to 1",
                    "merchant": "number from 0 to 1",
                    "category": "number from 0 to 1",
                    "payment_method": "number from 0 to 1",
                    "paid_at": "number from 0 to 1",
                    "transaction_type": "number from 0 to 1",
                },
                "warnings": "array of stable warning strings",
                "need_user_confirmation": True,
            }
        return {
            "confidence": "number from 0 to 1",
            "data": {
                "title": "short title or null",
                "description": "details from input or null",
                "category": "生活 | 工作 | 学习 | 财务 | 医疗 | 居住 or another concise category",
                "task_type": "todo | reminder",
                "due_at": "ISO 8601 datetime with timezone or null",
                "remind_at": "ISO 8601 datetime with timezone or null",
                "priority": "low | medium | high",
            },
            "field_confidence": {
                "title": "number from 0 to 1",
                "category": "number from 0 to 1",
                "task_type": "number from 0 to 1",
                "due_at": "number from 0 to 1",
                "remind_at": "number from 0 to 1",
                "priority": "number from 0 to 1",
            },
            "warnings": "array of stable warning strings",
            "need_user_confirmation": True,
        }

    def _llm_system_prompt(self, kind: str) -> str:
        shared = (
            "你是 LifeSnap AI 小事管家的 MVP Agent。"
            "你的任务是把用户自然语言或 OCR 文本转换为可确认的候选结果，不能直接创建正式数据。"
            "只输出一个 JSON object，不要 Markdown，不要解释。"
            "未知字段用 null，不要编造金额、商户或时间。"
            "所有 confidence 和 field_confidence 必须在 0 到 1 之间。"
            "source 以用户 payload 为准，不要改写。"
            "如果接口提供了 tools，优先通过 tool_calls 检索知识或判断分类，再输出最终 JSON。"
        )
        if kind == "chat_intent":
            return (
                shared
                + "判断用户意图，只允许 create_bill、create_task、create_diary、diary_reflection、analyze_bills、knowledge_answer、unsupported。"
                + "当用户询问本月或某月账单、支出、收入、分类占比、商户排行、趋势、环比、预算或消费分析时，返回 analyze_bills，不要编造统计数字。"
                + "当用户询问 Agent 自身、RAG 知识库、函数调用、工具链、模型策略或微调时，返回 knowledge_answer。"
                + "订阅、保修和非账单类跨记录搜索属于非 MVP，除非能降级为普通账单或待办，否则返回 unsupported。"
                + "如果缺少关键信息，reply 要用一句中文追问。"
            )
        if kind == "bill":
            return (
                shared
                + f"抽取账单候选。category 优先从 {list(self._bill_categories)} 中选择。"
                + "transaction_type 根据语义选择：消费为 expense，工资/收款为 income，退款为 refund，转账为 transfer，充值为 top_up。"
                + "分类参考：餐饮含咖啡、外卖、饭店、奶茶；交通含打车、地铁、公交、高铁、停车、加油；购物含淘宝、京东、衣服、数码；日用含超市、便利店、买菜、纸巾；医疗含医院、药店、买药；娱乐含电影、游戏、会员；学习含课程、书籍、考试；住房含房租、物业、水电、燃气、宽带。"
                + "用户明确说分类、类别、归类、记到或算作时，以用户指定分类为准。居住归一为住房，工资收入归一为工资。"
                + "如果文本没有支付时间，paid_at 返回 null；如果只有相对时间，可用 current_datetime 解析。"
                + "只有金额是确认前必须具备的信息；商户、分类、支付方式、支付时间和备注都是选填。金额缺失时保留候选并在 warnings 中标记 amount_missing。"
            )
        return (
            shared
            + "抽取待办或提醒候选。明确要求提醒、闹钟、到点通知时 task_type=reminder 且需要 remind_at；普通事项用 todo。"
            + "没有具体提醒时间时 remind_at 返回 null，并在 warnings 中标记 remind_time_missing。"
            + "标题缺失时 title 返回 null，并在 warnings 中标记 title_missing。"
        )

    def _llm_chat_completions_url(self, base_url: str | None) -> str | None:
        if not base_url:
            return None
        url = base_url.rstrip("/")
        if url.endswith("/chat/completions"):
            return url
        return f"{url}/chat/completions"

    def _llm_response_content(self, response_body: dict[str, Any]) -> str:
        message = self._llm_response_message(response_body)
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    parts.append(part["text"])
            if parts:
                return "".join(parts)
        raise ValueError("LLM message content must be text.")

    def _llm_response_message(self, response_body: dict[str, Any]) -> dict[str, Any]:
        choices = response_body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("LLM response must include choices.")
        choice = choices[0]
        if not isinstance(choice, dict):
            raise ValueError("LLM choice must be an object.")
        message = choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("LLM choice must include a message object.")
        return message

    def _json_object_from_text(self, text: str) -> dict[str, Any]:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
            if match is None:
                raise
            parsed = json.loads(match.group(0))
        if not isinstance(parsed, dict):
            raise TypeError("LLM content must be a JSON object.")
        return parsed

    def _response_data(self, response_body: dict[str, Any]) -> dict[str, Any]:
        raw_data = response_body.get("data")
        if raw_data is None:
            raw_data = response_body
        if not isinstance(raw_data, dict):
            raise TypeError("External AI parser response data must be an object.")
        return self._normalize_empty_strings(dict(raw_data))

    def _normalize_empty_strings(self, data: dict[str, Any]) -> dict[str, Any]:
        blank_defaults = {
            "currency": "CNY",
            "category": "其他",
            "transaction_type": "expense",
            "task_type": "todo",
            "priority": "medium",
        }
        normalized: dict[str, Any] = {}
        for key, value in data.items():
            if isinstance(value, str) and not value.strip():
                normalized[key] = blank_defaults.get(key)
            else:
                normalized[key] = value
        return normalized

    def _response_warnings(self, response_body: dict[str, Any]) -> list[str]:
        warnings = response_body.get("warnings")
        if not isinstance(warnings, list):
            return []
        return [str(warning) for warning in warnings if str(warning).strip()]

    def _optional_text(self, raw_value: Any) -> str | None:
        if not isinstance(raw_value, str):
            return None
        text = raw_value.strip()
        return text or None

    def _field_confidence(
        self,
        raw_confidence: Any,
        fallback_confidence: dict[str, float],
    ) -> dict[str, float]:
        confidence = dict(fallback_confidence)
        if not isinstance(raw_confidence, dict):
            return confidence

        for key, value in raw_confidence.items():
            parsed_value = self._optional_confidence(value)
            if parsed_value is not None:
                confidence[str(key)] = parsed_value
        return confidence

    def _confidence(self, raw_value: Any, fallback: float) -> float:
        parsed_value = self._optional_confidence(raw_value)
        if parsed_value is None:
            return fallback
        return parsed_value

    def _optional_confidence(self, raw_value: Any) -> float | None:
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            return None
        return round(min(1.0, max(0.0, value)), 2)

    def _bill_warnings(self, data: BillCandidateData) -> list[str]:
        warnings: list[str] = []
        if data.amount is None:
            warnings.append("amount_missing")
        return warnings

    def _refine_bill_category(
        self,
        text: str,
        data: BillCandidateData,
    ) -> tuple[BillCandidateData, float | None]:
        normalized_category = bill_category_classifier.normalize_category(data.category)
        category_match = bill_category_classifier.classify(text, data.transaction_type)

        category = normalized_category
        confidence: float | None = None
        if normalized_category == "其他" and category_match.category != "其他":
            category = category_match.category
            confidence = category_match.confidence
        elif normalized_category != data.category:
            category = normalized_category
            confidence = 0.82 if normalized_category != "其他" else None

        if category == data.category:
            return data, confidence
        return data.model_copy(update={"category": category}), confidence

    def _bill_field_confidence(self, data: BillCandidateData) -> dict[str, float]:
        return {
            "amount": 0.9 if data.amount is not None else 0.0,
            "merchant": 0.85 if data.merchant is not None else 0.0,
            "category": 0.8 if data.category != "其他" else 0.45,
            "payment_method": 0.8 if data.payment_method is not None else 0.0,
            "paid_at": 0.8 if data.paid_at is not None else 0.0,
            "transaction_type": 0.9,
        }

    def _bill_overall_confidence(self, field_confidence: dict[str, float]) -> float:
        important_fields = ["amount", "transaction_type"]
        score = sum(
            field_confidence.get(field, 0.0) for field in important_fields
        ) / len(important_fields)
        return round(score, 2)

    def _task_warnings(self, data: TaskCandidateData) -> list[str]:
        warnings: list[str] = []
        if data.title is None:
            warnings.append("title_missing")
        if data.category == "生活":
            warnings.append("category_low_confidence")
        if data.task_type == TaskType.reminder and data.remind_at is None:
            warnings.append("remind_time_missing")
        return warnings

    def _task_field_confidence(self, data: TaskCandidateData) -> dict[str, float]:
        return {
            "title": 0.85 if data.title is not None else 0.0,
            "category": 0.8 if data.category != "生活" else 0.45,
            "task_type": 0.85 if data.task_type == TaskType.reminder else 0.65,
            "due_at": 0.8 if data.due_at is not None else 0.0,
            "remind_at": 0.85 if data.remind_at is not None else 0.0,
            "priority": 0.8 if data.priority != TaskPriority.medium else 0.55,
        }

    def _task_overall_confidence(
        self,
        field_confidence: dict[str, float],
        task_type: TaskType,
    ) -> float:
        important_fields = ["title", "category", "task_type", "priority"]
        if task_type == TaskType.reminder:
            important_fields.append("remind_at")
        score = sum(
            field_confidence.get(field, 0.0) for field in important_fields
        ) / len(important_fields)
        return round(score, 2)

    def _dedupe(self, warnings: list[str]) -> list[str]:
        deduped: list[str] = []
        for warning in warnings:
            if warning not in deduped:
                deduped.append(warning)
        return deduped


external_ai_parser = ExternalAiParserService()
