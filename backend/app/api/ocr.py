from fastapi import APIRouter, HTTPException, status

from app.schemas.ocr import OcrRecognizeRequest, OcrRecognizeResponse
from app.services.ocr_service import ocr_service

router = APIRouter(prefix="/ocr", tags=["ocr"])


@router.post("/recognize", response_model=OcrRecognizeResponse)
def recognize_ocr(payload: OcrRecognizeRequest) -> OcrRecognizeResponse:
    result = ocr_service.recognize(payload.attachment_id)
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )
    return result
