from __future__ import annotations

import base64
import json
import re
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
        if settings.kimi_vision_ocr_enabled and not settings.external_ocr_api_key:
            return self._manual_required(
                attachment_id=attachment_id,
                provider=settings.ocr_provider_name,
                warnings=["kimi_api_key_missing", "manual_entry_required"],
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
        if settings.kimi_vision_ocr_enabled:
            return self._call_kimi_vision_ocr(
                filename=filename,
                content_type=content_type,
                content=content,
            )
        return self._call_custom_ocr_provider(
            attachment_id=attachment_id,
            filename=filename,
            content_type=content_type,
            content=content,
        )

    def _call_custom_ocr_provider(
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

    def _call_kimi_vision_ocr(
        self,
        *,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> dict:
        if not content_type.startswith("image/"):
            return {
                "text": "",
                "confidence": 0,
                "provider": settings.ocr_provider_name,
                "warnings": ["kimi_vision_unsupported_content_type", "manual_entry_required"],
            }

        request_body = self._kimi_vision_request_body(
            filename=filename,
            content_type=content_type,
            content=content,
        )
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if settings.external_ocr_api_key:
            headers["Authorization"] = f"Bearer {settings.external_ocr_api_key}"

        request = Request(
            settings.external_ocr_endpoint or "",
            data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urlopen(request, timeout=settings.external_ocr_timeout_seconds) as response:
            response_body = json.loads(response.read().decode("utf-8"))
        return self._kimi_vision_response_data(response_body)

    def _kimi_vision_request_body(
        self,
        *,
        filename: str,
        content_type: str,
        content: bytes,
    ) -> dict:
        image_url = f"data:{content_type};base64,{base64.b64encode(content).decode('ascii')}"
        return {
            "model": settings.external_ocr_model or "kimi-k2.6",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是 LifeSnap AI 的图片记账 OCR 引擎。"
                        "只识别图片中真实可见的账单、支付截图、发票或收据文字，不要编造。"
                        "只输出一个 JSON object，不要 Markdown。"
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": image_url}},
                        {
                            "type": "text",
                            "text": (
                                f"请识别文件 {filename} 中与记账相关的全部可见文字。"
                                "保留金额、商户、时间、支付方式、订单说明等关键行。"
                                "返回 JSON：{\"text\":\"识别出的原文\",\"confidence\":0到1,"
                                "\"provider\":\"kimi_vision\",\"warnings\":[]}。"
                                "如果无法识别，text 为空字符串，并在 warnings 中写 external_ocr_empty_text。"
                            ),
                        },
                    ],
                },
            ],
            "temperature": 0,
        }

    def _kimi_vision_response_data(self, response_body: dict) -> dict:
        content = self._chat_completion_content(response_body).strip()
        if not content:
            return {
                "text": "",
                "confidence": 0,
                "provider": settings.ocr_provider_name,
                "warnings": ["external_ocr_empty_text"],
            }
        try:
            parsed = self._json_object_from_text(content)
        except (ValueError, TypeError, json.JSONDecodeError):
            return {
                "text": content,
                "confidence": 0.75,
                "provider": settings.ocr_provider_name,
                "warnings": ["kimi_vision_non_json_response"],
            }

        text = str(parsed.get("text") or parsed.get("ocr_text") or "").strip()
        return {
            "text": text,
            "confidence": self._confidence(parsed.get("confidence")),
            "provider": str(parsed.get("provider") or settings.ocr_provider_name),
            "warnings": self._response_warnings(parsed),
        }

    def _chat_completion_content(self, response_body: dict) -> str:
        choices = response_body.get("choices")
        if not isinstance(choices, list) or not choices:
            raise ValueError("Kimi OCR response must include choices.")
        choice = choices[0]
        if not isinstance(choice, dict):
            raise ValueError("Kimi OCR choice must be an object.")
        message = choice.get("message")
        if not isinstance(message, dict):
            raise ValueError("Kimi OCR choice must include a message object.")
        content = message.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts = [str(part.get("text")) for part in content if isinstance(part, dict) and part.get("text")]
            if parts:
                return "".join(parts)
        raise ValueError("Kimi OCR message content must be text.")

    def _json_object_from_text(self, text: str) -> dict:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
            if match is None:
                raise
            parsed = json.loads(match.group(0))
        if not isinstance(parsed, dict):
            raise TypeError("Kimi OCR content must be a JSON object.")
        return parsed

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
