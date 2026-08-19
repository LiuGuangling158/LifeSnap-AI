from datetime import date, datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, Field


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


class DiaryUpdate(BaseModel):
    entry_date: date | None = None
    title: str | None = Field(default=None, min_length=1, max_length=120)
    content: str | None = Field(default=None, min_length=1, max_length=5000)
    mood: DiaryMood | None = None
    weather: str | None = Field(default=None, max_length=40)
    source: DiarySource | None = None
    attachment_ids: list[UUID] | None = None


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
