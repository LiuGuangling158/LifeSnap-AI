from __future__ import annotations

import json
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
from app.schemas.task import TaskPriority, TaskType
from app.services.settings_store import settings_store


class ExternalAiParserService:
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
        except (TypeError, ValueError, ValidationError):
            return None, ["external_ai_parser_invalid_response"]

        field_confidence = self._field_confidence(
            response_body.get("field_confidence"),
            self._bill_field_confidence(data),
        )
        warnings = self._dedupe(
            self._bill_warnings(data) + self._response_warnings(response_body)
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
                need_user_confirmation=self._bool_value(
                    response_body.get("need_user_confirmation"),
                    default=True,
                ),
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
            return None, ["external_ai_parser_invalid_response"]

        field_confidence = self._field_confidence(
            response_body.get("field_confidence"),
            self._task_field_confidence(data),
        )
        warnings = self._dedupe(
            self._task_warnings(data) + self._response_warnings(response_body)
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
                need_user_confirmation=self._bool_value(
                    response_body.get("need_user_confirmation"),
                    default=True,
                ),
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
        endpoint = settings.external_ai_parser_endpoint
        if endpoint is None:
            return None, []

        request_body = {
            "schema_version": "lifesnap.ai.parse.v1",
            "kind": kind,
            "text": text,
            "source": source,
            "locale": "zh-CN",
            "current_datetime": datetime.now().astimezone().isoformat(),
        }
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

    def _response_data(self, response_body: dict[str, Any]) -> dict[str, Any]:
        raw_data = response_body.get("data")
        if raw_data is None:
            raw_data = response_body
        if not isinstance(raw_data, dict):
            raise TypeError("External AI parser response data must be an object.")
        return dict(raw_data)

    def _response_warnings(self, response_body: dict[str, Any]) -> list[str]:
        warnings = response_body.get("warnings")
        if not isinstance(warnings, list):
            return []
        return [str(warning) for warning in warnings if str(warning).strip()]

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

    def _bool_value(self, raw_value: Any, default: bool) -> bool:
        if isinstance(raw_value, bool):
            return raw_value
        return default

    def _bill_warnings(self, data: BillCandidateData) -> list[str]:
        warnings: list[str] = []
        if data.amount is None:
            warnings.append("amount_missing")
        if data.merchant is None:
            warnings.append("merchant_missing")
        if data.payment_method is None:
            warnings.append("payment_method_missing")
        if data.category == "其他":
            warnings.append("category_low_confidence")
        return warnings

    def _bill_field_confidence(self, data: BillCandidateData) -> dict[str, float]:
        return {
            "amount": 0.9 if data.amount is not None else 0.0,
            "merchant": 0.85 if data.merchant is not None else 0.0,
            "category": 0.8 if data.category != "其他" else 0.45,
            "payment_method": 0.8 if data.payment_method is not None else 0.0,
            "paid_at": 0.8 if data.paid_at is not None else 0.0,
        }

    def _bill_overall_confidence(self, field_confidence: dict[str, float]) -> float:
        important_fields = ["amount", "merchant", "category", "payment_method"]
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
