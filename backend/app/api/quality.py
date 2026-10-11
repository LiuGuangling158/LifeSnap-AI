from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from uuid import UUID

from app.schemas.quality import (
    AgentQualityEvaluationRun,
    AgentQualityFeedbackCreate,
    AgentQualityFeedbackListResponse,
    AgentQualityFeedbackRead,
    AgentQualityFeedbackReviewRequest,
    AgentQualitySummary,
    AnnotationConsistencySummary,
    EvaluationComparisonReport,
    EvaluationComparisonRequest,
    EvaluationDatasetApprovalRequest,
    EvaluationDatasetSnapshot,
    EvaluationDatasetSnapshotCreate,
    OnlineEvaluationAnnotation,
    OnlineEvaluationAnnotationCreate,
    OnlineEvaluationSample,
    OnlineEvaluationSampleCollection,
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


@router.get("/datasets", response_model=list[EvaluationDatasetSnapshot])
def list_quality_datasets(
    limit: int = Query(default=50, ge=1, le=100),
    _: None = Depends(require_quality_admin_session),
) -> list[EvaluationDatasetSnapshot]:
    return agent_quality_service.list_dataset_snapshots(limit=limit)


@router.post("/datasets/snapshots", response_model=EvaluationDatasetSnapshot, status_code=status.HTTP_201_CREATED)
def create_quality_dataset_snapshot(
    payload: EvaluationDatasetSnapshotCreate,
    request: Request,
    _: None = Depends(require_quality_admin_session),
) -> EvaluationDatasetSnapshot:
    snapshot = agent_quality_service.create_dataset_snapshot(approval_note=payload.approval_note)
    audit_log_store.record(
        action="evaluation_dataset_snapshot_created",
        entity_type="evaluation_dataset_snapshot",
        entity_id=snapshot.snapshot_id,
        request=request,
        metadata={"dataset_id": snapshot.dataset_id, "source_version": snapshot.source_version},
    )
    return snapshot


@router.post("/datasets/{snapshot_id}/approve", response_model=EvaluationDatasetSnapshot)
def approve_quality_dataset_snapshot(
    snapshot_id: UUID,
    payload: EvaluationDatasetApprovalRequest,
    request: Request,
    _: None = Depends(require_quality_admin_session),
) -> EvaluationDatasetSnapshot:
    try:
        snapshot = agent_quality_service.approve_dataset_snapshot(
            snapshot_id,
            approval_note=payload.approval_note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit_log_store.record(
        action="evaluation_dataset_snapshot_approved",
        entity_type="evaluation_dataset_snapshot",
        entity_id=snapshot.snapshot_id,
        request=request,
        metadata={"dataset_id": snapshot.dataset_id, "source_version": snapshot.source_version},
    )
    return snapshot


@router.get("/online-samples", response_model=list[OnlineEvaluationSample])
def list_online_evaluation_samples(
    limit: int = Query(default=100, ge=1, le=200),
    _: None = Depends(require_quality_admin_session),
) -> list[OnlineEvaluationSample]:
    return agent_quality_service.list_online_samples(limit=limit)


@router.post("/online-samples/collect", response_model=list[OnlineEvaluationSample], status_code=status.HTTP_201_CREATED)
def collect_online_evaluation_samples(
    payload: OnlineEvaluationSampleCollection,
    request: Request,
    _: None = Depends(require_quality_admin_session),
) -> list[OnlineEvaluationSample]:
    samples = agent_quality_service.collect_online_samples(requested_count=payload.requested_count)
    audit_log_store.record(
        action="online_evaluation_samples_collected",
        entity_type="online_evaluation_sample_batch",
        entity_id="latest",
        request=request,
        metadata={"requested_count": payload.requested_count, "created_count": len(samples)},
    )
    return samples


@router.post("/online-samples/{sample_id}/annotations", response_model=OnlineEvaluationAnnotation)
def annotate_online_evaluation_sample(
    sample_id: UUID,
    payload: OnlineEvaluationAnnotationCreate,
    request: Request,
    _: None = Depends(require_quality_admin_session),
) -> OnlineEvaluationAnnotation:
    try:
        annotation = agent_quality_service.annotate_online_sample(sample_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    audit_log_store.record(
        action="online_evaluation_sample_annotated",
        entity_type="online_evaluation_sample",
        entity_id=sample_id,
        request=request,
        metadata={"annotator_id": annotation.annotator_id, "verdict": annotation.verdict},
    )
    return annotation


@router.get("/online-samples/consistency", response_model=AnnotationConsistencySummary)
def get_online_evaluation_annotation_consistency(
    _: None = Depends(require_quality_admin_session),
) -> AnnotationConsistencySummary:
    return agent_quality_service.annotation_consistency()


@router.post("/comparisons", response_model=EvaluationComparisonReport)
def compare_quality_evaluations(
    payload: EvaluationComparisonRequest,
    request: Request,
    _: None = Depends(require_quality_admin_session),
) -> EvaluationComparisonReport:
    try:
        report = agent_quality_service.compare_evaluations(
            payload.baseline_run_id,
            payload.candidate_run_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    audit_log_store.record(
        action="agent_quality_evaluations_compared",
        entity_type="agent_quality_evaluation_comparison",
        entity_id=payload.candidate_run_id,
        request=request,
        metadata={"baseline_run_id": str(payload.baseline_run_id), "candidate_run_id": str(payload.candidate_run_id)},
    )
    return report


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
