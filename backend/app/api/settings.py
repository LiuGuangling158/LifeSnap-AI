from fastapi import APIRouter, Request

from app.schemas.settings import (
    BudgetSettings,
    BudgetSettingsUpdate,
    CategorySettings,
    CategorySettingsUpdate,
    PrivacySettings,
    PrivacySettingsUpdate,
    TagSettings,
    TagSettingsUpdate,
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


@router.get("/budget", response_model=BudgetSettings)
def get_budget_settings() -> BudgetSettings:
    return settings_store.get_budget_settings()


@router.patch("/budget", response_model=BudgetSettings)
def update_budget_settings(
    payload: BudgetSettingsUpdate,
    request: Request,
) -> BudgetSettings:
    settings = settings_store.update_budget_settings(payload)
    audit_log_store.record(
        action="budget_settings_updated",
        entity_type="settings",
        request=request,
        metadata={
            "updated_fields": list(payload.model_dump(exclude_none=True, exclude_unset=True)),
            "monthly_budget": str(settings.monthly_budget),
            "warning_threshold_percent": settings.warning_threshold_percent,
        },
    )
    return settings


@router.get("/tags", response_model=TagSettings)
def get_tag_settings() -> TagSettings:
    return settings_store.get_tag_settings()


@router.patch("/tags", response_model=TagSettings)
def update_tag_settings(
    payload: TagSettingsUpdate,
    request: Request,
) -> TagSettings:
    settings = settings_store.update_tag_settings(payload)
    audit_log_store.record(
        action="tag_settings_updated",
        entity_type="settings",
        request=request,
        metadata={
            "updated_fields": list(payload.model_dump(exclude_none=True, exclude_unset=True)),
            "tag_count": len(settings.tags),
        },
    )
    return settings
