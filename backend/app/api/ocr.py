from fastapi import APIRouter, HTTPException, Request, status

from app.schemas.ocr import OcrRecognizeRequest, OcrRecognizeResponse
from app.services.audit_log_store import audit_log_store
from app.services.ocr_service import ocr_service

router = APIRouter(prefix="/ocr", tags=["ocr"])


@router.post("/recognize", response_model=OcrRecognizeResponse)
def recognize_ocr(payload: OcrRecognizeRequest, request: Request) -> OcrRecognizeResponse:
    result = ocr_service.recognize(payload.attachment_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )
    audit_log_store.record(
        action="ocr_recognized",
        entity_type="attachment",
        entity_id=payload.attachment_id,
        request=request,
        metadata={"ocr_status": result.status, "warning_count": len(result.warnings)},
    )
    return result
