from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status

from app.schemas.agent import ParseBillRequest, ParseBillResponse
from app.schemas.attachment import (
    AttachmentBillParseResponse,
    AttachmentBillParseStatus,
    AttachmentDuplicateResponse,
    AttachmentOcrTextUpdate,
    AttachmentRead,
    AttachmentSource,
)
from app.schemas.bill import BillSource
from app.schemas.ocr import OcrRecognitionStatus
from app.services.audit_log_store import audit_log_store
from app.services.bill_candidate_store import bill_candidate_store
from app.services.bill_parser import bill_parser
from app.services.attachment_store import (
    AttachmentTooLargeError,
    UnsupportedAttachmentTypeError,
    attachment_store,
)
from app.services.ocr_service import ocr_service
from app.services.settings_store import settings_store

router = APIRouter(prefix="/attachments", tags=["attachments"])


@router.post("/upload", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    request: Request,
    file: UploadFile = File(...),
    source: AttachmentSource = Form(default=AttachmentSource.upload),
    save_original: bool | None = Form(default=None),
) -> AttachmentRead:
    content = await file.read()
    should_save_original = (
        save_original
        if save_original is not None
        else settings_store.get_privacy_settings().save_original_attachments_by_default
    )
    try:
        attachment = attachment_store.create(
            filename=file.filename or "attachment",
            content_type=file.content_type or "application/octet-stream",
            content=content,
            source=source,
            save_original=should_save_original,
        )
        audit_log_store.record(
            action="attachment_uploaded",
            entity_type="attachment",
            entity_id=attachment.id,
            request=request,
            metadata={
                "content_type": attachment.content_type,
                "file_size": attachment.file_size,
                "source": attachment.source,
                "duplicate_of": attachment.duplicate_of,
                "original_saved": attachment.original_saved,
            },
        )
        return attachment
    except AttachmentTooLargeError as exc:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(exc))
    except UnsupportedAttachmentTypeError as exc:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(exc))


@router.get("/{attachment_id}", response_model=AttachmentRead)
def get_attachment(attachment_id: UUID) -> AttachmentRead:
    attachment = attachment_store.get(attachment_id)
    if attachment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )
    return attachment


@router.get("/{attachment_id}/duplicates", response_model=AttachmentDuplicateResponse)
def get_attachment_duplicates(attachment_id: UUID) -> AttachmentDuplicateResponse:
    duplicates = attachment_store.duplicates_for(attachment_id)
    if duplicates is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )
    return duplicates


@router.patch("/{attachment_id}/ocr-text", response_model=AttachmentRead)
def update_attachment_ocr_text(
    attachment_id: UUID,
    payload: AttachmentOcrTextUpdate,
    request: Request,
) -> AttachmentRead:
    attachment = attachment_store.update_ocr_text(attachment_id, payload.ocr_text)
    if attachment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )
    audit_log_store.record(
        action="attachment_ocr_text_updated",
        entity_type="attachment",
        entity_id=attachment_id,
        request=request,
        metadata={"ocr_text_length": len(payload.ocr_text)},
    )
    return attachment


@router.post("/{attachment_id}/parse-bill", response_model=ParseBillResponse)
def parse_attachment_bill(attachment_id: UUID, request: Request) -> ParseBillResponse:
    privacy_settings = settings_store.get_privacy_settings()
    if not privacy_settings.allow_ai_text_processing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI text processing is disabled in privacy settings",
        )

    attachment = attachment_store.get(attachment_id)
    if attachment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )
    if not attachment.ocr_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Attachment OCR text is missing",
        )

    candidate = bill_parser.parse_bill(
        ParseBillRequest(
            text=attachment.ocr_text,
            source=_bill_source_from_attachment(attachment.source),
        )
    )
    saved_candidate = bill_candidate_store.save(candidate)
    if not privacy_settings.keep_ocr_text:
        attachment_store.clear_ocr_text(attachment_id)
    audit_log_store.record(
        action="attachment_bill_candidate_created",
        entity_type="bill_candidate",
        entity_id=saved_candidate.candidate_id,
        request=request,
        metadata={"attachment_id": attachment_id, "source": attachment.source},
    )
    return saved_candidate


@router.post(
    "/{attachment_id}/recognize-and-parse-bill",
    response_model=AttachmentBillParseResponse,
)
def recognize_and_parse_attachment_bill(
    attachment_id: UUID,
    request: Request,
) -> AttachmentBillParseResponse:
    privacy_settings = settings_store.get_privacy_settings()
    if not privacy_settings.allow_ai_text_processing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI text processing is disabled in privacy settings",
        )

    attachment = attachment_store.get(attachment_id)
    if attachment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )

    ocr_result = ocr_service.recognize(attachment_id)
    if ocr_result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )
    if ocr_result.status != OcrRecognitionStatus.recognized or not ocr_result.text:
        audit_log_store.record(
            action="attachment_recognition_manual_required",
            entity_type="attachment",
            entity_id=attachment_id,
            request=request,
            metadata={"ocr_status": ocr_result.status, "warning_count": len(ocr_result.warnings)},
        )
        return AttachmentBillParseResponse(
            attachment_id=attachment_id,
            status=AttachmentBillParseStatus.manual_required,
            ocr=ocr_result,
            candidate=None,
            warnings=ocr_result.warnings,
            manual_entry_required=True,
        )

    candidate = bill_parser.parse_bill(
        ParseBillRequest(
            text=ocr_result.text,
            source=_bill_source_from_attachment(attachment.source),
        )
    )
    saved_candidate = bill_candidate_store.save(candidate)
    if not privacy_settings.keep_ocr_text:
        attachment_store.clear_ocr_text(attachment_id)

    audit_log_store.record(
        action="attachment_recognized_and_bill_candidate_created",
        entity_type="bill_candidate",
        entity_id=saved_candidate.candidate_id,
        request=request,
        metadata={"attachment_id": attachment_id, "source": attachment.source},
    )
    return AttachmentBillParseResponse(
        attachment_id=attachment_id,
        status=AttachmentBillParseStatus.candidate_created,
        ocr=ocr_result,
        candidate=saved_candidate,
        warnings=saved_candidate.warnings,
        manual_entry_required=False,
    )


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(attachment_id: UUID, request: Request) -> None:
    deleted = attachment_store.delete(attachment_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )
    audit_log_store.record(
        action="attachment_deleted",
        entity_type="attachment",
        entity_id=attachment_id,
        request=request,
    )


def _bill_source_from_attachment(source: AttachmentSource) -> BillSource:
    if source == AttachmentSource.screenshot:
        return BillSource.screenshot
    if source == AttachmentSource.album:
        return BillSource.album
    return BillSource.upload
