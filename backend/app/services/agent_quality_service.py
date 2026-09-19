from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.schemas.chat import ChatActionType, ChatMessageRequest
from app.schemas.quality import (
    AgentQualityEvaluationCase,
    AgentQualityEvaluationRun,
    AgentQualityFeedbackCreate,
    AgentQualityFeedbackRead,
    AgentQualitySummary,
)
from app.services.bill_candidate_store import bill_candidate_store
from app.services.chat_service import chat_service
from app.services.diary_candidate_store import diary_candidate_store
from app.services.sqlite_state_store import sqlite_state_store
from app.services.task_candidate_store import task_candidate_store


class AgentQualityService:
    _evaluation_cases = (
        {
            "case_id": "bill_dining_category",
            "message": "星巴克咖啡花了 38 元",
            "intent": "create_bill",
            "category": "餐饮",
            "tools": {"route_chat_intent", "parse_bill_candidate", "classify_bill_category"},
        },
        {
            "case_id": "task_reminder",
            "message": "提醒我明天提交周报",
            "intent": "create_task",
            "category": None,
            "tools": {"route_chat_intent", "parse_task_candidate"},
        },
        {
            "case_id": "diary_entry",
            "message": "写日记：今天完成项目复盘，心情很开心",
            "intent": "create_diary",
            "category": None,
            "tools": {"route_chat_intent", "parse_diary_candidate"},
        },
        {
            "case_id": "bill_analysis",
            "message": "这个月消费趋势和预算情况怎么样？",
            "intent": "analyze_bills",
            "category": None,
            "tools": {"analyze_bills"},
        },
    )

    def record_feedback(self, payload: AgentQualityFeedbackCreate) -> AgentQualityFeedbackRead:
        record = AgentQualityFeedbackRead(
            feedback_id=uuid4(),
            created_at=datetime.now(timezone.utc),
            **payload.model_dump(),
        )
        sqlite_state_store.append_agent_quality_feedback(record.model_dump(mode="json"))
        return record

    def summary(self) -> AgentQualitySummary:
        feedback = sqlite_state_store.list_agent_quality_feedback(limit=500)
        counts = {"accepted": 0, "corrected": 0, "rejected": 0}
        for item in feedback:
            verdict = str(item["verdict"])
            if verdict in counts:
                counts[verdict] += 1
        feedback_count = len(feedback)
        latest = sqlite_state_store.latest_agent_quality_evaluation()
        return AgentQualitySummary(
            generated_at=datetime.now(timezone.utc),
            feedback_count=feedback_count,
            accepted_count=counts["accepted"],
            corrected_count=counts["corrected"],
            rejected_count=counts["rejected"],
            acceptance_rate=round(counts["accepted"] / feedback_count, 4) if feedback_count else None,
            correction_rate=round((counts["corrected"] + counts["rejected"]) / feedback_count, 4) if feedback_count else None,
            latest_evaluation=AgentQualityEvaluationRun.model_validate(latest) if latest else None,
        )

    def run_evaluation(self) -> AgentQualityEvaluationRun:
        results: list[AgentQualityEvaluationCase] = []
        strategy = "unknown"
        for fixture in self._evaluation_cases:
            response = chat_service.handle_message(ChatMessageRequest(message=fixture["message"]))
            strategy = response.model_trace.strategy if response.model_trace else strategy
            actual_category = self._candidate_category(response.action_type, response.candidate)
            tool_names = {call.name for call in response.function_calls}
            missing_tools = sorted(fixture["tools"] - tool_names)
            passed = (
                response.intent.value == fixture["intent"]
                and (fixture["category"] is None or actual_category == fixture["category"])
                and not missing_tools
            )
            results.append(
                AgentQualityEvaluationCase(
                    case_id=fixture["case_id"],
                    passed=passed,
                    expected_intent=fixture["intent"],
                    actual_intent=response.intent.value,
                    expected_category=fixture["category"],
                    actual_category=actual_category,
                    missing_function_tools=missing_tools,
                )
            )
            self._discard_candidate(response.action_type, response.candidate_id)

        passed_cases = sum(1 for item in results if item.passed)
        run = AgentQualityEvaluationRun(
            run_id=uuid4(),
            created_at=datetime.now(timezone.utc),
            total_cases=len(results),
            passed_cases=passed_cases,
            pass_rate=round(passed_cases / len(results), 4) if results else 0.0,
            model_strategy=strategy,
            cases=results,
        )
        sqlite_state_store.append_agent_quality_evaluation(run.model_dump(mode="json"))
        return run

    def _candidate_category(self, action_type: ChatActionType, candidate: object) -> str | None:
        if action_type != ChatActionType.bill_candidate or candidate is None:
            return None
        data = getattr(candidate, "data", None)
        return str(getattr(data, "category", "")) or None

    def _discard_candidate(self, action_type: ChatActionType, candidate_id: UUID | None) -> None:
        if candidate_id is None:
            return
        if action_type == ChatActionType.bill_candidate:
            bill_candidate_store.delete(candidate_id)
        elif action_type == ChatActionType.task_candidate:
            task_candidate_store.delete(candidate_id)
        elif action_type == ChatActionType.diary_candidate:
            diary_candidate_store.delete(candidate_id)


agent_quality_service = AgentQualityService()
