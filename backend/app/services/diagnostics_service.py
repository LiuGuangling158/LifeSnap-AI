from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from uuid import UUID

from app.core.config import settings
from app.schemas.agent import (
    ParseBillRequest,
    ParseBillResponse,
    ParseTaskRequest,
    ParseTaskResponse,
    ParseDiaryResponse,
)
from app.schemas.attachment import AttachmentRead
from app.schemas.bill import BillRead, BillSource
from app.schemas.diagnostics import (
    DataQualityDiagnostics,
    DiagnosticIssue,
    DiagnosticSeverity,
    IntegrationCheck,
    IntegrationDiagnostics,
    IntegrationProbeResponse,
    IntegrationProbeResult,
    ReadinessComponent,
    ReadinessDiagnostics,
)
from app.services.agent_knowledge_base import agent_knowledge_base
from app.services.agent_runtime_service import agent_runtime_service
from app.schemas.task import TaskRead, TaskSource, TaskStatus, TaskType
from app.services.attachment_store import attachment_store
from app.services.audit_log_store import audit_log_store
from app.services.bill_candidate_store import bill_candidate_store
from app.services.bill_store import bill_store
from app.services.data_management_service import data_management_service
from app.services.diary_candidate_store import diary_candidate_store
from app.services.external_ai_parser import external_ai_parser
from app.services.ocr_service import ocr_service
from app.services.settings_store import settings_store
from app.services.task_candidate_store import task_candidate_store
from app.services.task_store import task_store


