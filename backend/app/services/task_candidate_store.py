from uuid import UUID

from app.schemas.agent import ParseTaskResponse, TaskCandidateData, TaskCandidateUpdate
from app.schemas.task import TaskCreate, TaskRead, TaskType
from app.services.task_parser import task_parser
from app.services.task_store import task_store


class InMemoryTaskCandidateStore:
    def __init__(self) -> None:
        self._candidates: dict[UUID, ParseTaskResponse] = {}

    def save(self, candidate: ParseTaskResponse) -> ParseTaskResponse:
        self._candidates[candidate.candidate_id] = candidate
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
        return task

    def delete(self, candidate_id: UUID) -> bool:
        if candidate_id not in self._candidates:
            return False
        del self._candidates[candidate_id]
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
        return count


task_candidate_store = InMemoryTaskCandidateStore()
