from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Literal
from unittest.mock import patch
from uuid import UUID, uuid4

from app.schemas.chat import ChatActionType, ChatMessageRequest
from app.schemas.quality import (
    AgentQualityAdmission,
    AgentQualityEvaluationCase,
    AgentQualityEvaluationRun,
    AgentQualityFeedbackCreate,
    AgentQualityFeedbackRead,
    AgentQualitySummary,
)
from app.services.bill_candidate_store import bill_candidate_store
from app.services.chat_service import chat_service
from app.services.diary_candidate_store import diary_candidate_store
from app.services.external_ai_parser import external_ai_parser
from app.services.rag_retriever import hybrid_rag_retriever
from app.services.sqlite_state_store import sqlite_state_store
from app.services.task_candidate_store import task_candidate_store


class AgentQualityService:
    _dataset_path = Path(__file__).resolve().parents[2] / "evaluations" / "agent_admission_v1.json"

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
            acceptance_rate=round(counts["accepted"] / feedback_count, 4)
            if feedback_count
            else None,
            correction_rate=round(
                (counts["corrected"] + counts["rejected"]) / feedback_count,
                4,
            )
            if feedback_count
            else None,
            latest_evaluation=AgentQualityEvaluationRun.model_validate(latest)
            if latest
            else None,
        )

    def run_evaluation(
        self,
        *,
        execution_mode: Literal["offline", "live"] = "offline",
    ) -> AgentQualityEvaluationRun:
        suite = self._load_suite()
        results: list[AgentQualityEvaluationCase] = []
        strategy = "unknown"

        with self._provider_mode(execution_mode):
            for fixture in suite["cases"]:
                response = chat_service.handle_message(
                    ChatMessageRequest(message=fixture["message"])
                )
                strategy = (
                    response.model_trace.strategy
                    if response.model_trace
                    else strategy
                )
                actual_category = self._candidate_category(
                    response.action_type,
                    response.candidate,
                )
                tool_names = {call.name for call in response.function_calls}
                missing_tools = sorted(set(fixture["tools"]) - tool_names)
                expected_confirmation = fixture.get("need_user_confirmation")
                passed = (
                    response.intent.value == fixture["intent"]
                    and (
                        fixture.get("category") is None
                        or actual_category == fixture["category"]
                    )
                    and not missing_tools
                    and (
                        expected_confirmation is None
                        or response.need_user_confirmation == expected_confirmation
                    )
                )
                results.append(
                    AgentQualityEvaluationCase(
                        case_id=fixture["case_id"],
                        passed=passed,
                        expected_intent=fixture["intent"],
                        actual_intent=response.intent.value,
                        expected_category=fixture.get("category"),
                        actual_category=actual_category,
                        missing_function_tools=missing_tools,
                        critical=bool(fixture.get("critical", False)),
                        expected_confirmation=expected_confirmation,
                        actual_confirmation=response.need_user_confirmation,
                    )
                )
                self._discard_candidate(
                    response.action_type,
                    response.candidate_id,
                )

        passed_cases = sum(1 for item in results if item.passed)
        pass_rate = round(passed_cases / len(results), 4) if results else 0.0
        admission = self._admission(suite, results, pass_rate)
        run = AgentQualityEvaluationRun(
            run_id=uuid4(),
            created_at=datetime.now(timezone.utc),
            total_cases=len(results),
            passed_cases=passed_cases,
            pass_rate=pass_rate,
            model_strategy=(
                "offline_rule_based_admission"
                if execution_mode == "offline"
                else strategy
            ),
            cases=results,
            dataset_id=suite["dataset_id"],
            dataset_version=suite["dataset_version"],
            execution_mode=execution_mode,
            admission=admission,
        )
        sqlite_state_store.append_agent_quality_evaluation(run.model_dump(mode="json"))
        return run

    def _load_suite(self) -> dict:
        payload = json.loads(self._dataset_path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Agent admission dataset must be an object")
        cases = payload.get("cases")
        if not isinstance(cases, list) or not cases:
            raise ValueError("Agent admission dataset must include cases")

        normalized_cases: list[dict] = []
        ids: set[str] = set()
        for item in cases:
            if not isinstance(item, dict):
                raise ValueError("Agent admission case must be an object")
            case_id = str(item.get("case_id") or "").strip()
            message = str(item.get("message") or "").strip()
            intent = str(item.get("intent") or "").strip()
            tools = item.get("tools", [])
            if (
                not case_id
                or not message
                or not intent
                or not isinstance(tools, list)
                or case_id in ids
            ):
                raise ValueError("Agent admission dataset has an invalid case")
            ids.add(case_id)
            normalized_cases.append(
                {
                    "case_id": case_id,
                    "message": message,
                    "intent": intent,
                    "category": (
                        str(item["category"]).strip()
                        if item.get("category") is not None
                        else None
                    ),
                    "tools": [str(tool) for tool in tools if str(tool).strip()],
                    "critical": bool(item.get("critical", False)),
                    "need_user_confirmation": item.get("need_user_confirmation"),
                }
            )

        minimum_pass_rate = float(payload.get("minimum_pass_rate", 1.0))
        if not 0 <= minimum_pass_rate <= 1:
            raise ValueError("Agent admission minimum_pass_rate must be between 0 and 1")
        return {
            "dataset_id": str(payload.get("dataset_id") or "agent-admission"),
            "dataset_version": str(payload.get("dataset_version") or "v1"),
            "policy_id": str(payload.get("policy_id") or "agent-admission-v1"),
            "minimum_pass_rate": minimum_pass_rate,
            "cases": normalized_cases,
        }

    def _admission(
        self,
        suite: dict,
        cases: list[AgentQualityEvaluationCase],
        pass_rate: float,
    ) -> AgentQualityAdmission:
        failed_critical = [
            case.case_id
            for case in cases
            if case.critical and not case.passed
        ]
        reasons: list[str] = []
        if pass_rate < suite["minimum_pass_rate"]:
            reasons.append(
                "pass_rate_below_threshold:"
                f"{pass_rate:.4f}<{suite['minimum_pass_rate']:.4f}"
            )
        if failed_critical:
            reasons.append(
                "critical_cases_failed:" + ",".join(failed_critical)
            )
        return AgentQualityAdmission(
            policy_id=suite["policy_id"],
            dataset_version=suite["dataset_version"],
            minimum_pass_rate=suite["minimum_pass_rate"],
            admitted=not reasons,
            critical_case_count=sum(1 for case in cases if case.critical),
            failed_critical_case_ids=failed_critical,
            failure_reasons=reasons,
        )

    @contextmanager
    def _provider_mode(
        self,
        execution_mode: Literal["offline", "live"],
    ) -> Iterator[None]:
        if execution_mode == "live":
            yield
            return

        bypass = (None, ["evaluation_external_model_bypassed"])
        with (
            patch.object(external_ai_parser, "route_chat", return_value=bypass),
            patch.object(external_ai_parser, "parse_bill", return_value=bypass),
            patch.object(external_ai_parser, "parse_task", return_value=bypass),
            patch.object(hybrid_rag_retriever, "semantic_available", return_value=False),
        ):
            yield

    def _candidate_category(
        self,
        action_type: ChatActionType,
        candidate: object,
    ) -> str | None:
        if action_type != ChatActionType.bill_candidate or candidate is None:
            return None
        data = getattr(candidate, "data", None)
        return str(getattr(data, "category", "")) or None

    def _discard_candidate(
        self,
        action_type: ChatActionType,
        candidate_id: UUID | None,
    ) -> None:
        if candidate_id is None:
            return
        if action_type == ChatActionType.bill_candidate:
            bill_candidate_store.delete(candidate_id)
        elif action_type == ChatActionType.task_candidate:
            task_candidate_store.delete(candidate_id)
        elif action_type == ChatActionType.diary_candidate:
            diary_candidate_store.delete(candidate_id)


agent_quality_service = AgentQualityService()
