from fastapi import APIRouter, Depends, Header, HTTPException, Request, status

from app.schemas.async_job import AsyncJobRead, AsyncJobType
from app.services.admin_auth_service import admin_auth_service
from app.services.async_job_service import async_job_service
from app.services.audit_log_store import audit_log_store


router = APIRouter(prefix="/jobs", tags=["asynchronous jobs"])


def require_job_admin_session(
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> None:
    if not admin_auth_service.validate_bearer(authorization):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator session required",
        )


@router.get("", response_model=list[AsyncJobRead])
def list_async_jobs(
    _: None = Depends(require_job_admin_session),
) -> list[AsyncJobRead]:
    return async_job_service.list_recent()


@router.post(
    "/agent-quality-evaluation",
    response_model=AsyncJobRead,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_agent_quality_evaluation(
    request: Request,
    _: None = Depends(require_job_admin_session),
) -> AsyncJobRead:
    return _enqueue(AsyncJobType.agent_quality_evaluation, request)


@router.post("/rag-reindex", response_model=AsyncJobRead, status_code=status.HTTP_202_ACCEPTED)
def enqueue_rag_reindex(
    request: Request,
    _: None = Depends(require_job_admin_session),
) -> AsyncJobRead:
    return _enqueue(AsyncJobType.rag_reindex, request)


@router.get("/{job_id}", response_model=AsyncJobRead)
def get_async_job(
    job_id: str,
    _: None = Depends(require_job_admin_session),
) -> AsyncJobRead:
    job = async_job_service.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return job


@router.post("/{job_id}/retry", response_model=AsyncJobRead, status_code=status.HTTP_202_ACCEPTED)
def retry_async_job(
    job_id: str,
    request: Request,
    _: None = Depends(require_job_admin_session),
) -> AsyncJobRead:
    job = async_job_service.retry(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Job cannot be retried",
        )
    audit_log_store.record(
        action="async_job_retried",
        entity_type="async_job",
        entity_id=job.job_id,
        request=request,
        metadata={"job_type": job.job_type, "attempt": job.attempt},
    )
    return job


@router.post("/{job_id}/cancel", response_model=AsyncJobRead)
def cancel_async_job(
    job_id: str,
    request: Request,
    _: None = Depends(require_job_admin_session),
) -> AsyncJobRead:
    job = async_job_service.cancel(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only queued jobs can be cancelled",
        )
    audit_log_store.record(
        action="async_job_cancelled",
        entity_type="async_job",
        entity_id=job.job_id,
        request=request,
        metadata={"job_type": job.job_type},
    )
    return job


def _enqueue(job_type: AsyncJobType, request: Request) -> AsyncJobRead:
    job = async_job_service.enqueue(job_type)
    audit_log_store.record(
        action="async_job_enqueued",
        entity_type="async_job",
        entity_id=job.job_id,
        request=request,
        metadata={"job_type": job.job_type, "max_attempts": job.max_attempts},
    )
    return job
