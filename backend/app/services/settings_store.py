from __future__ import annotations

import json
from datetime import datetime, timezone

from app.core.config import settings
from app.schemas.attachment import RetentionPolicy
from app.schemas.settings import PrivacySettings, PrivacySettingsUpdate


class LocalSettingsStore:
    def __init__(self) -> None:
        self._privacy_settings = self._load_privacy_settings()

    def get_privacy_settings(self) -> PrivacySettings:
        return self._privacy_settings

    def update_privacy_settings(
        self,
        payload: PrivacySettingsUpdate,
    ) -> PrivacySettings:
        data = self._privacy_settings.model_dump()
        data.update(payload.model_dump(exclude_none=True, exclude_unset=True))
        data["attachment_retention_policy"] = (
            RetentionPolicy.keep_until_user_delete
            if data["save_original_attachments_by_default"]
            else RetentionPolicy.delete_after_recognition
        )
        data["updated_at"] = datetime.now(timezone.utc)
        self._privacy_settings = PrivacySettings(**data)
        self._persist()
        return self._privacy_settings

    def reset_privacy_settings(self) -> PrivacySettings:
        self._privacy_settings = self._default_privacy_settings()
        self._persist()
        return self._privacy_settings

    def replace_privacy_settings(self, payload: PrivacySettings) -> PrivacySettings:
        self._privacy_settings = payload
        self._persist()
        return self._privacy_settings

    def _default_privacy_settings(self) -> PrivacySettings:
        return PrivacySettings(
            local_only_mode=True,
            allow_ai_text_processing=True,
            save_original_attachments_by_default=False,
            attachment_retention_policy=RetentionPolicy.delete_after_recognition,
            keep_ocr_text=True,
            updated_at=datetime.now(timezone.utc),
        )

    def _load_privacy_settings(self) -> PrivacySettings:
        path = settings.local_settings_path
        if not path.exists():
            return self._default_privacy_settings()
        try:
            raw_settings = json.loads(path.read_text(encoding="utf-8"))
            return PrivacySettings.model_validate(raw_settings)
        except (OSError, ValueError, TypeError):
            return self._default_privacy_settings()

    def _persist(self) -> None:
        path = settings.local_settings_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(
            self._privacy_settings.model_dump_json(indent=2),
            encoding="utf-8",
        )
        temp_path.replace(path)


settings_store = LocalSettingsStore()
