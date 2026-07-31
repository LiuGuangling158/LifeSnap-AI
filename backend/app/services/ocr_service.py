from datetime import datetime, timezone
from uuid import UUID

from app.schemas.ocr import OcrRecognitionStatus, OcrRecognizeResponse
from app.services.attachment_store import attachment_store


class RuleBasedOcrService:
    def recognize(self, attachment_id: UUID) -> OcrRecognizeResponse | None:
        attachment = attachment_store.get(attachment_id)
        if attachment is None:
            return None

        if attachment.ocr_text:
            return OcrRecognizeResponse(
                attachment_id=attachment_id,
                status=OcrRecognitionStatus.recognized,
                text=attachment.ocr_text,
                confidence=0.95,
                warnings=[],
                manual_entry_required=False,
                recognized_at=datetime.now(timezone.utc),
            )

        return OcrRecognizeResponse(
            attachment_id=attachment_id,
            status=OcrRecognitionStatus.manual_required,
            text=None,
            confidence=0.0,
            warnings=["ocr_engine_not_configured", "manual_entry_required"],
            manual_entry_required=True,
            recognized_at=datetime.now(timezone.utc),
        )


ocr_service = RuleBasedOcrService()
