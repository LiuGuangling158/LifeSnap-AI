from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar

from app.schemas.agent_runtime import AgentFunctionCallTrace, AgentFunctionToolCapability

T = TypeVar("T")


class AgentToolNotFoundError(ValueError):
    pass


class AgentToolRegistry:
    _tools = (
        AgentFunctionToolCapability(
            name="privacy_guard",
            label="检查隐私授权",
            description="检查当前隐私设置是否允许 Agent 对文本做解析。",
            input_schema={"scope": "string"},
            side_effect="read",
        ),
        AgentFunctionToolCapability(
            name="knowledge_search",
            label="检索知识库",
            description="从 LifeSnap 内置业务知识库检索相关规则和策略。",
            input_schema={"query": "string", "limit": "integer"},
            side_effect="read",
        ),
        AgentFunctionToolCapability(
            name="route_chat_intent",
            label="识别用户意图",
            description="判断用户是在记账、建提醒、写日记、追问日记，还是请求未支持能力。",
            input_schema={"message": "string"},
            side_effect="read",
        ),
        AgentFunctionToolCapability(
            name="parse_bill_candidate",
            label="解析账单候选",
            description="抽取金额、收支类型、分类、商家/用途、支付方式和时间。",
            input_schema={"text": "string", "source": "BillSource"},
            requires_confirmation=True,
            side_effect="candidate_write",
        ),
        AgentFunctionToolCapability(
            name="classify_bill_category",
            label="判断花销分类",
            description="按显式分类、商家、物品和场景关键词判断账单分类。",
            input_schema={"text": "string", "transaction_type": "TransactionType"},
            side_effect="read",
        ),
        AgentFunctionToolCapability(
            name="parse_task_candidate",
            label="解析待办候选",
            description="抽取事项标题、提醒时间、截止时间、分类和优先级。",
            input_schema={"text": "string", "source": "TaskSource"},
            requires_confirmation=True,
            side_effect="candidate_write",
        ),
        AgentFunctionToolCapability(
            name="parse_diary_candidate",
            label="整理日记候选",
            description="整理日期、标题、正文、心情、天气和标签。",
            input_schema={"text": "string"},
            requires_confirmation=True,
            side_effect="candidate_write",
        ),
        AgentFunctionToolCapability(
            name="generate_diary_reflection",
            label="生成日记追问",
            description="围绕心情、感谢、学习和生活片段生成引导问题。",
            input_schema={"text": "string"},
            side_effect="read",
        ),
        AgentFunctionToolCapability(
            name="update_candidate",
            label="更新候选记录",
            description="根据用户后续补充修改当前待确认候选。",
            input_schema={"candidate_id": "uuid", "fields": "object"},
            requires_confirmation=True,
            side_effect="candidate_write",
        ),
        AgentFunctionToolCapability(
            name="confirm_candidate",
            label="确认保存候选",
            description="在用户确认后把候选写入正式账单、待办或日记。",
            input_schema={"candidate_id": "uuid", "action_type": "ChatActionType"},
            requires_confirmation=True,
            side_effect="record_write",
        ),
        AgentFunctionToolCapability(
            name="discard_candidate",
            label="丢弃候选记录",
            description="按用户要求删除当前待确认候选。",
            input_schema={"candidate_id": "uuid", "action_type": "ChatActionType"},
            side_effect="candidate_delete",
        ),
    )

    def all(self) -> list[AgentFunctionToolCapability]:
        return list(self._tools)

    def get(self, name: str) -> AgentFunctionToolCapability | None:
        for tool in self._tools:
            if tool.name == name:
                return tool
        return None

    def require(self, name: str) -> AgentFunctionToolCapability:
        tool = self.get(name)
        if tool is None:
            raise AgentToolNotFoundError(f"Unknown Agent tool: {name}")
        return tool

    def session(self) -> AgentFunctionCallSession:
        return AgentFunctionCallSession(self)

    def trace(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        result: str = "completed",
        status: str = "completed",
    ) -> AgentFunctionCallTrace:
        tool = self.require(name)
        return AgentFunctionCallTrace(
            name=name,
            label=tool.label,
            arguments=arguments or {},
            result=self._clip_result(result),
            status=status,
        )

    def llm_tool_definitions(self, kind: str) -> list[dict[str, Any]]:
        names_by_kind = {
            "chat_intent": ("knowledge_search",),
            "bill": ("knowledge_search", "classify_bill_category"),
            "task": ("knowledge_search",),
        }
        return [
            self._llm_tool_definition(self.require(name))
            for name in names_by_kind.get(kind, ("knowledge_search",))
        ]

    def _llm_tool_definition(self, tool: AgentFunctionToolCapability) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": self._json_schema(tool.input_schema),
            },
        }

    def _json_schema(self, input_schema: dict[str, Any]) -> dict[str, Any]:
        properties: dict[str, Any] = {}
        required: list[str] = []
        for name, raw_type in input_schema.items():
            json_type = self._json_schema_type(str(raw_type))
            properties[name] = {"type": json_type}
            if name in {"query", "text", "message"}:
                required.append(name)
        return {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        }

    def _json_schema_type(self, raw_type: str) -> str:
        if raw_type in {"integer"}:
            return "integer"
        if raw_type in {"number", "float"}:
            return "number"
        if raw_type in {"boolean", "bool"}:
            return "boolean"
        if raw_type in {"object"}:
            return "object"
        return "string"

    def _clip_result(self, result: str, max_length: int = 180) -> str:
        cleaned = " ".join(str(result or "completed").split())
        if len(cleaned) <= max_length:
            return cleaned
        return f"{cleaned[: max_length - 1]}…"


class AgentFunctionCallSession:
    def __init__(self, registry: AgentToolRegistry) -> None:
        self._registry = registry
        self._calls: list[AgentFunctionCallTrace] = []

    @property
    def traces(self) -> list[AgentFunctionCallTrace]:
        return list(self._calls)

    def call(
        self,
        name: str,
        arguments: dict[str, Any] | None,
        handler: Callable[[], T],
        result_formatter: Callable[[T], str] | None = None,
    ) -> T:
        try:
            value = handler()
        except Exception as exc:
            self.record(name, arguments, f"调用失败：{exc.__class__.__name__}", status="failed")
            raise
        result = result_formatter(value) if result_formatter is not None else "completed"
        self.record(name, arguments, result)
        return value

    def record(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        result: str = "completed",
        status: str = "completed",
    ) -> AgentFunctionCallTrace:
        trace = self._registry.trace(name, arguments, result, status)
        self._calls.append(trace)
        return trace


agent_tool_registry = AgentToolRegistry()
