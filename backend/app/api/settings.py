from fastapi import APIRouter, Request

from app.schemas.settings import (
    CategorySettings,
    CategorySettingsUpdate,
    PrivacySettings,
    PrivacySettingsUpdate,
)
from app.services.audit_log_store import audit_log_store
from app.services.settings_store import settings_store

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/privacy", response_model=PrivacySettings)
def get_privacy_settings() -> PrivacySettings:
    return settings_store.get_privacy_settings()


@router.patch("/privacy", response_model=PrivacySettings)
def update_privacy_settings(
    payload: PrivacySettingsUpdate,
    request: Request,
) -> PrivacySettings:
    settings = settings_store.update_privacy_settings(payload)
    audit_log_store.record(
        action="privacy_settings_updated",
        entity_type="settings",
        request=request,
        metadata={"updated_fields": payload.model_dump(exclude_none=True, exclude_unset=True)},
    )
    return settings


@router.get("/categories", response_model=CategorySettings)
def get_category_settings() -> CategorySettings:
    return settings_store.get_category_settings()


@router.patch("/categories", response_model=CategorySettings)
def update_category_settings(
    payload: CategorySettingsUpdate,
    request: Request,
) -> CategorySettings:
    settings = settings_store.update_category_settings(payload)
    audit_log_store.record(
        action="category_settings_updated",
        entity_type="settings",
        request=request,
        metadata={
            "updated_fields": list(payload.model_dump(exclude_none=True, exclude_unset=True)),
            "bill_category_count": len(settings.bill_categories),
            "task_category_count": len(settings.task_categories),
        },
    )
    return settings
