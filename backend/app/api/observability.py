from fastapi import APIRouter, Query, Response

from app.core.user_context import current_owner_id
from app.schemas.observability import (
    AgentExecutionTraceListResponse,
    MonitoringSummary,
)
from app.services.observability_service import observability_service


router = APIRouter(prefix="/observability", tags=["observability"])
metrics_router = APIRouter(tags=["observability"])


@router.get("/summary", response_model=MonitoringSummary)
def get_monitoring_summary(
) -> MonitoringSummary:
    return observability_service.summary(owner_id=current_owner_id())


@router.get("/agent-traces", response_model=AgentExecutionTraceListResponse)
def list_agent_traces(
    limit: int = Query(default=20, ge=1, le=200),
) -> AgentExecutionTraceListResponse:
    return observability_service.list_agent_traces(owner_id=current_owner_id(), limit=limit)


@metrics_router.get("/metrics", include_in_schema=False)
def get_prometheus_metrics() -> Response:
    return Response(
        content=observability_service.prometheus_metrics(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
