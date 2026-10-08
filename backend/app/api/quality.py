from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from uuid import UUID

from app.schemas.quality import (
    AgentQualityEvaluationRun,
    AgentQualityFeedbackCreate,
    AgentQualityFeedbackListResponse,
    AgentQualityFeedbackRead,
    AgentQualityFeedbackReviewRequest,
    AgentQualitySummary,
)
from app.services.admin_auth_service import admin_auth_service
from app.services.agent_quality_service import agent_quality_service
from app.services.audit_log_store import audit_log_store


router = APIRouter(prefix="/quality", tags=["quality"])


def require_quality_admin_session(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    if not admin_auth_service.validate_bearer(authorization):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator session required",
        )


@router.get("/summary", response_model=AgentQualitySummary)
def get_quality_summary() -> AgentQualitySummary:
    return agent_quality_service.summary()


@router.post("/feedback", response_model=AgentQualityFeedbackRead, status_code=status.HTTP_201_CREATED)
def create_quality_feedback(
    payload: AgentQualityFeedbackCreate,
    request: Request,
) -> AgentQualityFeedbackRead:
    feedback = agent_quality_service.record_feedback(payload)
    audit_log_store.record(
        action="agent_quality_feedback_recorded",
        entity_type="agent_quality_feedback",
        entity_id=feedback.feedback_id,
        request=request,
        metadata={
            "message_id": str(feedback.message_id),
            "verdict": feedback.verdict,
            "has_expected_intent": bool(feedback.expected_intent),
            "has_expected_category": bool(feedback.expected_category),
        },
    )
    return feedback


@router.get("/feedback", response_model=AgentQualityFeedbackListResponse)
def list_quality_feedback(
    _: None = Depends(require_quality_admin_session),
) -> AgentQualityFeedbackListResponse:
    items = [
        AgentQualityFeedbackRead.model_validate(item)
        for item in agent_quality_service.list_feedback(limit=100)
    ]
    return AgentQualityFeedbackListResponse(
        generated_at=agent_quality_service.now(),
        total=len(items),
        items=items,
    )


@router.post("/feedback/{feedback_id}/review", response_model=AgentQualityFeedbackRead)
def review_quality_feedback(
    feedback_id: UUID,
    payload: AgentQualityFeedbackReviewRequest,
    request: Request,
    _: None = Depends(require_quality_admin_session),
) -> AgentQualityFeedbackRead:
    try:
        feedback = agent_quality_service.review_feedback(feedback_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    audit_log_store.record(
        action="agent_quality_feedback_reviewed",
        entity_type="agent_quality_feedback",
        entity_id=feedback.feedback_id,
        request=request,
        metadata={
            "disposition": payload.disposition,
            "review_status": feedback.review_status,
            "promoted_case_id": feedback.promoted_case_id,
        },
    )
    return feedback


@router.post("/evaluations/run", response_model=AgentQualityEvaluationRun)
def run_quality_evaluation(
    request: Request,
    _: None = Depends(require_quality_admin_session),
) -> AgentQualityEvaluationRun:
    run = agent_quality_service.run_evaluation()
    audit_log_store.record(
        action="agent_quality_evaluation_run",
        entity_type="agent_quality_evaluation",
        entity_id=run.run_id,
        request=request,
        metadata={
            "total_cases": run.total_cases,
            "passed_cases": run.passed_cases,
            "pass_rate": run.pass_rate,
            "model_strategy": run.model_strategy,
            "dataset_version": run.dataset_version,
            "execution_mode": run.execution_mode,
            "admitted": run.admission.admitted,
            "failed_critical_case_ids": run.admission.failed_critical_case_ids,
        },
    )
    return run