class DiagnosticsService:
    def readiness(self) -> ReadinessDiagnostics:
        now = datetime.now(timezone.utc)
        integrations = self.integrations()
        data_quality = self.data_quality(issue_limit=20)
        components = [
            self._storage_readiness(),
            self._agent_readiness(),
            self._integration_readiness(integrations),
            self._privacy_readiness(),
            self._audit_readiness(),
            self._data_quality_readiness(data_quality),
        ]
        ready_count = len([component for component in components if component.status == "ready"])
        degraded_count = len([component for component in components if component.status == "degraded"])
        action_required_count = len([component for component in components if component.status == "action_required"])
        return ReadinessDiagnostics(
            generated_at=now,
            status=self._readiness_status(components),
            component_count=len(components),
            ready_count=ready_count,
            degraded_count=degraded_count,
            action_required_count=action_required_count,
            components=components,
        )

    def integrations(self) -> IntegrationDiagnostics:
        now = datetime.now(timezone.utc)
        checks = [
            self._ocr_integration_check(),
            self._ai_parser_integration_check(),
            self._chat_intent_integration_check(),
        ]
        blocked_count = len([check for check in checks if check.status == "blocked"])
        fallback_count = len([check for check in checks if check.status == "fallback"])
        ready_count = len([check for check in checks if check.ready])
        return IntegrationDiagnostics(
            generated_at=now,
            status=self._integration_status(blocked_count, fallback_count),
            check_count=len(checks),
            ready_count=ready_count,
            blocked_count=blocked_count,
            fallback_count=fallback_count,
            checks=checks,
        )

    def probe_integrations(self) -> IntegrationProbeResponse:
        now = datetime.now(timezone.utc)
        results = [
            self._probe_ocr(),
            self._probe_ai_bill_parser(),
            self._probe_ai_task_parser(),
            self._probe_chat_intent(),
        ]
        success_count = len([result for result in results if result.status == "success"])
        failed_count = len([result for result in results if result.status == "failed"])
        skipped_count = len([result for result in results if result.status == "skipped"])
        return IntegrationProbeResponse(
            generated_at=now,
            status=self._probe_status(success_count, failed_count),
            probe_count=len(results),
            success_count=success_count,
            failed_count=failed_count,
            skipped_count=skipped_count,
            results=results,
        )

    def data_quality(
        self,
        *,
        duplicate_time_window_minutes: int = 10,
        issue_limit: int = 50,
    ) -> DataQualityDiagnostics:
        now = datetime.now(timezone.utc)
        issues: list[DiagnosticIssue] = []
        issues.extend(self._privacy_issues())
        issues.extend(self._attachment_issues())
        issues.extend(self._candidate_issues())
        issues.extend(self._duplicate_bill_issues(duplicate_time_window_minutes))
        issues.extend(self._task_issues(now))
        issues.extend(self._recycle_bin_issues())

        sorted_issues = sorted(issues, key=self._issue_sort_key)
        limited_issues = sorted_issues[:issue_limit]
        info_count = self._severity_count(issues, DiagnosticSeverity.info)
        warning_count = self._severity_count(issues, DiagnosticSeverity.warning)
        action_required_count = self._severity_count(
            issues,
            DiagnosticSeverity.action_required,
        )
        return DataQualityDiagnostics(
            generated_at=now,
            status=self._status(warning_count, action_required_count),
            data_summary=data_management_service.summary(),
            issue_count=len(issues),
            info_count=info_count,
            warning_count=warning_count,
            action_required_count=action_required_count,
            issue_limit=issue_limit,
            truncated=len(issues) > issue_limit,
            issues=limited_issues,
        )

    def _storage_readiness(self) -> ReadinessComponent:
        data_dir = settings.local_bill_path.parent
        managed_paths = [
            settings.local_bill_path,
            settings.local_task_path,
            settings.local_diary_path,
            settings.local_attachment_path,
            settings.local_audit_path,
            settings.local_idempotency_path,
            settings.local_agent_knowledge_path,
        ]
        existing_files = sum(1 for path in managed_paths if path.exists())
        writable = self._path_writable(data_dir)
        summary = data_management_service.summary()
        candidate_count = summary.bill_candidate_count + summary.task_candidate_count + summary.diary_candidate_count
        warnings: list[str] = []
        next_action: str | None = None
        status = "ready"
        if not writable:
            status = "action_required"
            warnings.append("data_directory_not_writable")
            next_action = "Check LIFESNAP_DATA_DIR permissions before running writes or imports."
        elif candidate_count:
            status = "degraded"
            warnings.append("pending_candidates_present")
            next_action = "Review and confirm or discard pending AI candidates."

        return ReadinessComponent(
            name="storage",
            title="Local storage",
            status=status,
            summary="Local JSON persistence is reachable." if writable else "Local JSON persistence cannot be written.",
            metrics={
                "backend": "local_json",
                "data_dir": str(data_dir),
                "managed_file_count": len(managed_paths),
                "existing_file_count": existing_files,
                "bill_count": summary.bill_count,
                "task_count": summary.task_count,
                "diary_count": summary.diary_count,
                "attachment_count": summary.attachment_count,
                "pending_candidate_count": candidate_count,
            },
            warnings=warnings,
            next_action=next_action,
        )

    def _agent_readiness(self) -> ReadinessComponent:
        runtime = agent_runtime_service.profile()
        model = runtime.model_profile
        knowledge_count = sum(source.document_count for source in runtime.knowledge_sources)
        versions = agent_knowledge_base.response().versions
        warnings: list[str] = []
        next_action: str | None = None
        status = "ready"
        if not runtime.rag_enabled or knowledge_count == 0:
            status = "action_required"
            warnings.append("rag_knowledge_missing")
            next_action = "Restore built-in knowledge or add admin knowledge before using the Agent."
        elif model.local_fallback_active:
            status = "degraded"
            warnings.append("external_model_not_ready")
            next_action = model.next_action or "Configure a ready external model or keep using local fallback."

        return ReadinessComponent(
            name="agent",
            title="AI Agent runtime",
            status=status,
            summary=f"Agent strategy: {model.strategy}.",
            metrics={
                "rag_enabled": runtime.rag_enabled,
                "function_calling_enabled": runtime.function_calling_enabled,
                "fine_tuning_ready": runtime.fine_tuning_ready,
                "knowledge_document_count": knowledge_count,
                "knowledge_version_count": len(versions),
                "function_tool_count": len(runtime.function_tools),
                "model_provider": model.provider,
                "model_strategy": model.strategy,
                "external_model_ready": model.external_model_ready,
                "local_fallback_active": model.local_fallback_active,
            },
            warnings=warnings,
            next_action=next_action,
        )

    def _integration_readiness(self, integrations: IntegrationDiagnostics) -> ReadinessComponent:
        status = "ready"
        warnings: list[str] = []
        next_action: str | None = None
        if integrations.blocked_count:
            status = "action_required"
            warnings.append("configured_integrations_blocked")
        elif integrations.fallback_count:
            status = "degraded"
            warnings.append("some_integrations_using_fallback")

        for check in integrations.checks:
            if check.next_action:
                next_action = check.next_action
                break

        return ReadinessComponent(
            name="integrations",
            title="AI/OCR integrations",
            status=status,
            summary=f"{integrations.ready_count} of {integrations.check_count} integrations are ready.",
            metrics={
                "check_count": integrations.check_count,
                "ready_count": integrations.ready_count,
                "fallback_count": integrations.fallback_count,
                "blocked_count": integrations.blocked_count,
            },
            warnings=warnings,
            next_action=next_action,
        )

    def _privacy_readiness(self) -> ReadinessComponent:
        privacy = settings_store.get_privacy_settings()
        external_model_configured = agent_runtime_service.model_trace().external_model_configured or settings.real_ocr_enabled
        warnings: list[str] = []
        next_action: str | None = None
        status = "ready"
        if external_model_configured and privacy.local_only_mode:
            status = "degraded"
            warnings.append("external_ai_blocked_by_local_only_mode")
            next_action = "Disable local-only mode only when the user explicitly allows external AI processing."
        if privacy.save_original_attachments_by_default:
            warnings.append("original_attachment_retention_enabled")
            if status == "ready":
                status = "degraded"
            next_action = next_action or "Disable original attachment retention unless product policy requires it."

        return ReadinessComponent(
            name="privacy",
            title="Privacy controls",
            status=status,
            summary="Privacy switches are loaded and enforce external AI boundaries.",
            metrics={
                "local_only_mode": privacy.local_only_mode,
                "allow_ai_text_processing": privacy.allow_ai_text_processing,
                "save_original_attachments_by_default": privacy.save_original_attachments_by_default,
                "keep_ocr_text": privacy.keep_ocr_text,
                "attachment_retention_policy": privacy.attachment_retention_policy,
            },
            warnings=warnings,
            next_action=next_action,
        )

    def _audit_readiness(self) -> ReadinessComponent:
        path = settings.local_audit_path
        writable = self._path_writable(path.parent)
        event_count = audit_log_store.list(page_size=1).total
        status = "ready" if writable else "action_required"
        warnings = [] if writable else ["audit_log_directory_not_writable"]
        return ReadinessComponent(
            name="audit",
            title="Audit log",
            status=status,
            summary="Audit events are persisted locally." if writable else "Audit events cannot be persisted.",
            metrics={
                "event_count": event_count,
                "path": str(path),
                "redaction_enabled": True,
            },
            warnings=warnings,
            next_action=None if writable else "Check audit log directory permissions.",
        )

    def _data_quality_readiness(self, diagnostics: DataQualityDiagnostics) -> ReadinessComponent:
        if diagnostics.action_required_count:
            status = "action_required"
        elif diagnostics.warning_count:
            status = "degraded"
        else:
            status = "ready"
        return ReadinessComponent(
            name="data_quality",
            title="Data quality",
            status=status,
            summary=f"{diagnostics.issue_count} data quality findings detected.",
            metrics={
                "issue_count": diagnostics.issue_count,
                "action_required_count": diagnostics.action_required_count,
                "warning_count": diagnostics.warning_count,
                "info_count": diagnostics.info_count,
            },
            warnings=[issue.code for issue in diagnostics.issues[:5]],
            next_action="Resolve action-required diagnostics first." if diagnostics.action_required_count else None,
        )

    def _ocr_integration_check(self) -> IntegrationCheck:
        configured = settings.real_ocr_enabled
        blockers = self._external_ai_privacy_blockers() + self._ocr_credential_blockers()
        warnings: list[str] = []
        next_action: str | None = None

        if not configured:
            warnings.append("ocr_engine_not_configured")
            next_action = "Set LIFESNAP_OCR_ENDPOINT to enable external OCR."
        elif "kimi_api_key_missing" in blockers:
            next_action = "Set LIFESNAP_IMAGE_BILL_API_KEY, LIFESNAP_KIMI_API_KEY, or MOONSHOT_API_KEY before using Kimi Vision OCR."
        elif blockers:
            next_action = "Disable local-only mode and allow AI text processing before using external OCR."
        if configured:
            warnings.append("original_attachment_required_for_external_ocr")

        capabilities = ["attachment_text_recognition", "stored_text_fallback"]
        if settings.kimi_vision_ocr_enabled:
            capabilities.extend(["kimi_vision_chat_completions", "image_bill_text_extraction"])

        return IntegrationCheck(
            name="ocr",
            provider=settings.ocr_provider_name,
            status=self._integration_check_status(configured, blockers),
            configured=configured,
            ready=configured and not blockers,
            endpoint_configured=bool(settings.external_ocr_endpoint),
            api_key_configured=bool(settings.external_ocr_api_key),
            timeout_seconds=settings.external_ocr_timeout_seconds,
            capabilities=capabilities,
            privacy_blockers=blockers,
            warnings=warnings,
            next_action=next_action,
        )

    def _ai_parser_integration_check(self) -> IntegrationCheck:
        configured = settings.real_ai_parser_enabled or settings.llm_agent_configured_for_kind("bill")
        blockers = self._external_ai_privacy_blockers() + self._llm_credential_blockers("bill")
        warnings: list[str] = []
        next_action: str | None = None

        if not configured:
            warnings.append("rule_based_parser_fallback")
            next_action = "Set LIFESNAP_DEEPSEEK_CHAT_API_KEY or DEEPSEEK_API_KEY to enable the built-in DeepSeek LLM agent, or set LIFESNAP_AI_PARSE_ENDPOINT for a custom parser."
        elif "deepseek_api_key_missing" in blockers:
            next_action = "Set LIFESNAP_DEEPSEEK_CHAT_API_KEY, DEEPSEEK_API_KEY, or LIFESNAP_LLM_API_KEY before using DeepSeek."
        elif "siliconflow_api_key_missing" in blockers:
            next_action = "Set LIFESNAP_DEFAULT_AI_API_KEY or SILICONFLOW_API_KEY before using SiliconFlow."
        elif blockers:
            next_action = "Disable local-only mode and allow AI text processing before using external AI parsing."

        capabilities = ["bill_candidate_parsing", "task_candidate_parsing"]
        if settings.llm_agent_configured_for_kind("bill"):
            capabilities.extend(["llm_agent_reasoning", "llm_json_output", "llm_function_calling"])
        if settings.deepseek_llm_agent_enabled_for_kind("bill"):
            capabilities.append("deepseek_chat_completions")
        if settings.siliconflow_llm_agent_enabled_for_kind("bill"):
            capabilities.append("siliconflow_chat_completions")

        return IntegrationCheck(
            name="ai_parser",
            provider=self._configured_ai_provider_name("bill"),
            status=self._integration_check_status(configured, blockers),
            configured=configured,
            ready=configured and not blockers,
            endpoint_configured=bool(settings.external_ai_parser_endpoint or settings.llm_agent_base_url_for_kind("bill")),
            api_key_configured=bool(settings.external_ai_parser_api_key or settings.llm_agent_api_key_configured),
            timeout_seconds=(
                settings.llm_agent_timeout_seconds
                if settings.real_llm_agent_enabled
                else settings.external_ai_parser_timeout_seconds
            ),
            capabilities=capabilities,
            privacy_blockers=blockers,
            warnings=warnings,
            next_action=next_action,
        )

    def _chat_intent_integration_check(self) -> IntegrationCheck:
        configured = settings.real_ai_parser_enabled or settings.llm_agent_configured_for_kind("chat_intent")
        blockers = self._external_ai_privacy_blockers() + self._llm_credential_blockers("chat_intent")
        warnings: list[str] = []
        next_action: str | None = None

        if not configured:
            warnings.append("keyword_router_fallback")
            next_action = "Set LIFESNAP_DEEPSEEK_CHAT_API_KEY or DEEPSEEK_API_KEY to enable DeepSeek chat routing, or set LIFESNAP_AI_PARSE_ENDPOINT for a custom parser."
        elif "deepseek_api_key_missing" in blockers:
            next_action = "Set LIFESNAP_DEEPSEEK_CHAT_API_KEY, DEEPSEEK_API_KEY, or LIFESNAP_LLM_API_KEY before using DeepSeek."
        elif "siliconflow_api_key_missing" in blockers:
            next_action = "Set LIFESNAP_DEFAULT_AI_API_KEY or SILICONFLOW_API_KEY before using SiliconFlow."
        elif blockers:
            next_action = "Disable local-only mode and allow AI text processing before using external chat intent routing."

        capabilities = ["chat_intent_routing", "chat_candidate_flow"]
        if settings.llm_agent_configured_for_kind("chat_intent"):
            capabilities.extend(["llm_agent_reasoning", "llm_json_output", "llm_function_calling"])
        if settings.deepseek_llm_agent_enabled_for_kind("chat_intent"):
            capabilities.append("deepseek_chat_completions")
        if settings.siliconflow_llm_agent_enabled_for_kind("chat_intent"):
            capabilities.append("siliconflow_chat_completions")

        return IntegrationCheck(
            name="chat_intent",
            provider=self._configured_ai_provider_name("chat_intent"),
            status=self._integration_check_status(configured, blockers),
            configured=configured,
            ready=configured and not blockers,
            endpoint_configured=bool(settings.external_ai_parser_endpoint or settings.llm_agent_base_url_for_kind("chat_intent")),
            api_key_configured=bool(settings.external_ai_parser_api_key or settings.llm_agent_api_key_configured),
            timeout_seconds=(
                settings.llm_agent_timeout_seconds
                if settings.real_llm_agent_enabled
                else settings.external_ai_parser_timeout_seconds
            ),
            capabilities=capabilities,
            privacy_blockers=blockers,
            warnings=warnings,
            next_action=next_action,
        )
    def _probe_ocr(self) -> IntegrationProbeResult:
        configured = settings.real_ocr_enabled
        blockers = self._external_ai_privacy_blockers()
        if not configured:
            return self._skipped_probe(
                name="ocr",
                provider=settings.ocr_provider_name,
                configured=False,
                warnings=["ocr_engine_not_configured"],
            )
        if blockers:
            return self._skipped_probe(
                name="ocr",
                provider=settings.ocr_provider_name,
                configured=True,
                warnings=["external_processing_blocked", *blockers],
                privacy_blockers=blockers,
            )

        started = time.perf_counter()
        try:
            response = ocr_service._call_external_ocr(
                attachment_id=UUID("00000000-0000-0000-0000-000000000001"),
                filename="lifesnap-probe-receipt.png",
                content_type="image/png",
                content=b"lifesnap-probe-receipt",
            )
            latency_ms = self._elapsed_ms(started)
        except (
            HTTPError,
            URLError,
            TimeoutError,
            OSError,
            ValueError,
            json.JSONDecodeError,
        ) as error:
            return self._failed_probe(
                name="ocr",
                provider=settings.ocr_provider_name,
                latency_ms=self._elapsed_ms(started),
                warnings=["external_ocr_failed"],
                error=type(error).__name__,
            )

        if not isinstance(response, dict):
            return self._failed_probe(
                name="ocr",
                provider=settings.ocr_provider_name,
                latency_ms=latency_ms,
                warnings=["external_ocr_invalid_response"],
                error="InvalidResponse",
            )

        warnings = self._warning_list(response.get("warnings"))
        if "text" not in response:
            return self._failed_probe(
                name="ocr",
                provider=settings.ocr_provider_name,
                latency_ms=latency_ms,
                warnings=[*warnings, "external_ocr_invalid_response"],
                error="MissingText",
            )

        text = str(response.get("text") or "").strip()
        if not text:
            warnings.append("external_ocr_empty_text")
        return self._successful_probe(
            name="ocr",
            provider=str(response.get("provider") or settings.ocr_provider_name),
            latency_ms=latency_ms,
            warnings=warnings,
            response_preview={
                "text_sample": self._preview_text(text),
                "text_length": len(text),
                "confidence": self._optional_float(response.get("confidence")),
            },
        )

    def _probe_ai_bill_parser(self) -> IntegrationProbeResult:
        configured = settings.real_ai_parser_enabled or settings.llm_agent_configured_for_kind("bill")
        blockers = self._external_ai_privacy_blockers() + self._llm_credential_blockers("bill")
        if not configured:
            return self._skipped_probe(
                name="ai_bill_parser",
                provider=self._configured_ai_provider_name("bill"),
                configured=False,
                warnings=["rule_based_parser_fallback"],
            )
        if blockers:
            return self._skipped_probe(
                name="ai_bill_parser",
                provider=self._configured_ai_provider_name("bill"),
                configured=True,
                warnings=["external_processing_blocked", *blockers],
                privacy_blockers=blockers,
            )

        started = time.perf_counter()
        try:
            candidate, warnings = external_ai_parser.parse_bill(
                ParseBillRequest(
                    text="瑞幸咖啡\n微信支付\n实付 18.50 元",
                    source=BillSource.ai_chat,
                )
            )
            latency_ms = self._elapsed_ms(started)
        except Exception as error:
            return self._failed_probe(
                name="ai_bill_parser",
                provider=self._configured_ai_provider_name("bill"),
                latency_ms=self._elapsed_ms(started),
                warnings=["external_ai_parser_failed"],
                error=type(error).__name__,
            )

        if candidate is None:
            return self._failed_probe(
                name="ai_bill_parser",
                provider=self._configured_ai_provider_name("bill"),
                latency_ms=latency_ms,
                warnings=warnings or ["external_ai_parser_failed"],
                error="NoCandidate",
            )

        return self._successful_probe(
            name="ai_bill_parser",
            provider=self._configured_ai_provider_name("bill"),
            latency_ms=latency_ms,
            warnings=candidate.warnings,
            response_preview={
                "intent": candidate.intent,
                "confidence": candidate.confidence,
                "amount": str(candidate.data.amount) if candidate.data.amount else None,
                "merchant": candidate.data.merchant,
                "category": candidate.data.category,
            },
        )

    def _probe_ai_task_parser(self) -> IntegrationProbeResult:
        configured = settings.real_ai_parser_enabled or settings.llm_agent_configured_for_kind("task")
        blockers = self._external_ai_privacy_blockers() + self._llm_credential_blockers("task")
        if not configured:
            return self._skipped_probe(
                name="ai_task_parser",
                provider=self._configured_ai_provider_name("task"),
                configured=False,
                warnings=["rule_based_parser_fallback"],
            )
        if blockers:
            return self._skipped_probe(
                name="ai_task_parser",
                provider=self._configured_ai_provider_name("task"),
                configured=True,
                warnings=["external_processing_blocked", *blockers],
                privacy_blockers=blockers,
            )

        started = time.perf_counter()
        try:
            candidate, warnings = external_ai_parser.parse_task(
                ParseTaskRequest(
                    text="明天下午 3 点提醒我开项目会，准备周报",
                    source=TaskSource.ai_chat,
                )
            )
            latency_ms = self._elapsed_ms(started)
        except Exception as error:
            return self._failed_probe(
                name="ai_task_parser",
                provider=self._configured_ai_provider_name("task"),
                latency_ms=self._elapsed_ms(started),
                warnings=["external_ai_parser_failed"],
                error=type(error).__name__,
            )

        if candidate is None:
            return self._failed_probe(
                name="ai_task_parser",
                provider=self._configured_ai_provider_name("task"),
                latency_ms=latency_ms,
                warnings=warnings or ["external_ai_parser_failed"],
                error="NoCandidate",
            )

        return self._successful_probe(
            name="ai_task_parser",
            provider=self._configured_ai_provider_name("task"),
            latency_ms=latency_ms,
            warnings=candidate.warnings,
            response_preview={
                "intent": candidate.intent,
                "confidence": candidate.confidence,
                "title": candidate.data.title,
                "category": candidate.data.category,
                "task_type": candidate.data.task_type.value,
            },
        )

    def _probe_chat_intent(self) -> IntegrationProbeResult:
        configured = settings.real_ai_parser_enabled or settings.llm_agent_configured_for_kind("chat_intent")
        blockers = self._external_ai_privacy_blockers() + self._llm_credential_blockers("chat_intent")
        if not configured:
            return self._skipped_probe(
                name="chat_intent",
                provider=self._configured_ai_provider_name("chat_intent"),
                configured=False,
                warnings=["keyword_router_fallback"],
            )
        if blockers:
            return self._skipped_probe(
                name="chat_intent",
                provider=self._configured_ai_provider_name("chat_intent"),
                configured=True,
                warnings=["external_processing_blocked", *blockers],
                privacy_blockers=blockers,
            )

        started = time.perf_counter()
        try:
            route, warnings = external_ai_parser.route_chat(
                "明天下午 3 点提醒我开项目会"
            )
            latency_ms = self._elapsed_ms(started)
        except Exception as error:
            return self._failed_probe(
                name="chat_intent",
                provider=self._configured_ai_provider_name("chat_intent"),
                latency_ms=self._elapsed_ms(started),
                warnings=["external_ai_parser_failed"],
                error=type(error).__name__,
            )

        if route is None:
            return self._failed_probe(
                name="chat_intent",
                provider=self._configured_ai_provider_name("chat_intent"),
                latency_ms=latency_ms,
                warnings=warnings or ["external_chat_intent_invalid_response"],
                error="NoRoute",
            )

        return self._successful_probe(
            name="chat_intent",
            provider=self._configured_ai_provider_name("chat_intent"),
            latency_ms=latency_ms,
            warnings=route.warnings,
            response_preview={
                "intent": route.intent.value,
                "confidence": route.confidence,
                "reply_sample": self._preview_text(route.reply or ""),
            },
        )

    def _external_ai_privacy_blockers(self) -> list[str]:
        privacy_settings = settings_store.get_privacy_settings()
        blockers: list[str] = []
        if privacy_settings.local_only_mode:
            blockers.append("local_only_mode_enabled")
        if not privacy_settings.allow_ai_text_processing:
            blockers.append("ai_text_processing_disabled")
        return blockers

    def _llm_credential_blockers(self, kind: str) -> list[str]:
        if not settings.llm_agent_configured_for_kind(kind) or not settings.llm_agent_api_key_required_for_kind(kind):
            return []
        if settings.llm_agent_api_key_for_kind(kind):
            return []
        if settings.deepseek_llm_agent_enabled_for_kind(kind):
            return ["deepseek_api_key_missing"]
        if settings.siliconflow_llm_agent_enabled_for_kind(kind):
            return ["siliconflow_api_key_missing"]
        return ["llm_api_key_missing"]

    def _ocr_credential_blockers(self) -> list[str]:
        if settings.real_ocr_enabled and settings.kimi_vision_ocr_enabled and not settings.external_ocr_api_key:
            return ["kimi_api_key_missing"]
        return []

    def _configured_ai_provider_name(self, kind: str) -> str:
        if settings.llm_agent_configured_for_kind(kind):
            return settings.llm_agent_provider_for_kind(kind)
        return settings.ai_parser_provider_name

    def _integration_check_status(self, configured: bool, blockers: list[str]) -> str:
        if not configured:
            return "fallback"
        if blockers:
            return "blocked"
        return "ready"

    def _integration_status(self, blocked_count: int, fallback_count: int) -> str:
        if blocked_count:
            return "blocked"
        if fallback_count:
            return "fallback"
        return "ready"

    def _probe_status(self, success_count: int, failed_count: int) -> str:
        if failed_count:
            return "failed"
        if success_count:
            return "success"
        return "skipped"

    def _skipped_probe(
        self,
        *,
        name: str,
        provider: str,
        configured: bool,
        warnings: list[str],
        privacy_blockers: list[str] | None = None,
    ) -> IntegrationProbeResult:
        return IntegrationProbeResult(
            name=name,
            provider=provider,
            status="skipped",
            configured=configured,
            attempted=False,
            success=False,
            privacy_blockers=privacy_blockers or [],
            warnings=self._dedupe(warnings),
        )

    def _failed_probe(
        self,
        *,
        name: str,
        provider: str,
        latency_ms: float,
        warnings: list[str],
        error: str,
    ) -> IntegrationProbeResult:
        return IntegrationProbeResult(
            name=name,
            provider=provider,
            status="failed",
            configured=True,
            attempted=True,
            success=False,
            latency_ms=latency_ms,
            warnings=self._dedupe(warnings),
            error=error,
        )

    def _successful_probe(
        self,
        *,
        name: str,
        provider: str,
        latency_ms: float,
        warnings: list[str],
        response_preview: dict[str, Any],
    ) -> IntegrationProbeResult:
        return IntegrationProbeResult(
            name=name,
            provider=provider,
            status="success",
            configured=True,
            attempted=True,
            success=True,
            latency_ms=latency_ms,
            warnings=self._dedupe(warnings),
            response_preview=response_preview,
        )

    def _elapsed_ms(self, started: float) -> float:
        return round((time.perf_counter() - started) * 1000, 2)

    def _warning_list(self, raw_value: Any) -> list[str]:
        if not isinstance(raw_value, list):
            return []
        return [str(warning) for warning in raw_value if str(warning).strip()]

    def _optional_float(self, raw_value: Any) -> float | None:
        try:
            return float(raw_value)
        except (TypeError, ValueError):
            return None

    def _preview_text(self, text: str, max_length: int = 80) -> str:
        cleaned = " ".join(text.split())
        if len(cleaned) <= max_length:
            return cleaned
        return cleaned[:max_length]

    def _dedupe(self, values: list[str]) -> list[str]:
        deduped: list[str] = []
        for value in values:
            if value and value not in deduped:
                deduped.append(value)
        return deduped

    def _readiness_status(self, components: list[ReadinessComponent]) -> str:
        statuses = {component.status for component in components}
        if "action_required" in statuses:
            return "action_required"
        if "degraded" in statuses:
            return "degraded"
        return "ready"

    def _path_writable(self, path: object) -> bool:
        try:
            target = settings.local_bill_path.parent if path is None else path
            target.mkdir(parents=True, exist_ok=True)  # type: ignore[attr-defined]
            probe_path = target / ".lifesnap_write_probe"  # type: ignore[operator]
            probe_path.write_text("ok", encoding="utf-8")
            probe_path.unlink(missing_ok=True)
            return True
        except OSError:
            return False

    def _privacy_issues(self) -> list[DiagnosticIssue]:
        privacy_settings = settings_store.get_privacy_settings()
        issues: list[DiagnosticIssue] = []
        if not privacy_settings.allow_ai_text_processing:
            issues.append(
                DiagnosticIssue(
                    code="ai_text_processing_disabled",
                    severity=DiagnosticSeverity.warning,
                    message="AI text processing is disabled, so parsing from chat or OCR text will be limited.",
                    entity_type="settings",
                )
            )
        if privacy_settings.save_original_attachments_by_default:
            issues.append(
                DiagnosticIssue(
                    code="original_attachment_retention_enabled",
                    severity=DiagnosticSeverity.info,
                    message="Original attachments are kept by default. This may increase local storage and privacy exposure.",
                    entity_type="settings",
                )
            )
        return issues

    def _attachment_issues(self) -> list[DiagnosticIssue]:
        attachments = attachment_store.all()
        issues: list[DiagnosticIssue] = []
        for attachment in attachments:
            if attachment.ocr_text is None:
                issues.append(self._attachment_missing_ocr_issue(attachment))

        checksum_groups: dict[str, list[AttachmentRead]] = {}
        for attachment in attachments:
            checksum_groups.setdefault(attachment.checksum, []).append(attachment)
        for matches in checksum_groups.values():
            if len(matches) < 2:
                continue
            first = sorted(matches, key=lambda item: item.created_at)[0]
            issues.append(
                DiagnosticIssue(
                    code="duplicate_attachment",
                    severity=DiagnosticSeverity.info,
                    message="Multiple attachments share the same checksum.",
                    entity_type="attachment",
                    entity_id=str(first.id),
                    related_entity_ids=[str(item.id) for item in matches[1:]],
                    metadata={
                        "duplicate_count": len(matches) - 1,
                        "filename": first.filename,
                    },
                )
            )
        return issues

    def _attachment_missing_ocr_issue(self, attachment: AttachmentRead) -> DiagnosticIssue:
        return DiagnosticIssue(
            code="attachment_missing_ocr_text",
            severity=DiagnosticSeverity.warning,
            message="Attachment has no OCR text yet. It may need recognition or manual entry.",
            entity_type="attachment",
            entity_id=str(attachment.id),
            metadata={
                "filename": attachment.filename,
                "content_type": attachment.content_type,
                "source": attachment.source,
            },
        )

    def _candidate_issues(self) -> list[DiagnosticIssue]:
        issues: list[DiagnosticIssue] = []
        bill_candidates = bill_candidate_store.all()
        task_candidates = task_candidate_store.all()
        diary_candidates = diary_candidate_store.all()
        if bill_candidates:
            issues.append(
                DiagnosticIssue(
                    code="pending_bill_candidates",
                    severity=DiagnosticSeverity.info,
                    message="There are bill candidates waiting for user confirmation.",
                    entity_type="bill_candidate",
                    related_entity_ids=[
                        str(candidate.candidate_id) for candidate in bill_candidates[:10]
                    ],
                    metadata={"candidate_count": len(bill_candidates)},
                )
            )
        if task_candidates:
            issues.append(
                DiagnosticIssue(
                    code="pending_task_candidates",
                    severity=DiagnosticSeverity.info,
                    message="There are task candidates waiting for user confirmation.",
                    entity_type="task_candidate",
                    related_entity_ids=[
                        str(candidate.candidate_id) for candidate in task_candidates[:10]
                    ],
                    metadata={"candidate_count": len(task_candidates)},
                )
            )
        if diary_candidates:
            issues.append(
                DiagnosticIssue(
                    code="pending_diary_candidates",
                    severity=DiagnosticSeverity.info,
                    message="There are diary candidates waiting for user confirmation.",
                    entity_type="diary_candidate",
                    related_entity_ids=[
                        str(candidate.candidate_id) for candidate in diary_candidates[:10]
                    ],
                    metadata={"candidate_count": len(diary_candidates)},
                )
            )
        issues.extend(
            self._candidate_field_issues(
                bill_candidates,
                task_candidates,
                diary_candidates,
            )
        )
        return issues

    def _candidate_field_issues(
        self,
        bill_candidates: list[ParseBillResponse],
        task_candidates: list[ParseTaskResponse],
        diary_candidates: list[ParseDiaryResponse],
    ) -> list[DiagnosticIssue]:
        issues: list[DiagnosticIssue] = []
        for candidate in bill_candidates:
            if bill_candidate_store.is_confirmable(candidate):
                continue
            issues.append(
                DiagnosticIssue(
                    code="bill_candidate_missing_required_fields",
                    severity=DiagnosticSeverity.action_required,
                    message="Bill candidate is missing amount and cannot be confirmed yet.",
                    entity_type="bill_candidate",
                    entity_id=str(candidate.candidate_id),
                    metadata={"warnings": candidate.warnings},
                )
            )
        for candidate in task_candidates:
            if task_candidate_store.is_confirmable(candidate):
                continue
            issues.append(
                DiagnosticIssue(
                    code="task_candidate_missing_required_fields",
                    severity=DiagnosticSeverity.action_required,
                    message="Task candidate is missing title or reminder time and cannot be confirmed yet.",
                    entity_type="task_candidate",
                    entity_id=str(candidate.candidate_id),
                    metadata={"warnings": candidate.warnings},
                )
            )
        for candidate in diary_candidates:
            if diary_candidate_store.is_confirmable(candidate):
                continue
            issues.append(
                DiagnosticIssue(
                    code="diary_candidate_missing_required_fields",
                    severity=DiagnosticSeverity.action_required,
                    message="Diary candidate is missing date, title, or content and cannot be confirmed yet.",
                    entity_type="diary_candidate",
                    entity_id=str(candidate.candidate_id),
                    metadata={"warnings": candidate.warnings},
                )
            )
        return issues

    def _duplicate_bill_issues(self, time_window_minutes: int) -> list[DiagnosticIssue]:
        bills = sorted(bill_store.all(), key=lambda bill: bill.paid_at)
        issues: list[DiagnosticIssue] = []
        for index, bill in enumerate(bills):
            for other in bills[index + 1 :]:
                if not self._is_possible_duplicate_bill(
                    bill,
                    other,
                    time_window_minutes,
                ):
                    continue
                issues.append(
                    DiagnosticIssue(
                        code="possible_duplicate_bill",
                        severity=DiagnosticSeverity.warning,
                        message="Two bills have the same amount, type, nearby paid time, and matching optional merchant.",
                        entity_type="bill",
                        entity_id=str(bill.id),
                        related_entity_ids=[str(other.id)],
                        metadata={
                            "merchant": bill.merchant,
                            "amount": bill.amount,
                            "transaction_type": bill.transaction_type,
                            "time_window_minutes": time_window_minutes,
                        },
                    )
                )
        return issues

    def _is_possible_duplicate_bill(
        self,
        bill: BillRead,
        other: BillRead,
        time_window_minutes: int,
    ) -> bool:
        if bill.amount != other.amount:
            return False
        if bill.transaction_type != other.transaction_type:
            return False
        if self._merchant_key(bill.merchant) != self._merchant_key(other.merchant):
            return False
        delta = abs(
            self._as_utc(bill.paid_at)
            - self._as_utc(other.paid_at)
        )
        return delta.total_seconds() <= time_window_minutes * 60

    def _as_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _merchant_key(self, merchant: str | None) -> str:
        return (merchant or "").strip().casefold()

    def _task_issues(self, now: datetime) -> list[DiagnosticIssue]:
        issues: list[DiagnosticIssue] = []
        for task in task_store.all():
            if task.status != TaskStatus.pending:
                continue
            target_at = self._task_target_at(task)
            if target_at is None:
                issues.append(
                    DiagnosticIssue(
                        code="unscheduled_pending_task",
                        severity=DiagnosticSeverity.info,
                        message="Pending task has no due or reminder time.",
                        entity_type="task",
                        entity_id=str(task.id),
                        metadata={"title": task.title, "category": task.category},
                    )
                )
                continue
            if target_at < now:
                issues.append(
                    DiagnosticIssue(
                        code="overdue_task",
                        severity=DiagnosticSeverity.action_required,
                        message="Pending task is overdue.",
                        entity_type="task",
                        entity_id=str(task.id),
                        metadata={
                            "title": task.title,
                            "target_at": target_at,
                            "task_type": task.task_type,
                            "priority": task.priority,
                        },
                    )
                )
        return issues

    def _task_target_at(self, task: TaskRead) -> datetime | None:
        target_at = task.remind_at if task.task_type == TaskType.reminder else task.due_at
        target_at = target_at or task.due_at or task.remind_at
        if target_at is None:
            return None
        if target_at.tzinfo is None:
            return target_at.replace(tzinfo=timezone.utc)
        return target_at.astimezone(timezone.utc)

    def _recycle_bin_issues(self) -> list[DiagnosticIssue]:
        summary = data_management_service.summary()
        issues: list[DiagnosticIssue] = []
        if summary.deleted_bill_count:
            issues.append(
                DiagnosticIssue(
                    code="deleted_bills_in_recycle_bin",
                    severity=DiagnosticSeverity.info,
                    message="There are deleted bills available for restore.",
                    entity_type="bill",
                    metadata={"deleted_bill_count": summary.deleted_bill_count},
                )
            )
        if summary.deleted_task_count:
            issues.append(
                DiagnosticIssue(
                    code="deleted_tasks_in_recycle_bin",
                    severity=DiagnosticSeverity.info,
                    message="There are deleted tasks available for restore.",
                    entity_type="task",
                    metadata={"deleted_task_count": summary.deleted_task_count},
                )
            )
        return issues

    def _severity_count(
        self,
        issues: list[DiagnosticIssue],
        severity: DiagnosticSeverity,
    ) -> int:
        return len([issue for issue in issues if issue.severity == severity])

    def _status(self, warning_count: int, action_required_count: int) -> str:
        if action_required_count:
            return "action_required"
        if warning_count:
            return "warning"
        return "ok"

    def _issue_sort_key(self, issue: DiagnosticIssue) -> tuple[int, str]:
        severity_order = {
            DiagnosticSeverity.action_required: 0,
            DiagnosticSeverity.warning: 1,
            DiagnosticSeverity.info: 2,
        }
        return (severity_order[issue.severity], issue.code)


diagnostics_service = DiagnosticsService()
