from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID, uuid4

from app.schemas.attachment import (
    AttachmentDuplicateResponse,
    AttachmentRead,
    AttachmentSource,
    RetentionPolicy,
)


class AttachmentTooLargeError(ValueError):
    pass


class UnsupportedAttachmentTypeError(ValueError):
    pass


class InMemoryAttachmentStore:
    max_file_size = 10 * 1024 * 1024
    supported_content_types = {
        "image/jpeg",
        "image/png",
        "image/webp",
        "application/pdf",
    }

    def __init__(self) -> None:
        self._attachments: dict[UUID, AttachmentRead] = {}
        self._original_files: dict[UUID, bytes] = {}

    def create(
        self,
        filename: str,
        content_type: str,
        content: bytes,
        source: AttachmentSource,
        save_original: bool,
    ) -> AttachmentRead:
        if len(content) > self.max_file_size:
            raise AttachmentTooLargeError("Attachment exceeds 10MB limit")
        if content_type not in self.supported_content_types:
            raise UnsupportedAttachmentTypeError("Unsupported attachment content type")

        now = datetime.now(timezone.utc)
        attachment_id = uuid4()
        checksum = sha256(content).hexdigest()
        duplicate_matches = self._find_by_checksum(checksum)
        attachment = AttachmentRead(
            id=attachment_id,
            filename=filename,
            content_type=content_type,
            file_size=len(content),
            checksum=checksum,
            duplicate_of=duplicate_matches[0].id if duplicate_matches else None,
            source=source,
            retention_policy=(
                RetentionPolicy.keep_until_user_delete
                if save_original
                else RetentionPolicy.delete_after_recognition
            ),
            original_saved=save_original,
            created_at=now,
            updated_at=now,
        )

        self._attachments[attachment_id] = attachment
        if save_original:
            self._original_files[attachment_id] = content
        return attachment

    def get(self, attachment_id: UUID) -> AttachmentRead | None:
        return self._attachments.get(attachment_id)

    def all(self) -> list[AttachmentRead]:
        return list(self._attachments.values())

    def duplicates_for(self, attachment_id: UUID) -> AttachmentDuplicateResponse | None:
        attachment = self.get(attachment_id)
        if attachment is None:
            return None

        matches = [
            match
            for match in self._find_by_checksum(attachment.checksum)
            if match.id != attachment_id
        ]
        duplicate_of = attachment.duplicate_of or (matches[0].id if matches else None)
        return AttachmentDuplicateResponse(
            attachment_id=attachment.id,
            checksum=attachment.checksum,
            is_duplicate=bool(matches),
            duplicate_of=duplicate_of,
            duplicate_count=len(matches),
            matches=matches,
        )

    def update_ocr_text(self, attachment_id: UUID, ocr_text: str) -> AttachmentRead | None:
        attachment = self.get(attachment_id)
        if attachment is None:
            return None

        data = attachment.model_dump()
        data["ocr_text"] = ocr_text
        data["updated_at"] = datetime.now(timezone.utc)
        updated = AttachmentRead(**data)
        self._attachments[attachment_id] = updated
        return updated

    def clear_ocr_text(self, attachment_id: UUID) -> AttachmentRead | None:
        attachment = self.get(attachment_id)
        if attachment is None:
            return None

        data = attachment.model_dump()
        data["ocr_text"] = None
        data["updated_at"] = datetime.now(timezone.utc)
        updated = AttachmentRead(**data)
        self._attachments[attachment_id] = updated
        return updated

    def delete(self, attachment_id: UUID) -> bool:
        if attachment_id not in self._attachments:
            return False

        del self._attachments[attachment_id]
        self._original_files.pop(attachment_id, None)
        return True

    def clear(self) -> int:
        count = len(self._attachments)
        self._attachments.clear()
        self._original_files.clear()
        return count

    def _find_by_checksum(self, checksum: str) -> list[AttachmentRead]:
        matches = [
            attachment
            for attachment in self._attachments.values()
            if attachment.checksum == checksum
        ]
        return sorted(matches, key=lambda attachment: attachment.created_at)


attachment_store = InMemoryAttachmentStore()
