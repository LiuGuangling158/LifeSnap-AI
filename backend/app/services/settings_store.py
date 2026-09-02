from __future__ import annotations

import json
from datetime import datetime, timezone

from app.core.config import settings
from app.schemas.attachment import RetentionPolicy
from app.schemas.settings import (
    CategorySettings,
    CategorySettingsUpdate,
    DEFAULT_BILL_CATEGORIES,
    DEFAULT_TASK_CATEGORIES,
    PrivacySettings,
    PrivacySettingsUpdate,
)


class LocalSettingsStore:
    def __init__(self) -> None:
        self._privacy_settings = self._load_privacy_settings()
        self._category_settings = self._load_category_settings()

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

    def get_category_settings(self) -> CategorySettings:
        return self._category_settings

    def update_category_settings(
        self,
        payload: CategorySettingsUpdate,
    ) -> CategorySettings:
        data = self._category_settings.model_dump()
        incoming = payload.model_dump(exclude_none=True, exclude_unset=True)
        if "bill_categories" in incoming:
            data["bill_categories"] = self._normalize_categories(
                incoming["bill_categories"],
                DEFAULT_BILL_CATEGORIES,
            )
        if "task_categories" in incoming:
            data["task_categories"] = self._normalize_categories(
                incoming["task_categories"],
                DEFAULT_TASK_CATEGORIES,
            )
        data["updated_at"] = datetime.now(timezone.utc)
        self._category_settings = CategorySettings(**data)
        self._persist_category_settings()
        return self._category_settings

    def reset_category_settings(self) -> CategorySettings:
        self._category_settings = self._default_category_settings()
        self._persist_category_settings()
        return self._category_settings

    def replace_category_settings(self, payload: CategorySettings) -> CategorySettings:
        self._category_settings = CategorySettings(
            bill_categories=self._normalize_categories(
                payload.bill_categories,
                DEFAULT_BILL_CATEGORIES,
            ),
            task_categories=self._normalize_categories(
                payload.task_categories,
                DEFAULT_TASK_CATEGORIES,
            ),
            updated_at=payload.updated_at or datetime.now(timezone.utc),
        )
        self._persist_category_settings()
        return self._category_settings

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

    def _default_category_settings(self) -> CategorySettings:
        return CategorySettings(
            bill_categories=DEFAULT_BILL_CATEGORIES.copy(),
            task_categories=DEFAULT_TASK_CATEGORIES.copy(),
            updated_at=datetime.now(timezone.utc),
        )

    def _load_category_settings(self) -> CategorySettings:
        path = settings.local_category_settings_path
        if not path.exists():
            return self._default_category_settings()
        try:
            raw_settings = json.loads(path.read_text(encoding="utf-8"))
            loaded = CategorySettings.model_validate(raw_settings)
            return CategorySettings(
                bill_categories=self._normalize_categories(
                    loaded.bill_categories,
                    DEFAULT_BILL_CATEGORIES,
                ),
                task_categories=self._normalize_categories(
                    loaded.task_categories,
                    DEFAULT_TASK_CATEGORIES,
                ),
                updated_at=loaded.updated_at,
            )
        except (OSError, ValueError, TypeError):
            return self._default_category_settings()

    def _persist_category_settings(self) -> None:
        path = settings.local_category_settings_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(
            self._category_settings.model_dump_json(indent=2),
            encoding="utf-8",
        )
        temp_path.replace(path)

    def _normalize_categories(
        self,
        values: list[str],
        fallback: list[str],
    ) -> list[str]:
        normalized: list[str] = []
        for value in values:
            text = str(value).strip()
            if not text or len(text) > 40 or text in normalized:
                continue
            normalized.append(text)
            if len(normalized) >= 30:
                break
        return normalized or fallback.copy()


settings_store = LocalSettingsStore()
