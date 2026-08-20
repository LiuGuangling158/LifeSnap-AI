from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID

from app.core.config import settings
from app.schemas.ocr import OcrRecognitionStatus, OcrRecognizeResponse
from app.services.attachment_store import attachment_store
from app.services.settings_store import settings_store


class ConfigurableOcrService:
    def recognize(self, attachment_id: UUID) -> OcrRecognizeResponse | None:
        attachment = attachment_store.get(attachment_id)
        if attachment is None:
            return None

        if attachment.ocr_text:
            return self._recognized(
                attachment_id=attachment_id,
                text=attachment.ocr_text,
                confidence=0.95,
                provider="stored_text",
            )

        if settings.real_ocr_enabled:
            return self._recognize_with_external_provider(attachment_id)

        return self._manual_required(
            attachment_id=attachment_id,
            provider=settings.ocr_provider_name,
            warnings=["ocr_engine_not_configured", "manual_entry_required"],
        )

    def _recognize_with_external_provider(self, attachment_id: UUID) -> OcrRecognizeResponse:
        privacy_settings = settings_store.get_privacy_settings()
        if privacy_settings.local_only_mode:
            return self._manual_required(
                attachment_id=attachment_id,
                provider=settings.ocr_provider_name,
                warnings=["local_only_mode_enabled", "manual_entry_required"],
            )
        if not privacy_settings.allow_ai_text_processing:
            return self._manual_required(
                attachment_id=attachment_id,
                provider=settings.ocr_provider_name,
                warnings=["ai_text_processing_disabled", "manual_entry_required"],
            )

        original = attachment_store.original_content(attachment_id)
        if original is None:
            return self._manual_required(
                attachment_id=attachment_id,
                provider=settings.ocr_provider_name,
                warnings=["original_attachment_missing", "manual_entry_required"],
            )

        attachment, content = original
        try:
            response = self._call_external_ocr(
                attachment_id=attachment_id,
                filename=attachment.filename,
                content_type=attachment.content_type,
                content=content,
            )
        except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
            return self._manual_required(
                attachment_id=attachment_id,
                provider=settings.ocr_provider_name,
                warnings=["external_ocr_failed", "manual_entry_required"],
            )

        text = str(response.get("text") or "").strip()
        if not text:
            return self._manual_required(
                attachment_id=attachment_id,
                provider=settings.ocr_provider_name,
                warnings=self._response_warnings(response, "external_ocr_empty_text"),
            )

        attachment_store.update_ocr_text(attachment_id, text)
        return self._recognized(
            attachment_id=attachment_id,
            text=text,
            confidence=self._confidence(response.get("confidence")),
            provider=str(response.get("provider") or settings.ocr_provider_name),
            warnings=self._response_warnings(response),
        )

    def _call_external_ocr(
        self,
        *,
        attachment_id: UUID,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> dict:
        payload = {
            "attachment_id": str(attachment_id),
            "filename": filename,
            "content_type": content_type,
            "content_base64": base64.b64encode(content).decode("ascii"),
        }
        headers = {"Content-Type": "application/json"}
        if settings.external_ocr_api_key:
            headers["Authorization"] = f"Bearer {settings.external_ocr_api_key}"

        request = Request(
            settings.external_ocr_endpoint or "",
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urlopen(request, timeout=settings.external_ocr_timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))

    def _recognized(
        self,
        *,
        attachment_id: UUID,
        text: str,
        confidence: float,
        provider: str,
        warnings: list[str] | None = None,
    ) -> OcrRecognizeResponse:
        return OcrRecognizeResponse(
            attachment_id=attachment_id,
            status=OcrRecognitionStatus.recognized,
            text=text,
            confidence=confidence,
            provider=provider,
            warnings=warnings or [],
            manual_entry_required=False,
            recognized_at=datetime.now(timezone.utc),
        )

    def _manual_required(
        self,
        *,
        attachment_id: UUID,
        provider: str,
        warnings: list[str],
    ) -> OcrRecognizeResponse:
        return OcrRecognizeResponse(
            attachment_id=attachment_id,
            status=OcrRecognitionStatus.manual_required,
            text=None,
            confidence=0.0,
            provider=provider,
            warnings=warnings,
            manual_entry_required=True,
            recognized_at=datetime.now(timezone.utc),
        )

    def _confidence(self, value: object) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return 0.8
        return max(0.0, min(1.0, number))

    def _response_warnings(self, response: dict, fallback: str | None = None) -> list[str]:
        warnings = response.get("warnings")
        if isinstance(warnings, list):
            normalized = [str(item) for item in warnings if str(item)]
            if normalized:
                return normalized
        return [fallback, "manual_entry_required"] if fallback else []


ocr_service = ConfigurableOcrService()
