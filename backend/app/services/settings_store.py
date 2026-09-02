from __future__ import annotations

import json
from datetime import datetime, timezone

from app.core.config import settings
from app.schemas.attachment import RetentionPolicy
from app.schemas.settings import (
    BudgetSettings,
    BudgetSettingsUpdate,
    CategorySettings,
    CategorySettingsUpdate,
    DEFAULT_BILL_CATEGORIES,
    DEFAULT_TAGS,
    DEFAULT_TASK_CATEGORIES,
    PrivacySettings,
    PrivacySettingsUpdate,
    TagSettings,
    TagSettingsUpdate,
)


class LocalSettingsStore:
    def __init__(self) -> None:
        self._privacy_settings = self._load_privacy_settings()
        self._category_settings = self._load_category_settings()
        self._budget_settings = self._load_budget_settings()
        self._tag_settings = self._load_tag_settings()

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
            data["bill_categories"] = self._normalize_labels(
                incoming["bill_categories"],
                DEFAULT_BILL_CATEGORIES,
            )
        if "task_categories" in incoming:
            data["task_categories"] = self._normalize_labels(
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
            bill_categories=self._normalize_labels(
                payload.bill_categories,
                DEFAULT_BILL_CATEGORIES,
            ),
            task_categories=self._normalize_labels(
                payload.task_categories,
                DEFAULT_TASK_CATEGORIES,
            ),
            updated_at=payload.updated_at or datetime.now(timezone.utc),
        )
        self._persist_category_settings()
        return self._category_settings

    def get_budget_settings(self) -> BudgetSettings:
        return self._budget_settings

    def update_budget_settings(
        self,
        payload: BudgetSettingsUpdate,
    ) -> BudgetSettings:
        data = self._budget_settings.model_dump()
        incoming = payload.model_dump(exclude_none=True, exclude_unset=True)
        data.update(incoming)
        data["currency"] = "CNY"
        data["updated_at"] = datetime.now(timezone.utc)
        self._budget_settings = BudgetSettings(**data)
        self._persist_budget_settings()
        return self._budget_settings

    def reset_budget_settings(self) -> BudgetSettings:
        self._budget_settings = self._default_budget_settings()
        self._persist_budget_settings()
        return self._budget_settings

    def replace_budget_settings(self, payload: BudgetSettings) -> BudgetSettings:
        self._budget_settings = BudgetSettings(
            monthly_budget=payload.monthly_budget,
            currency="CNY",
            warning_threshold_percent=payload.warning_threshold_percent,
            updated_at=payload.updated_at or datetime.now(timezone.utc),
        )
        self._persist_budget_settings()
        return self._budget_settings

    def get_tag_settings(self) -> TagSettings:
        return self._tag_settings

    def update_tag_settings(
        self,
        payload: TagSettingsUpdate,
    ) -> TagSettings:
        data = self._tag_settings.model_dump()
        incoming = payload.model_dump(exclude_none=True, exclude_unset=True)
        if "tags" in incoming:
            data["tags"] = self._normalize_labels(incoming["tags"], DEFAULT_TAGS)
        data["updated_at"] = datetime.now(timezone.utc)
        self._tag_settings = TagSettings(**data)
        self._persist_tag_settings()
        return self._tag_settings

    def reset_tag_settings(self) -> TagSettings:
        self._tag_settings = self._default_tag_settings()
        self._persist_tag_settings()
        return self._tag_settings

    def replace_tag_settings(self, payload: TagSettings) -> TagSettings:
        self._tag_settings = TagSettings(
            tags=self._normalize_labels(payload.tags, DEFAULT_TAGS),
            updated_at=payload.updated_at or datetime.now(timezone.utc),
        )
        self._persist_tag_settings()
        return self._tag_settings

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

    def _default_budget_settings(self) -> BudgetSettings:
        return BudgetSettings(updated_at=datetime.now(timezone.utc))

    def _default_tag_settings(self) -> TagSettings:
        return TagSettings(
            tags=DEFAULT_TAGS.copy(),
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
                bill_categories=self._normalize_labels(
                    loaded.bill_categories,
                    DEFAULT_BILL_CATEGORIES,
                ),
                task_categories=self._normalize_labels(
                    loaded.task_categories,
                    DEFAULT_TASK_CATEGORIES,
                ),
                updated_at=loaded.updated_at,
            )
        except (OSError, ValueError, TypeError):
            return self._default_category_settings()

    def _load_budget_settings(self) -> BudgetSettings:
        path = settings.local_budget_settings_path
        if not path.exists():
            return self._default_budget_settings()
        try:
            raw_settings = json.loads(path.read_text(encoding="utf-8"))
            loaded = BudgetSettings.model_validate(raw_settings)
            return BudgetSettings(
                monthly_budget=loaded.monthly_budget,
                currency="CNY",
                warning_threshold_percent=loaded.warning_threshold_percent,
                updated_at=loaded.updated_at,
            )
        except (OSError, ValueError, TypeError):
            return self._default_budget_settings()

    def _load_tag_settings(self) -> TagSettings:
        path = settings.local_tag_settings_path
        if not path.exists():
            return self._default_tag_settings()
        try:
            raw_settings = json.loads(path.read_text(encoding="utf-8"))
            loaded = TagSettings.model_validate(raw_settings)
            return TagSettings(
                tags=self._normalize_labels(loaded.tags, DEFAULT_TAGS),
                updated_at=loaded.updated_at,
            )
        except (OSError, ValueError, TypeError):
            return self._default_tag_settings()

    def _persist_category_settings(self) -> None:
        path = settings.local_category_settings_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(
            self._category_settings.model_dump_json(indent=2),
            encoding="utf-8",
        )
        temp_path.replace(path)

    def _persist_budget_settings(self) -> None:
        path = settings.local_budget_settings_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(
            self._budget_settings.model_dump_json(indent=2),
            encoding="utf-8",
        )
        temp_path.replace(path)

    def _persist_tag_settings(self) -> None:
        path = settings.local_tag_settings_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(
            self._tag_settings.model_dump_json(indent=2),
            encoding="utf-8",
        )
        temp_path.replace(path)

    def _normalize_labels(
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
