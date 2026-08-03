from fastapi import APIRouter, Request

from app.schemas.settings import PrivacySettings, PrivacySettingsUpdate
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
