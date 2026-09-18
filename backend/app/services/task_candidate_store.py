from __future__ import annotations

import json
from uuid import UUID

from app.core.config import settings
from app.services.sqlite_state_store import sqlite_state_store
from app.schemas.agent import ParseTaskResponse, TaskCandidateData, TaskCandidateUpdate
from app.schemas.task import TaskCreate, TaskRead, TaskType
from app.services.task_parser import task_parser
from app.services.task_store import task_store


class LocalTaskCandidateStore:
    def __init__(self) -> None:
        self._candidates: dict[UUID, ParseTaskResponse] = {}
        self._load()

    def reload_for_current_owner(self) -> None:
        self._candidates = {}
        self._load()

    def save(self, candidate: ParseTaskResponse) -> ParseTaskResponse:
        self._candidates[candidate.candidate_id] = candidate
        self._persist()
        return candidate

    def get(self, candidate_id: UUID) -> ParseTaskResponse | None:
        return self._candidates.get(candidate_id)

    def all(self) -> list[ParseTaskResponse]:
        return list(self._candidates.values())

    def update(
        self,
        candidate_id: UUID,
        payload: TaskCandidateUpdate,
    ) -> ParseTaskResponse | None:
        candidate = self.get(candidate_id)
        if candidate is None:
            return None

        data = candidate.data.model_dump()
        updates = payload.model_dump(exclude_unset=True)
        for field in ("category", "task_type", "priority", "source"):
            if field in updates and updates[field] is None:
                updates.pop(field)
        data.update(updates)

        candidate.data = TaskCandidateData(**data)
        candidate.warnings = task_parser.warnings_for_data(candidate.data)
        candidate.field_confidence = task_parser.field_confidence_for_data(candidate.data)
        candidate.confidence = task_parser.overall_confidence(
            candidate.field_confidence,
            candidate.data.task_type,
        )
        return self.save(candidate)

    def confirm(self, candidate_id: UUID) -> TaskRead | None:
        candidate = self.get(candidate_id)
        if candidate is None:
            return None
        if not self.is_confirmable(candidate):
            return None

        title = candidate.data.title
        if title is None:
            return None

        task = task_store.create(
            TaskCreate(
                title=title,
                description=candidate.data.description,
                category=candidate.data.category,
                task_type=candidate.data.task_type,
                due_at=candidate.data.due_at,
                remind_at=candidate.data.remind_at,
                priority=candidate.data.priority,
                source=candidate.data.source,
            )
        )
        del self._candidates[candidate_id]
        self._persist()
        return task

    def delete(self, candidate_id: UUID) -> bool:
        if candidate_id not in self._candidates:
            return False
        del self._candidates[candidate_id]
        self._persist()
        return True

    def is_confirmable(self, candidate: ParseTaskResponse) -> bool:
        if candidate.data.title is None:
            return False
        if candidate.data.task_type == TaskType.reminder:
            return candidate.data.remind_at is not None
        return True

    def clear(self) -> int:
        count = len(self._candidates)
        self._candidates.clear()
        self._persist()
        return count

    def upsert_many(self, candidates: list[ParseTaskResponse]) -> int:
        for candidate in candidates:
            self._candidates[candidate.candidate_id] = candidate
        self._persist()
        return len(candidates)

    def _load(self) -> None:
        raw_items = sqlite_state_store.load_json("task_candidates", settings.local_task_candidate_path)
        if raw_items is None:
            return
        try:
            candidates = [ParseTaskResponse.model_validate(item) for item in raw_items]
        except (ValueError, TypeError):
            return
        self._candidates = {candidate.candidate_id: candidate for candidate in candidates}

    def _persist(self) -> None:
        sqlite_state_store.save_json(
            "task_candidates",
            [
                candidate.model_dump(mode="json")
                for candidate in sorted(
                    self._candidates.values(),
                    key=lambda item: str(item.candidate_id),
                )
            ],
        )


task_candidate_store = LocalTaskCandidateStore()
