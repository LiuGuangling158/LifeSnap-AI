from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.schemas.agent import ParseBillRequest, ParseBillResponse
from app.schemas.attachment import AttachmentOcrTextUpdate, AttachmentRead, AttachmentSource
from app.schemas.bill import BillSource
from app.services.bill_candidate_store import bill_candidate_store
from app.services.bill_parser import bill_parser
from app.services.attachment_store import (
    AttachmentTooLargeError,
    UnsupportedAttachmentTypeError,
    attachment_store,
)

router = APIRouter(prefix="/attachments", tags=["attachments"])


@router.post("/upload", response_model=AttachmentRead, status_code=status.HTTP_201_CREATED)
async def upload_attachment(
    file: UploadFile = File(...),
    source: AttachmentSource = Form(default=AttachmentSource.upload),
    save_original: bool = Form(default=False),
) -> AttachmentRead:
    content = await file.read()
    try:
        return attachment_store.create(
            filename=file.filename or "attachment",
            content_type=file.content_type or "application/octet-stream",
            content=content,
            source=source,
            save_original=save_original,
        )
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


@router.patch("/{attachment_id}/ocr-text", response_model=AttachmentRead)
def update_attachment_ocr_text(
    attachment_id: UUID,
    payload: AttachmentOcrTextUpdate,
) -> AttachmentRead:
    attachment = attachment_store.update_ocr_text(attachment_id, payload.ocr_text)
    if attachment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )
    return attachment


@router.post("/{attachment_id}/parse-bill", response_model=ParseBillResponse)
def parse_attachment_bill(attachment_id: UUID) -> ParseBillResponse:
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
    return bill_candidate_store.save(candidate)


@router.delete("/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attachment(attachment_id: UUID) -> None:
    deleted = attachment_store.delete(attachment_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Attachment not found",
        )


def _bill_source_from_attachment(source: AttachmentSource) -> BillSource:
    if source == AttachmentSource.screenshot:
        return BillSource.screenshot
    if source == AttachmentSource.album:
        return BillSource.album
    return BillSource.upload
