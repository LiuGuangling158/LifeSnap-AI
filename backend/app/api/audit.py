from fastapi import APIRouter, Query

from app.schemas.audit import AuditEventListResponse
from app.services.audit_log_store import audit_log_store

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/events", response_model=AuditEventListResponse)
def list_audit_events(
    action: str | None = Query(default=None, min_length=1, max_length=80),
    entity_type: str | None = Query(default=None, min_length=1, max_length=80),
    request_id: str | None = Query(default=None, min_length=1, max_length=128),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> AuditEventListResponse:
    return audit_log_store.list(
        action=action,
        entity_type=entity_type,
        request_id=request_id,
        page=page,
        page_size=page_size,
    )
