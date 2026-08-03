from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


class TaskType(str, Enum):
    todo = "todo"
    reminder = "reminder"


class TaskStatus(str, Enum):
    pending = "pending"
    done = "done"
    cancelled = "cancelled"


class TaskPriority(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class TaskSource(str, Enum):
    manual = "manual"
    ai_chat = "ai_chat"


class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    category: str = Field(default="生活", min_length=1, max_length=40)
    task_type: TaskType = TaskType.todo
    due_at: datetime | None = None
    remind_at: datetime | None = None
    priority: TaskPriority = TaskPriority.medium
    source: TaskSource = TaskSource.manual


class TaskUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    category: str | None = Field(default=None, min_length=1, max_length=40)
    task_type: TaskType | None = None
    due_at: datetime | None = None
    remind_at: datetime | None = None
    status: TaskStatus | None = None
    priority: TaskPriority | None = None
    source: TaskSource | None = None


class TaskSnoozeRequest(BaseModel):
    snooze_until: datetime | None = None
    minutes: int | None = Field(default=None, ge=1, le=43200)


class TaskRead(TaskCreate):
    id: UUID
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    deleted_at: datetime | None = None


class TaskListResponse(BaseModel):
    items: list[TaskRead]
    total: int
    page: int
    page_size: int
    total_pages: int
