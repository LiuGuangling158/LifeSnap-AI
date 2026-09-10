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
)
from app.schemas.task import TaskRead, TaskSource, TaskStatus, TaskType
from app.services.attachment_store import attachment_store
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

    def _ocr_integration_check(self) -> IntegrationCheck:
        configured = settings.real_ocr_enabled
        blockers = self._external_ai_privacy_blockers()
        warnings: list[str] = []
        next_action: str | None = None

        if not configured:
            warnings.append("ocr_engine_not_configured")
            next_action = "Set LIFESNAP_OCR_ENDPOINT to enable external OCR."
        elif blockers:
            next_action = "Disable local-only mode and allow AI text processing before using external OCR."
        if configured:
            warnings.append("original_attachment_required_for_external_ocr")

        return IntegrationCheck(
            name="ocr",
            provider=settings.ocr_provider_name,
            status=self._integration_check_status(configured, blockers),
            configured=configured,
            ready=configured and not blockers,
            endpoint_configured=bool(settings.external_ocr_endpoint),
            api_key_configured=bool(settings.external_ocr_api_key),
            timeout_seconds=settings.external_ocr_timeout_seconds,
            capabilities=["attachment_text_recognition", "stored_text_fallback"],
            privacy_blockers=blockers,
            warnings=warnings,
            next_action=next_action,
        )

    def _ai_parser_integration_check(self) -> IntegrationCheck:
        configured = settings.real_ai_parser_enabled or settings.llm_agent_configured
        blockers = self._external_ai_privacy_blockers() + self._llm_credential_blockers()
        warnings: list[str] = []
        next_action: str | None = None

        if not configured:
            warnings.append("rule_based_parser_fallback")
            next_action = "Set DEEPSEEK_API_KEY to enable the built-in DeepSeek LLM agent, or set LIFESNAP_AI_PARSE_ENDPOINT for a custom parser."
        elif "deepseek_api_key_missing" in blockers:
            next_action = "Set DEEPSEEK_API_KEY or LIFESNAP_LLM_API_KEY before using DeepSeek."
        elif blockers:
            next_action = "Disable local-only mode and allow AI text processing before using external AI parsing."

        capabilities = ["bill_candidate_parsing", "task_candidate_parsing"]
        if settings.llm_agent_configured:
            capabilities.extend(["llm_agent_reasoning", "llm_json_output", "llm_function_calling"])
        if settings.deepseek_llm_agent_enabled:
            capabilities.append("deepseek_chat_completions")

        return IntegrationCheck(
            name="ai_parser",
            provider=self._configured_ai_provider_name(),
            status=self._integration_check_status(configured, blockers),
            configured=configured,
            ready=configured and not blockers,
            endpoint_configured=bool(settings.external_ai_parser_endpoint or settings.llm_agent_base_url),
            api_key_configured=bool(settings.external_ai_parser_api_key or settings.llm_agent_api_key),
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
        configured = settings.real_ai_parser_enabled or settings.llm_agent_configured
        blockers = self._external_ai_privacy_blockers() + self._llm_credential_blockers()
        warnings: list[str] = []
        next_action: str | None = None

        if not configured:
            warnings.append("keyword_router_fallback")
            next_action = "Set DEEPSEEK_API_KEY to enable DeepSeek chat routing, or set LIFESNAP_AI_PARSE_ENDPOINT for a custom parser."
        elif "deepseek_api_key_missing" in blockers:
            next_action = "Set DEEPSEEK_API_KEY or LIFESNAP_LLM_API_KEY before using DeepSeek."
        elif blockers:
            next_action = "Disable local-only mode and allow AI text processing before using external chat intent routing."

        capabilities = ["chat_intent_routing", "chat_candidate_flow"]
        if settings.llm_agent_configured:
            capabilities.extend(["llm_agent_reasoning", "llm_json_output", "llm_function_calling"])
        if settings.deepseek_llm_agent_enabled:
            capabilities.append("deepseek_chat_completions")

        return IntegrationCheck(
            name="chat_intent",
            provider=self._configured_ai_provider_name(),
            status=self._integration_check_status(configured, blockers),
            configured=configured,
            ready=configured and not blockers,
            endpoint_configured=bool(settings.external_ai_parser_endpoint or settings.llm_agent_base_url),
            api_key_configured=bool(settings.external_ai_parser_api_key or settings.llm_agent_api_key),
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
        configured = settings.real_ai_parser_enabled or settings.llm_agent_configured
        blockers = self._external_ai_privacy_blockers() + self._llm_credential_blockers()
        if not configured:
            return self._skipped_probe(
                name="ai_bill_parser",
                provider=self._configured_ai_provider_name(),
                configured=False,
                warnings=["rule_based_parser_fallback"],
            )
        if blockers:
            return self._skipped_probe(
                name="ai_bill_parser",
                provider=self._configured_ai_provider_name(),
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
                provider=self._configured_ai_provider_name(),
                latency_ms=self._elapsed_ms(started),
                warnings=["external_ai_parser_failed"],
                error=type(error).__name__,
            )

        if candidate is None:
            return self._failed_probe(
                name="ai_bill_parser",
                provider=self._configured_ai_provider_name(),
                latency_ms=latency_ms,
                warnings=warnings or ["external_ai_parser_failed"],
                error="NoCandidate",
            )

        return self._successful_probe(
            name="ai_bill_parser",
            provider=self._configured_ai_provider_name(),
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
        configured = settings.real_ai_parser_enabled or settings.llm_agent_configured
        blockers = self._external_ai_privacy_blockers() + self._llm_credential_blockers()
        if not configured:
            return self._skipped_probe(
                name="ai_task_parser",
                provider=self._configured_ai_provider_name(),
                configured=False,
                warnings=["rule_based_parser_fallback"],
            )
        if blockers:
            return self._skipped_probe(
                name="ai_task_parser",
                provider=self._configured_ai_provider_name(),
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
                provider=self._configured_ai_provider_name(),
                latency_ms=self._elapsed_ms(started),
                warnings=["external_ai_parser_failed"],
                error=type(error).__name__,
            )

        if candidate is None:
            return self._failed_probe(
                name="ai_task_parser",
                provider=self._configured_ai_provider_name(),
                latency_ms=latency_ms,
                warnings=warnings or ["external_ai_parser_failed"],
                error="NoCandidate",
            )

        return self._successful_probe(
            name="ai_task_parser",
            provider=self._configured_ai_provider_name(),
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
        configured = settings.real_ai_parser_enabled or settings.llm_agent_configured
        blockers = self._external_ai_privacy_blockers() + self._llm_credential_blockers()
        if not configured:
            return self._skipped_probe(
                name="chat_intent",
                provider=self._configured_ai_provider_name(),
                configured=False,
                warnings=["keyword_router_fallback"],
            )
        if blockers:
            return self._skipped_probe(
                name="chat_intent",
                provider=self._configured_ai_provider_name(),
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
                provider=self._configured_ai_provider_name(),
                latency_ms=self._elapsed_ms(started),
                warnings=["external_ai_parser_failed"],
                error=type(error).__name__,
            )

        if route is None:
            return self._failed_probe(
                name="chat_intent",
                provider=self._configured_ai_provider_name(),
                latency_ms=latency_ms,
                warnings=warnings or ["external_chat_intent_invalid_response"],
                error="NoRoute",
            )

        return self._successful_probe(
            name="chat_intent",
            provider=self._configured_ai_provider_name(),
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

    def _llm_credential_blockers(self) -> list[str]:
        if settings.llm_agent_configured and settings.deepseek_llm_agent_enabled and not settings.llm_agent_api_key:
            return ["deepseek_api_key_missing"]
        return []

    def _configured_ai_provider_name(self) -> str:
        if settings.llm_agent_configured:
            return settings.llm_agent_provider
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
