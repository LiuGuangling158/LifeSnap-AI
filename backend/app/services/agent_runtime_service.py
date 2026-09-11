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
from app.services.settings_store import settings_store
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
        base_model = self._model_summary()
        runtime_model = self._model_summary(runtime=True)
        llm_configured = self._llm_configured()
        external_parser_configured = bool(settings.external_ai_parser_endpoint)
        external_model_configured = llm_configured or external_parser_configured
        privacy_blockers = self._privacy_blockers() if external_model_configured else []
        llm_credential_blockers = self._credential_blockers()
        llm_ready = self._llm_ready() and not privacy_blockers and not llm_credential_blockers
        external_parser_ready = external_parser_configured and not privacy_blockers
        active_external_ready = llm_ready or external_parser_ready
        credential_blockers = [] if external_parser_ready else llm_credential_blockers
        visible_runtime_model = runtime_model if llm_ready or (llm_configured and not external_parser_ready) else None
        visible_reasoning_effort = self._reasoning_effort() if visible_runtime_model else None

        if fine_tuned_model and llm_ready:
            strategy = "fine_tuned_llm_with_local_fallback"
            fine_tuning_status = "serving_fine_tuned_model"
        elif llm_ready:
            strategy = "base_llm_with_rag_and_function_calling"
            fine_tuning_status = "training_dataset_ready"
        elif external_parser_ready:
            strategy = "external_parser_with_local_fallback"
            fine_tuning_status = "training_dataset_ready"
        elif llm_configured and privacy_blockers:
            strategy = "llm_configured_blocked_by_privacy"
            fine_tuning_status = "training_dataset_ready"
        elif external_parser_configured and privacy_blockers:
            strategy = "external_parser_blocked_by_privacy"
            fine_tuning_status = "training_dataset_ready"
        elif llm_configured:
            strategy = "llm_configured_not_ready"
            fine_tuning_status = "training_dataset_ready"
        else:
            strategy = "rule_based_local_fallback"
            fine_tuning_status = "training_dataset_ready"

        provider = (
            self._provider_summary()
            if llm_ready or (llm_configured and not external_parser_ready)
            else settings.ai_parser_provider_name
        )

        return AgentModelTrace(
            provider=provider,
            strategy=strategy,
            runtime_model=visible_runtime_model,
            base_model=base_model,
            fine_tuned_model=fine_tuned_model,
            fine_tuning_status=fine_tuning_status,
            response_format=settings.llm_agent_response_format,
            reasoning_effort=visible_reasoning_effort,
            external_model_configured=external_model_configured,
            external_model_ready=active_external_ready,
            local_fallback_active=not active_external_ready,
            endpoint_configured=bool(
                settings.llm_agent_base_url_for_kind("chat_intent")
                or settings.llm_agent_base_url_for_kind("bill")
                or settings.external_ai_parser_endpoint
            ),
            api_key_configured=bool(settings.llm_agent_api_key_configured or settings.external_ai_parser_api_key),
            privacy_blockers=privacy_blockers,
            credential_blockers=credential_blockers,
            next_action=self._next_action(
                external_model_configured,
                privacy_blockers,
                credential_blockers,
                active_external_ready,
            ),
            function_calling_mode=self._function_calling_mode(llm_ready),
            rag_enabled=True,
            function_calling_enabled=True,
        )

    def _privacy_blockers(self) -> list[str]:
        privacy_settings = settings_store.get_privacy_settings()
        blockers: list[str] = []
        if privacy_settings.local_only_mode:
            blockers.append("local_only_mode_enabled")
        if not privacy_settings.allow_ai_text_processing:
            blockers.append("ai_text_processing_disabled")
        return blockers

    def _credential_blockers(self) -> list[str]:
        blockers: list[str] = []
        for kind in ("chat_intent", "bill"):
            if not settings.llm_agent_configured_for_kind(kind) or not settings.llm_agent_api_key_required_for_kind(kind):
                continue
            if settings.llm_agent_api_key_for_kind(kind):
                continue
            if settings.deepseek_llm_agent_enabled_for_kind(kind):
                blockers.append("deepseek_api_key_missing")
            elif settings.siliconflow_llm_agent_enabled_for_kind(kind):
                blockers.append("siliconflow_api_key_missing")
            else:
                blockers.append("llm_api_key_missing")
        return self._dedupe(blockers)

    def _reasoning_effort(self) -> str | None:
        if not settings.deepseek_llm_agent_enabled_for_kind("chat_intent"):
            return settings.llm_agent_reasoning_effort
        return settings.llm_agent_reasoning_effort or "none"

    def _function_calling_mode(self, llm_ready: bool) -> str:
        if llm_ready and settings.deepseek_llm_agent_enabled_for_kind("chat_intent") and settings.siliconflow_llm_agent_enabled_for_kind("bill"):
            return "mixed_deepseek_siliconflow_tool_calls_with_local_execution"
        if llm_ready and settings.deepseek_llm_agent_enabled:
            return "deepseek_native_tool_calls_with_local_execution"
        if llm_ready:
            return "native_tool_calls_with_local_execution"
        return "local_trace_only"

    def _next_action(
        self,
        external_model_configured: bool,
        privacy_blockers: list[str],
        credential_blockers: list[str],
        external_model_ready: bool,
    ) -> str | None:
        if external_model_ready:
            return None
        if credential_blockers:
            if "siliconflow_api_key_missing" in credential_blockers:
                return "配置 LIFESNAP_DEFAULT_AI_API_KEY 或 SILICONFLOW_API_KEY 后启用硅基流动默认解析。"
            return "配置 LIFESNAP_DEEPSEEK_CHAT_API_KEY、DEEPSEEK_API_KEY 或 LIFESNAP_LLM_API_KEY 后启用 DeepSeek。"
        if privacy_blockers:
            return "关闭本地-only 模式并允许 AI 文本处理后，外部大模型才会参与解析。"
        if external_model_configured:
            return "检查大模型 base URL、模型名和 API key 配置。"
        return "配置 LIFESNAP_DEEPSEEK_CHAT_API_KEY 或 DEEPSEEK_API_KEY 后，可启用 DeepSeek 大模型解析。"

    def _llm_configured(self) -> bool:
        return any(settings.llm_agent_configured_for_kind(kind) for kind in ("chat_intent", "bill"))

    def _llm_ready(self) -> bool:
        return any(settings.real_llm_agent_enabled_for_kind(kind) for kind in ("chat_intent", "bill"))

    def _provider_summary(self) -> str:
        providers = [
            settings.llm_agent_provider_for_kind("chat_intent"),
            settings.llm_agent_provider_for_kind("bill"),
        ]
        return "+".join(self._dedupe(providers))

    def _model_summary(self, *, runtime: bool = False) -> str | None:
        chat_model = settings.llm_agent_runtime_model_for_kind("chat_intent") if runtime else settings.llm_agent_model
        default_model = settings.llm_agent_runtime_model_for_kind("bill") if runtime else settings.llm_agent_default_model
        if chat_model == default_model:
            return chat_model
        parts = []
        if chat_model:
            parts.append(f"chat:{chat_model}")
        if default_model:
            parts.append(f"default:{default_model}")
        return " | ".join(parts) or None

    def _dedupe(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        for value in values:
            if value and value not in deduped:
                deduped.append(value)
        return deduped

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
