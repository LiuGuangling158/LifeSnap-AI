from datetime import datetime, timezone

from app.schemas.attachment import RetentionPolicy
from app.schemas.settings import PrivacySettings, PrivacySettingsUpdate


class InMemorySettingsStore:
    def __init__(self) -> None:
        self._privacy_settings = self._default_privacy_settings()

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
        return self._privacy_settings

    def reset_privacy_settings(self) -> PrivacySettings:
        self._privacy_settings = self._default_privacy_settings()
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


settings_store = InMemorySettingsStore()
