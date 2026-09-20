from __future__ import annotations

import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar
from uuid import UUID, uuid4

from app.schemas.chat import (
    CandidateSessionRead,
    CandidateSessionStatus,
    ChatActionType,
)
from app.services.sqlite_state_store import sqlite_state_store

T = TypeVar("T")


class CandidateSessionError(Exception):
    pass


class CandidateSessionNotFoundError(CandidateSessionError):
    pass


class CandidateSessionConflictError(CandidateSessionError):
    def __init__(self, session: CandidateSessionRead, expected_revision: int | None) -> None:
        self.session = session
        self.expected_revision = expected_revision
        super().__init__(
            "Candidate session conflict: "
            f"expected revision {expected_revision}, current revision "
            f"{session.revision}, status {session.status.value}"
        )


class CandidateSessionStore:
    _namespace = "candidate_sessions"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sessions: dict[UUID, CandidateSessionRead] = {}
        self._load()

    def ensure(
        self,
        action_type: ChatActionType,
        candidate_id: UUID,
    ) -> CandidateSessionRead:
        with self._lock:
            for session in self._sessions.values():
                if (
                    session.action_type == action_type
                    and session.candidate_id == candidate_id
                    and session.status == CandidateSessionStatus.active
                ):
                    return session
            now = datetime.now(timezone.utc)
            session = CandidateSessionRead(
                session_id=uuid4(),
                candidate_id=candidate_id,
                action_type=action_type,
                revision=1,
                status=CandidateSessionStatus.active,
                created_at=now,
                updated_at=now,
            )
            self._sessions[session.session_id] = session
            self._persist()
            return session

    def get(self, session_id: UUID) -> CandidateSessionRead | None:
        return self._sessions.get(session_id)

    def resolve(
        self,
        *,
        session_id: UUID | None,
        action_type: ChatActionType,
        candidate_id: UUID,
        expected_revision: int | None,
    ) -> CandidateSessionRead:
        with self._lock:
            if session_id is None:
                return self.ensure(action_type, candidate_id)
            session = self._sessions.get(session_id)
            if session is None:
                raise CandidateSessionNotFoundError("Candidate session not found")
            self._validate(session, action_type, candidate_id, expected_revision)
            return session

    def mutate(
        self,
        *,
        session_id: UUID,
        action_type: ChatActionType,
        candidate_id: UUID,
        expected_revision: int,
        operation: Callable[[], T],
        final_status: CandidateSessionStatus | None = None,
    ) -> tuple[T, CandidateSessionRead]:
        with self._lock:
            with sqlite_state_store.transaction():
                session = self._sessions.get(session_id)
                if session is None:
                    raise CandidateSessionNotFoundError("Candidate session not found")
                self._validate(session, action_type, candidate_id, expected_revision)
                result = operation()
                if result is None:
                    raise CandidateSessionNotFoundError("Candidate not found")
                updated = session.model_copy(
                    update={
                        "revision": session.revision + 1,
                        "status": final_status or CandidateSessionStatus.active,
                        "updated_at": datetime.now(timezone.utc),
                    }
                )
                self._sessions[session_id] = updated
                self._persist()
                return result, updated

    def _validate(
        self,
        session: CandidateSessionRead,
        action_type: ChatActionType,
        candidate_id: UUID,
        expected_revision: int | None,
    ) -> None:
        if session.action_type != action_type or session.candidate_id != candidate_id:
            raise CandidateSessionConflictError(session, expected_revision)
        if session.status != CandidateSessionStatus.active:
            raise CandidateSessionConflictError(session, expected_revision)
        if expected_revision is not None and session.revision != expected_revision:
            raise CandidateSessionConflictError(session, expected_revision)

    def _load(self) -> None:
        raw_items = sqlite_state_store.load_json(
            self._namespace,
            Path("candidate_sessions.json"),
        )
        if raw_items is None:
            return
        try:
            sessions = [CandidateSessionRead.model_validate(item) for item in raw_items]
        except (TypeError, ValueError):
            return
        self._sessions = {session.session_id: session for session in sessions}

    def _persist(self) -> None:
        sqlite_state_store.save_json(
            self._namespace,
            [
                session.model_dump(mode="json")
                for session in sorted(
                    self._sessions.values(),
                    key=lambda item: str(item.session_id),
                )
            ],
        )


candidate_session_store = CandidateSessionStore()
