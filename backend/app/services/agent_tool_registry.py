from __future__ import annotations

from typing import Any

from app.schemas.agent_runtime import AgentFunctionCallTrace, AgentFunctionToolCapability


class AgentToolRegistry:
    _tools = (
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

    def trace(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
        result: str = "completed",
        status: str = "completed",
    ) -> AgentFunctionCallTrace:
        tool = self.get(name)
        return AgentFunctionCallTrace(
            name=name,
            label=tool.label if tool is not None else name,
            arguments=arguments or {},
            result=result,
            status=status,
        )


agent_tool_registry = AgentToolRegistry()
