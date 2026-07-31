from fastapi import APIRouter

from app.schemas.settings import PrivacySettings, PrivacySettingsUpdate
from app.services.settings_store import settings_store

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/privacy", response_model=PrivacySettings)
def get_privacy_settings() -> PrivacySettings:
    return settings_store.get_privacy_settings()


@router.patch("/privacy", response_model=PrivacySettings)
def update_privacy_settings(payload: PrivacySettingsUpdate) -> PrivacySettings:
    return settings_store.update_privacy_settings(payload)
