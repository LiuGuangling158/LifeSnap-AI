from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from math import ceil
from uuid import UUID, uuid4

from app.core.config import settings
from app.schemas.task import (
    TaskCategoryBreakdown,
    TaskCreate,
    TaskListResponse,
    TaskPriority,
    TaskPriorityBreakdown,
    TaskRead,
    TaskStatisticsOverview,
    TaskStatus,
    TaskStatusBreakdown,
    TaskType,
    TaskTypeBreakdown,
    TaskUpdate,
)


class LocalTaskStore:
    def __init__(self) -> None:
        self._tasks: dict[UUID, TaskRead] = {}
        self._load()

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
        self._persist()
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
        data.update(payload.model_dump(exclude_unset=True))
        data["updated_at"] = datetime.now(timezone.utc)
        if data["status"] == TaskStatus.done and data["completed_at"] is None:
            data["completed_at"] = data["updated_at"]
        if data["status"] != TaskStatus.done:
            data["completed_at"] = None

        updated = TaskRead(**data)
        self._tasks[task_id] = updated
        self._persist()
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
            self._persist()
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
        self._persist()
        return restored

    def clear(self) -> int:
        count = len(self._tasks)
        self._tasks.clear()
        self._persist()
        return count

    def upsert_many(self, tasks: list[TaskRead]) -> int:
        for task in tasks:
            self._tasks[task.id] = task
        self._persist()
        return len(tasks)

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

    def statistics_overview(
        self,
        now: datetime | None = None,
        upcoming_days: int = 7,
        item_limit: int = 10,
    ) -> TaskStatisticsOverview:
        current_at = self._as_utc(now or datetime.now(timezone.utc))
        tasks = self.all()
        pending_tasks = [task for task in tasks if task.status == TaskStatus.pending]
        overdue_tasks = self._overdue_tasks(current_at, pending_tasks, item_limit)
        today_tasks = self.today_tasks(current_at, limit=item_limit)
        upcoming_reminders = self.upcoming_reminders(
            current_at,
            days=upcoming_days,
            limit=item_limit,
        )

        return TaskStatisticsOverview(
            generated_at=current_at,
            upcoming_days=upcoming_days,
            pending_count=self._count_status(tasks, TaskStatus.pending),
            done_count=self._count_status(tasks, TaskStatus.done),
            cancelled_count=self._count_status(tasks, TaskStatus.cancelled),
            overdue_count=len(self._overdue_tasks(current_at, pending_tasks)),
            due_today_count=len(self._due_today_tasks(current_at, pending_tasks)),
            upcoming_reminder_count=len(
                self._upcoming_reminder_tasks(current_at, upcoming_days, pending_tasks)
            ),
            unscheduled_pending_count=len(
                [task for task in pending_tasks if self._target_at(task) is None]
            ),
            status_breakdown=self._status_breakdown(tasks),
            type_breakdown=self._type_breakdown(tasks),
            priority_breakdown=self._priority_breakdown(tasks),
            category_breakdown=self._category_breakdown(tasks),
            overdue_tasks=overdue_tasks,
            today_tasks=today_tasks,
            upcoming_reminders=upcoming_reminders,
        )

    def _overdue_tasks(
        self,
        now: datetime,
        tasks: list[TaskRead],
        limit: int | None = None,
    ) -> list[TaskRead]:
        overdue = [
            task
            for task in tasks
            if self._target_at(task) is not None
            and self._as_utc(self._target_at(task)) < now
        ]
        sorted_tasks = sorted(overdue, key=self._sort_key)
        return sorted_tasks if limit is None else sorted_tasks[:limit]

    def _due_today_tasks(
        self,
        now: datetime,
        tasks: list[TaskRead],
    ) -> list[TaskRead]:
        start_at = self._start_of_day(now)
        end_at = start_at + timedelta(days=1)
        return [
            task
            for task in tasks
            if self._target_at(task) is not None
            and start_at <= self._as_utc(self._target_at(task)) < end_at
        ]

    def _upcoming_reminder_tasks(
        self,
        now: datetime,
        days: int,
        tasks: list[TaskRead],
    ) -> list[TaskRead]:
        start_at = self._as_utc(now)
        end_at = start_at + timedelta(days=days)
        return [
            task
            for task in tasks
            if task.task_type == TaskType.reminder
            and task.remind_at is not None
            and start_at <= self._as_utc(task.remind_at) <= end_at
        ]

    def _status_breakdown(self, tasks: list[TaskRead]) -> list[TaskStatusBreakdown]:
        return [
            TaskStatusBreakdown(status=status, count=self._count_status(tasks, status))
            for status in TaskStatus
        ]

    def _type_breakdown(self, tasks: list[TaskRead]) -> list[TaskTypeBreakdown]:
        return [
            TaskTypeBreakdown(
                task_type=task_type,
                count=len([task for task in tasks if task.task_type == task_type]),
            )
            for task_type in TaskType
        ]

    def _priority_breakdown(self, tasks: list[TaskRead]) -> list[TaskPriorityBreakdown]:
        return [
            TaskPriorityBreakdown(
                priority=priority,
                count=len([task for task in tasks if task.priority == priority]),
            )
            for priority in TaskPriority
        ]

    def _category_breakdown(self, tasks: list[TaskRead]) -> list[TaskCategoryBreakdown]:
        category_counts: dict[str, int] = {}
        for task in tasks:
            category_counts[task.category] = category_counts.get(task.category, 0) + 1

        breakdown = [
            TaskCategoryBreakdown(category=category, count=count)
            for category, count in category_counts.items()
        ]
        breakdown.sort(key=lambda item: (-item.count, item.category))
        return breakdown

    def _count_status(self, tasks: list[TaskRead], status: TaskStatus) -> int:
        return len([task for task in tasks if task.status == status])

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

    def _load(self) -> None:
        path = settings.local_task_path
        if not path.exists():
            return
        try:
            raw_items = json.loads(path.read_text(encoding="utf-8"))
            tasks = [TaskRead.model_validate(item) for item in raw_items]
        except (OSError, ValueError, TypeError):
            return
        self._tasks = {task.id: task for task in tasks}

    def _persist(self) -> None:
        path = settings.local_task_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(
                [
                    task.model_dump(mode="json")
                    for task in sorted(self._tasks.values(), key=self._sort_key)
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temp_path.replace(path)


task_store = LocalTaskStore()
