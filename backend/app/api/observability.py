from fastapi import APIRouter, Depends, Query, Response

from app.schemas.auth import AuthUser
from app.schemas.observability import (
    AgentExecutionTraceListResponse,
    MonitoringSummary,
)
from app.services.auth_service import require_current_user
from app.services.observability_service import observability_service


router = APIRouter(prefix="/observability", tags=["observability"])
metrics_router = APIRouter(tags=["observability"])


@router.get("/summary", response_model=MonitoringSummary)
def get_monitoring_summary(
    user: AuthUser = Depends(require_current_user),
) -> MonitoringSummary:
    return observability_service.summary(owner_id=user.user_id)


@router.get("/agent-traces", response_model=AgentExecutionTraceListResponse)
def list_agent_traces(
    limit: int = Query(default=20, ge=1, le=200),
    user: AuthUser = Depends(require_current_user),
) -> AgentExecutionTraceListResponse:
    return observability_service.list_agent_traces(owner_id=user.user_id, limit=limit)


@metrics_router.get("/metrics", include_in_schema=False)
def get_prometheus_metrics() -> Response:
    return Response(
        content=observability_service.prometheus_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
