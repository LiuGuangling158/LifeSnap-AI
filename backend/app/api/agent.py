from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, Query, status

from app.schemas.bill import BillRead, DuplicateBillCheckResponse
from app.schemas.agent import (
    BillCandidateUpdate,
    BillCandidateListResponse,
    CandidateListResponse,
    ParseBillRequest,
    ParseBillResponse,
    ParseTaskRequest,
    ParseTaskResponse,
    TaskCandidateUpdate,
    TaskCandidateListResponse,
)
from app.schemas.task import TaskRead
from app.services.bill_candidate_store import bill_candidate_store
from app.services.bill_parser import bill_parser
from app.services.bill_store import bill_store
from app.services.idempotency_store import IdempotencyConflictError, idempotency_store
from app.services.settings_store import settings_store
from app.services.task_candidate_store import task_candidate_store
from app.services.task_parser import task_parser

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/parse-bill", response_model=ParseBillResponse)
def parse_bill(payload: ParseBillRequest) -> ParseBillResponse:
    if not settings_store.get_privacy_settings().allow_ai_text_processing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI text processing is disabled in privacy settings",
        )
    candidate = bill_parser.parse_bill(payload)
    return bill_candidate_store.save(candidate)


@router.get("/candidates", response_model=CandidateListResponse)
def list_candidates(
    confirmable_only: bool = Query(default=False),
) -> CandidateListResponse:
    bill_candidates = bill_candidate_store.all()
    task_candidates = task_candidate_store.all()
    if confirmable_only:
        bill_candidates = [
            candidate
            for candidate in bill_candidates
            if bill_candidate_store.is_confirmable(candidate)
        ]
        task_candidates = [
            candidate
            for candidate in task_candidates
            if task_candidate_store.is_confirmable(candidate)
        ]

    return CandidateListResponse(
        bill_candidates=bill_candidates,
        task_candidates=task_candidates,
        bill_candidate_count=len(bill_candidates),
        task_candidate_count=len(task_candidates),
        total=len(bill_candidates) + len(task_candidates),
    )


@router.get("/bill-candidates", response_model=BillCandidateListResponse)
def list_bill_candidates(
    confirmable_only: bool = Query(default=False),
) -> BillCandidateListResponse:
    candidates = bill_candidate_store.all()
    if confirmable_only:
        candidates = [
            candidate
            for candidate in candidates
            if bill_candidate_store.is_confirmable(candidate)
        ]
    return BillCandidateListResponse(items=candidates, total=len(candidates))


@router.get("/bill-candidates/{candidate_id}", response_model=ParseBillResponse)
def get_bill_candidate(candidate_id: UUID) -> ParseBillResponse:
    candidate = bill_candidate_store.get(candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill candidate not found",
        )
    return candidate


@router.patch("/bill-candidates/{candidate_id}", response_model=ParseBillResponse)
def update_bill_candidate(
    candidate_id: UUID,
    payload: BillCandidateUpdate,
) -> ParseBillResponse:
    candidate = bill_candidate_store.update(candidate_id, payload)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill candidate not found",
        )
    return candidate


@router.delete("/bill-candidates/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_bill_candidate(candidate_id: UUID) -> None:
    deleted = bill_candidate_store.delete(candidate_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill candidate not found",
        )


@router.post(
    "/bill-candidates/{candidate_id}/check-duplicate",
    response_model=DuplicateBillCheckResponse,
)
def check_bill_candidate_duplicate(
    candidate_id: UUID,
    time_window_minutes: int = Query(default=10, ge=1, le=1440),
) -> DuplicateBillCheckResponse:
    candidate = bill_candidate_store.get(candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Bill candidate not found",
        )

    payload = bill_candidate_store.to_bill_create(candidate)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Bill candidate is missing required fields",
        )
    return bill_store.check_duplicate(
        payload,
        time_window_minutes=time_window_minutes,
    )


@router.post("/bill-candidates/{candidate_id}/confirm", response_model=BillRead)
def confirm_bill_candidate(
    candidate_id: UUID,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> BillRead:
    def confirm() -> BillRead:
        candidate = bill_candidate_store.get(candidate_id)
        if candidate is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bill candidate not found",
            )
        if not bill_candidate_store.is_confirmable(candidate):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Bill candidate is missing required fields",
            )

        bill = bill_candidate_store.confirm(candidate_id)
        if bill is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Bill candidate not found",
            )
        return bill

    try:
        return idempotency_store.run(
            scope="POST /agent/bill-candidates/confirm",
            key=idempotency_key,
            fingerprint={"candidate_id": str(candidate_id)},
            factory=confirm,
        )
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post("/parse-task", response_model=ParseTaskResponse)
def parse_task(payload: ParseTaskRequest) -> ParseTaskResponse:
    if not settings_store.get_privacy_settings().allow_ai_text_processing:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="AI text processing is disabled in privacy settings",
        )
    candidate = task_parser.parse_task(payload)
    return task_candidate_store.save(candidate)


@router.get("/task-candidates", response_model=TaskCandidateListResponse)
def list_task_candidates(
    confirmable_only: bool = Query(default=False),
) -> TaskCandidateListResponse:
    candidates = task_candidate_store.all()
    if confirmable_only:
        candidates = [
            candidate
            for candidate in candidates
            if task_candidate_store.is_confirmable(candidate)
        ]
    return TaskCandidateListResponse(items=candidates, total=len(candidates))


@router.get("/task-candidates/{candidate_id}", response_model=ParseTaskResponse)
def get_task_candidate(candidate_id: UUID) -> ParseTaskResponse:
    candidate = task_candidate_store.get(candidate_id)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task candidate not found",
        )
    return candidate


@router.patch("/task-candidates/{candidate_id}", response_model=ParseTaskResponse)
def update_task_candidate(
    candidate_id: UUID,
    payload: TaskCandidateUpdate,
) -> ParseTaskResponse:
    candidate = task_candidate_store.update(candidate_id, payload)
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task candidate not found",
        )
    return candidate


@router.delete("/task-candidates/{candidate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_candidate(candidate_id: UUID) -> None:
    deleted = task_candidate_store.delete(candidate_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task candidate not found",
        )


@router.post("/task-candidates/{candidate_id}/confirm", response_model=TaskRead)
def confirm_task_candidate(
    candidate_id: UUID,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> TaskRead:
    def confirm() -> TaskRead:
        candidate = task_candidate_store.get(candidate_id)
        if candidate is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task candidate not found",
            )
        if not task_candidate_store.is_confirmable(candidate):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Task candidate is missing required fields",
            )

        task = task_candidate_store.confirm(candidate_id)
        if task is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Task candidate not found",
            )
        return task

    try:
        return idempotency_store.run(
            scope="POST /agent/task-candidates/confirm",
            key=idempotency_key,
            fingerprint={"candidate_id": str(candidate_id)},
            factory=confirm,
        )
    except IdempotencyConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
