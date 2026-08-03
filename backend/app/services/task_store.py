from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import ceil
from uuid import UUID, uuid4

from app.schemas.task import (
    TaskCreate,
    TaskListResponse,
    TaskRead,
    TaskStatus,
    TaskType,
    TaskUpdate,
)


class InMemoryTaskStore:
    def __init__(self) -> None:
        self._tasks: dict[UUID, TaskRead] = {}

    def create(self, payload: TaskCreate) -> TaskRead:
        now = datetime.now(timezone.utc)
        task = TaskRead(
            id=uuid4(),
            status=TaskStatus.pending,
            created_at=now,
            updated_at=now,
            completed_at=None,
            deleted_at=None,
            **payload.model_dump(),
        )
        self._tasks[task.id] = task
        return task

    def list(
        self,
        status: TaskStatus | None = None,
        task_type: TaskType | None = None,
        category: str | None = None,
        due_from: datetime | None = None,
        due_to: datetime | None = None,
        include_deleted: bool = False,
        deleted_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> TaskListResponse:
        tasks = self.all(
            include_deleted=include_deleted,
            deleted_only=deleted_only,
        )
        if status is not None:
            tasks = [task for task in tasks if task.status == status]
        if task_type is not None:
            tasks = [task for task in tasks if task.task_type == task_type]
        if category is not None:
            tasks = [task for task in tasks if task.category == category]
        if due_from is not None:
            due_from_utc = self._as_utc(due_from)
            tasks = [
                task
                for task in tasks
                if self._target_at(task) is not None
                and self._as_utc(self._target_at(task)) >= due_from_utc
            ]
        if due_to is not None:
            due_to_utc = self._as_utc(due_to)
            tasks = [
                task
                for task in tasks
                if self._target_at(task) is not None
                and self._as_utc(self._target_at(task)) <= due_to_utc
            ]

        sorted_tasks = sorted(tasks, key=self._sort_key)
        total = len(sorted_tasks)
        start = (page - 1) * page_size
        end = start + page_size

        return TaskListResponse(
            items=sorted_tasks[start:end],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def get(self, task_id: UUID, include_deleted: bool = False) -> TaskRead | None:
        task = self._tasks.get(task_id)
        if task is None:
            return None
        if task.deleted_at is not None and not include_deleted:
            return None
        return task

    def all(
        self,
        include_deleted: bool = False,
        deleted_only: bool = False,
    ) -> list[TaskRead]:
        tasks = list(self._tasks.values())
        if deleted_only:
            return [task for task in tasks if task.deleted_at is not None]
        if include_deleted:
            return tasks
        return [task for task in tasks if task.deleted_at is None]

    def deleted_count(self) -> int:
        return len(self.all(deleted_only=True))

    def update(self, task_id: UUID, payload: TaskUpdate) -> TaskRead | None:
        existing = self.get(task_id)
        if existing is None:
            return None

        data = existing.model_dump()
        data.update(payload.model_dump(exclude_none=True, exclude_unset=True))
        data["updated_at"] = datetime.now(timezone.utc)
        if data["status"] == TaskStatus.done and data["completed_at"] is None:
            data["completed_at"] = data["updated_at"]
        if data["status"] != TaskStatus.done:
            data["completed_at"] = None

        updated = TaskRead(**data)
        self._tasks[task_id] = updated
        return updated

    def complete(self, task_id: UUID) -> TaskRead | None:
        return self.update(task_id, TaskUpdate(status=TaskStatus.done))

    def snooze(
        self,
        task_id: UUID,
        snooze_until: datetime | None = None,
        minutes: int | None = None,
    ) -> TaskRead | None:
        existing = self.get(task_id)
        if existing is None:
            return None

        target_at = snooze_until
        if target_at is None and minutes is not None:
            now = datetime.now(timezone.utc)
            base_at = self._target_at(existing)
            if base_at is None or self._as_utc(base_at) < now:
                base_at = now
            target_at = base_at + timedelta(minutes=minutes)
        if target_at is None:
            return None

        if existing.task_type == TaskType.reminder:
            return self.update(task_id, TaskUpdate(remind_at=target_at))
        return self.update(task_id, TaskUpdate(due_at=target_at))

    def delete(self, task_id: UUID) -> bool:
        existing = self._tasks.get(task_id)
        if existing is None:
            return False

        if existing.deleted_at is None:
            now = datetime.now(timezone.utc)
            data = existing.model_dump()
            data["updated_at"] = now
            data["deleted_at"] = now
            self._tasks[task_id] = TaskRead(**data)
        return True

    def restore(self, task_id: UUID) -> TaskRead | None:
        existing = self._tasks.get(task_id)
        if existing is None:
            return None
        if existing.deleted_at is None:
            return existing

        data = existing.model_dump()
        data["updated_at"] = datetime.now(timezone.utc)
        data["deleted_at"] = None
        restored = TaskRead(**data)
        self._tasks[task_id] = restored
        return restored

    def clear(self) -> int:
        count = len(self._tasks)
        self._tasks.clear()
        return count

    def today_tasks(self, now: datetime, limit: int = 10) -> list[TaskRead]:
        start_at = self._start_of_day(now)
        end_at = start_at + timedelta(days=1)
        tasks = [
            task
            for task in self.all()
            if task.status == TaskStatus.pending
            and task.task_type == TaskType.todo
            and task.due_at is not None
            and start_at <= self._as_utc(task.due_at) < end_at
        ]
        return sorted(tasks, key=self._sort_key)[:limit]

    def upcoming_reminders(
        self,
        now: datetime,
        days: int = 7,
        limit: int = 10,
    ) -> list[TaskRead]:
        start_at = self._as_utc(now)
        end_at = start_at + timedelta(days=days)
        reminders = [
            task
            for task in self.all()
            if task.status == TaskStatus.pending
            and task.task_type == TaskType.reminder
            and task.remind_at is not None
            and start_at <= self._as_utc(task.remind_at) <= end_at
        ]
        return sorted(reminders, key=self._sort_key)[:limit]

    def _sort_key(self, task: TaskRead) -> tuple[int, datetime]:
        target_at = self._target_at(task)
        if target_at is not None:
            return (0, self._as_utc(target_at))
        return (1, self._as_utc(task.created_at))

    def _target_at(self, task: TaskRead) -> datetime | None:
        if task.task_type == TaskType.reminder:
            return task.remind_at or task.due_at
        return task.due_at or task.remind_at

    def _as_utc(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _start_of_day(self, value: datetime) -> datetime:
        value_utc = self._as_utc(value)
        return value_utc.replace(hour=0, minute=0, second=0, microsecond=0)


task_store = InMemoryTaskStore()
