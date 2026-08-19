from __future__ import annotations

import json
from datetime import datetime, timezone
from hashlib import sha256
from uuid import UUID, uuid4

from app.core.config import settings
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


class LocalAttachmentStore:
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
        self._load()

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
            storage_type="local_file" if save_original else "local_json",
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
            self._persist_original_file(attachment_id, content)
        self._persist()
        return attachment

    def get(self, attachment_id: UUID) -> AttachmentRead | None:
        return self._attachments.get(attachment_id)

    def original_content(self, attachment_id: UUID) -> tuple[AttachmentRead, bytes] | None:
        attachment = self.get(attachment_id)
        if attachment is None or not attachment.original_saved:
            return None

        content = self._original_files.get(attachment_id)
        if content is not None:
            return attachment, content

        original_file = self._original_file_path(attachment_id)
        if not original_file.exists():
            return None
        try:
            content = original_file.read_bytes()
        except OSError:
            return None

        self._original_files[attachment_id] = content
        return attachment, content

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
        self._persist()
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
        self._persist()
        return updated

    def delete(self, attachment_id: UUID) -> bool:
        if attachment_id not in self._attachments:
            return False

        del self._attachments[attachment_id]
        self._original_files.pop(attachment_id, None)
        self._delete_original_file(attachment_id)
        self._persist()
        return True

    def clear(self) -> int:
        count = len(self._attachments)
        self._attachments.clear()
        self._original_files.clear()
        self._clear_original_files()
        self._persist()
        return count

    def upsert_many(self, attachments: list[AttachmentRead]) -> int:
        for attachment in attachments:
            self._attachments[attachment.id] = self._normalized_import_attachment(attachment)
            if not self._attachments[attachment.id].original_saved:
                self._original_files.pop(attachment.id, None)
                self._delete_original_file(attachment.id)
        self._persist()
        return len(attachments)

    def _find_by_checksum(self, checksum: str) -> list[AttachmentRead]:
        matches = [
            attachment
            for attachment in self._attachments.values()
            if attachment.checksum == checksum
        ]
        return sorted(matches, key=lambda attachment: attachment.created_at)

    def _load(self) -> None:
        path = settings.local_attachment_path
        if not path.exists():
            return
        try:
            raw_items = json.loads(path.read_text(encoding="utf-8"))
            attachments = [AttachmentRead.model_validate(item) for item in raw_items]
        except (OSError, ValueError, TypeError):
            return

        self._attachments = {attachment.id: attachment for attachment in attachments}
        self._original_files = {}
        for attachment in attachments:
            if attachment.original_saved:
                original_file = self._original_file_path(attachment.id)
                if original_file.exists():
                    try:
                        self._original_files[attachment.id] = original_file.read_bytes()
                    except OSError:
                        continue

    def _persist(self) -> None:
        path = settings.local_attachment_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(
                [
                    attachment.model_dump(mode="json")
                    for attachment in sorted(
                        self._attachments.values(),
                        key=lambda item: item.created_at,
                        reverse=True,
                    )
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temp_path.replace(path)

    def _normalized_import_attachment(self, attachment: AttachmentRead) -> AttachmentRead:
        original_file = self._original_file_path(attachment.id)
        original_saved = attachment.original_saved and original_file.exists()
        data = attachment.model_dump()
        data["original_saved"] = original_saved
        data["storage_type"] = "local_file" if original_saved else "local_json"
        data["updated_at"] = datetime.now(timezone.utc)
        return AttachmentRead(**data)

    def _persist_original_file(self, attachment_id: UUID, content: bytes) -> None:
        directory = settings.local_attachment_file_dir
        directory.mkdir(parents=True, exist_ok=True)
        self._original_file_path(attachment_id).write_bytes(content)

    def _delete_original_file(self, attachment_id: UUID) -> None:
        path = self._original_file_path(attachment_id)
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass

    def _clear_original_files(self) -> None:
        directory = settings.local_attachment_file_dir
        if not directory.exists():
            return
        for path in directory.iterdir():
            if path.is_file():
                try:
                    path.unlink()
                except OSError:
                    continue

    def _original_file_path(self, attachment_id: UUID):
        return settings.local_attachment_file_dir / f"{attachment_id}.bin"

attachment_store = LocalAttachmentStore()
