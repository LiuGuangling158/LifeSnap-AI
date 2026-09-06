from datetime import date, datetime
from enum import Enum
from uuid import UUID

from app.schemas.patch import PatchModel

from pydantic import BaseModel, Field, field_validator


def _normalize_tag_values(value: object) -> list[str]:
    if value is None:
        return []
    raw_items = value if isinstance(value, list) else [value]
    tags: list[str] = []
    for item in raw_items:
        text = str(item).strip()
        if not text or len(text) > 40 or text in tags:
            continue
        tags.append(text)
        if len(tags) >= 20:
            break
    return tags


class DiaryMood(str, Enum):
    happy = "happy"
    calm = "calm"
    tired = "tired"
    anxious = "anxious"
    sad = "sad"


class DiarySource(str, Enum):
    manual = "manual"
    voice = "voice"
    ai_chat = "ai_chat"


class DiaryCreate(BaseModel):
    entry_date: date
    title: str = Field(min_length=1, max_length=120)
    content: str = Field(min_length=1, max_length=5000)
    mood: DiaryMood = DiaryMood.happy
    weather: str | None = Field(default=None, max_length=40)
    source: DiarySource = DiarySource.manual
    attachment_ids: list[UUID] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: object) -> list[str]:
        return _normalize_tag_values(value)


class DiaryUpdate(PatchModel):
    non_nullable_fields = frozenset(["entry_date","title","content","mood","source","attachment_ids","tags"])

    entry_date: date | None = None
    title: str | None = Field(default=None, min_length=1, max_length=120)
    content: str | None = Field(default=None, min_length=1, max_length=5000)
    mood: DiaryMood | None = None
    weather: str | None = Field(default=None, max_length=40)
    source: DiarySource | None = None
    attachment_ids: list[UUID] | None = None
    tags: list[str] | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: object) -> list[str] | None:
        if value is None:
            return None
        return _normalize_tag_values(value)


class DiaryRead(DiaryCreate):
    id: UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None


class DiaryListResponse(BaseModel):
    items: list[DiaryRead]
    total: int
    page: int
    page_size: int
    total_pages: int


class DiaryMoodBreakdown(BaseModel):
    mood: DiaryMood
    count: int


class DiaryStatisticsOverview(BaseModel):
    generated_at: datetime
    total_count: int
    current_month_count: int
    streak_days: int
    mood_breakdown: list[DiaryMoodBreakdown]
