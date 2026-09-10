from __future__ import annotations

import json
from datetime import datetime, timezone

from app.core.config import settings
from app.schemas.agent_runtime import (
    AgentFineTuningDatasetResponse,
    AgentFineTuningExample,
    AgentModelTrace,
    AgentRuntimeProfile,
)
from app.services.agent_knowledge_base import agent_knowledge_base
from app.services.agent_tool_registry import agent_tool_registry
from app.services.bill_store import bill_store
from app.services.diary_store import diary_store
from app.services.task_store import task_store


class AgentRuntimeService:
    def profile(self) -> AgentRuntimeProfile:
        return AgentRuntimeProfile(
            rag_enabled=True,
            function_calling_enabled=True,
            fine_tuning_ready=True,
            knowledge_sources=agent_knowledge_base.sources(),
            function_tools=agent_tool_registry.all(),
            model_profile=self.model_trace(),
        )

    def model_trace(self) -> AgentModelTrace:
        fine_tuned_model = settings.llm_agent_fine_tuned_model
        base_model = settings.llm_agent_model
        runtime_model = settings.llm_agent_runtime_model
        if fine_tuned_model and settings.real_llm_agent_enabled:
            strategy = "fine_tuned_llm_with_local_fallback"
            fine_tuning_status = "serving_fine_tuned_model"
        elif settings.real_llm_agent_enabled:
            strategy = "base_llm_with_rag_and_function_calling"
            fine_tuning_status = "training_dataset_ready"
        elif settings.llm_agent_configured:
            strategy = "llm_configured_not_ready"
            fine_tuning_status = "training_dataset_ready"
        elif settings.external_ai_parser_endpoint:
            strategy = "external_parser_with_local_fallback"
            fine_tuning_status = "training_dataset_ready"
        else:
            strategy = "rule_based_local_fallback"
            fine_tuning_status = "training_dataset_ready"

        provider = (
            settings.llm_agent_provider
            if settings.llm_agent_configured
            else settings.ai_parser_provider_name
        )

        return AgentModelTrace(
            provider=provider,
            strategy=strategy,
            runtime_model=runtime_model,
            base_model=base_model,
            fine_tuned_model=fine_tuned_model,
            fine_tuning_status=fine_tuning_status,
            response_format=settings.llm_agent_response_format,
            rag_enabled=True,
            function_calling_enabled=True,
        )

    def fine_tuning_dataset(self, limit: int = 50) -> AgentFineTuningDatasetResponse:
        examples: list[AgentFineTuningExample] = []
        for bill in bill_store.all()[:limit]:
            examples.append(
                AgentFineTuningExample(
                    purpose="bill_candidate_extraction",
                    messages=[
                        {"role": "system", "content": "Extract a LifeSnap bill candidate as strict JSON."},
                        {"role": "user", "content": self._bill_training_prompt(bill)},
                        {
                            "role": "assistant",
                            "content": self._json_content(
                                {"intent": "create_bill", "data": self._bill_target_data(bill)}
                            ),
                        },
                    ],
                )
            )
            if len(examples) >= limit:
                break

        if len(examples) < limit:
            for task in task_store.all()[: limit - len(examples)]:
                examples.append(
                    AgentFineTuningExample(
                        purpose="task_candidate_extraction",
                        messages=[
                            {"role": "system", "content": "Extract a LifeSnap task candidate as strict JSON."},
                            {"role": "user", "content": self._task_training_prompt(task)},
                            {
                                "role": "assistant",
                                "content": self._json_content(
                                    {"intent": "create_task", "data": self._task_target_data(task)}
                                ),
                            },
                        ],
                    )
                )
                if len(examples) >= limit:
                    break

        if len(examples) < limit:
            for diary in diary_store.all()[: limit - len(examples)]:
                examples.append(
                    AgentFineTuningExample(
                        purpose="diary_candidate_extraction",
                        messages=[
                            {"role": "system", "content": "Extract a LifeSnap diary candidate as strict JSON."},
                            {"role": "user", "content": diary.content[:500]},
                            {"role": "assistant", "content": self._json_content({"intent": "create_diary", "data": self._diary_target_data(diary)})},
                        ],
                    )
                )
                if len(examples) >= limit:
                    break

        return AgentFineTuningDatasetResponse(
            generated_at=datetime.now(timezone.utc),
            total=len(examples),
            examples=examples,
        )

    def _bill_training_prompt(self, bill) -> str:
        parts = [str(bill.amount), bill.category, bill.merchant, bill.payment_method, bill.note]
        text = " ".join(str(part) for part in parts if part)
        return text or f"{bill.transaction_type.value} {bill.amount}"

    def _bill_target_data(self, bill) -> dict:
        return {
            "amount": str(bill.amount),
            "currency": bill.currency,
            "merchant": bill.merchant,
            "category": bill.category,
            "payment_method": bill.payment_method,
            "paid_at": bill.paid_at.isoformat() if bill.paid_at else None,
            "transaction_type": self._enum_value(bill.transaction_type),
            "note": bill.note,
            "source": self._enum_value(bill.source),
        }

    def _task_training_prompt(self, task) -> str:
        parts = [task.title, task.description, task.category, self._enum_value(task.priority)]
        return " ".join(str(part) for part in parts if part)

    def _task_target_data(self, task) -> dict:
        return {
            "title": task.title,
            "description": task.description,
            "category": task.category,
            "task_type": self._enum_value(task.task_type),
            "due_at": task.due_at.isoformat() if task.due_at else None,
            "remind_at": task.remind_at.isoformat() if task.remind_at else None,
            "priority": self._enum_value(task.priority),
            "source": self._enum_value(task.source),
        }

    def _diary_target_data(self, diary) -> dict:
        return {
            "entry_date": diary.entry_date.isoformat() if diary.entry_date else None,
            "title": diary.title,
            "content": diary.content,
            "mood": self._enum_value(diary.mood),
            "weather": diary.weather,
            "source": self._enum_value(diary.source),
            "tags": diary.tags,
        }

    def _enum_value(self, value):
        return value.value if hasattr(value, "value") else value

    def _json_content(self, payload: dict) -> str:
        return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


agent_runtime_service = AgentRuntimeService()
