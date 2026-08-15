from __future__ import annotations

import json
from datetime import date, datetime, timezone
from math import ceil
from uuid import UUID, uuid4

from app.core.config import settings
from app.schemas.diary import (
    DiaryCreate,
    DiaryListResponse,
    DiaryMood,
    DiaryMoodBreakdown,
    DiaryRead,
    DiaryStatisticsOverview,
    DiaryUpdate,
)


class DiaryDateConflictError(ValueError):
    pass


class LocalDiaryStore:
    def __init__(self) -> None:
        self._diaries: dict[UUID, DiaryRead] = {}
        self._load()

    def create(self, payload: DiaryCreate) -> DiaryRead:
        if self.get_by_date(payload.entry_date) is not None:
            raise DiaryDateConflictError("Diary entry already exists for this date")

        now = datetime.now(timezone.utc)
        diary = DiaryRead(
            id=uuid4(),
            created_at=now,
            updated_at=now,
            deleted_at=None,
            **payload.model_dump(),
        )
        self._diaries[diary.id] = diary
        self._persist()
        return diary

    def upsert_by_date(self, entry_date: date, payload: DiaryCreate) -> DiaryRead:
        existing = self.get_by_date(entry_date)
        if existing is None:
            return self.create(payload)
        return self.update(existing.id, DiaryUpdate(**payload.model_dump())) or existing

    def list(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
        mood: DiaryMood | None = None,
        keyword: str | None = None,
        include_deleted: bool = False,
        deleted_only: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> DiaryListResponse:
        diaries = self.all(
            include_deleted=include_deleted,
            deleted_only=deleted_only,
        )
        if start_date is not None:
            diaries = [diary for diary in diaries if diary.entry_date >= start_date]
        if end_date is not None:
            diaries = [diary for diary in diaries if diary.entry_date <= end_date]
        if mood is not None:
            diaries = [diary for diary in diaries if diary.mood == mood]
        if keyword is not None:
            normalized_keyword = keyword.casefold()
            diaries = [
                diary for diary in diaries if self._matches_keyword(diary, normalized_keyword)
            ]

        sorted_diaries = sorted(
            diaries,
            key=lambda diary: (diary.entry_date, diary.created_at),
            reverse=True,
        )
        total = len(sorted_diaries)
        start = (page - 1) * page_size
        end = start + page_size

        return DiaryListResponse(
            items=sorted_diaries[start:end],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def get(self, diary_id: UUID, include_deleted: bool = False) -> DiaryRead | None:
        diary = self._diaries.get(diary_id)
        if diary is None:
            return None
        if diary.deleted_at is not None and not include_deleted:
            return None
        return diary

    def get_by_date(
        self,
        entry_date: date,
        include_deleted: bool = False,
    ) -> DiaryRead | None:
        matches = [diary for diary in self._diaries.values() if diary.entry_date == entry_date]
        for diary in matches:
            if diary.deleted_at is None:
                return diary
        if include_deleted and matches:
            return matches[0]
        return None

    def all(
        self,
        include_deleted: bool = False,
        deleted_only: bool = False,
    ) -> list[DiaryRead]:
        diaries = list(self._diaries.values())
        if deleted_only:
            return [diary for diary in diaries if diary.deleted_at is not None]
        if include_deleted:
            return diaries
        return [diary for diary in diaries if diary.deleted_at is None]

    def deleted_count(self) -> int:
        return len(self.all(deleted_only=True))

    def update(self, diary_id: UUID, payload: DiaryUpdate) -> DiaryRead | None:
        existing = self.get(diary_id)
        if existing is None:
            return None

        data = existing.model_dump()
        update_data = payload.model_dump(exclude_none=True, exclude_unset=True)
        next_entry_date = update_data.get("entry_date")
        if next_entry_date is not None and next_entry_date != existing.entry_date:
            same_date = self.get_by_date(next_entry_date)
            if same_date is not None and same_date.id != diary_id:
                raise DiaryDateConflictError("Diary entry already exists for this date")

        data.update(update_data)
        data["updated_at"] = datetime.now(timezone.utc)

        updated = DiaryRead(**data)
        self._diaries[diary_id] = updated
        self._persist()
        return updated

    def delete(self, diary_id: UUID) -> bool:
        existing = self._diaries.get(diary_id)
        if existing is None:
            return False

        if existing.deleted_at is None:
            now = datetime.now(timezone.utc)
            data = existing.model_dump()
            data["updated_at"] = now
            data["deleted_at"] = now
            self._diaries[diary_id] = DiaryRead(**data)
            self._persist()
        return True

    def restore(self, diary_id: UUID) -> DiaryRead | None:
        existing = self._diaries.get(diary_id)
        if existing is None:
            return None
        if existing.deleted_at is None:
            return existing

        same_date = self.get_by_date(existing.entry_date)
        if same_date is not None and same_date.id != diary_id:
            raise DiaryDateConflictError("Diary entry already exists for this date")

        data = existing.model_dump()
        data["updated_at"] = datetime.now(timezone.utc)
        data["deleted_at"] = None
        restored = DiaryRead(**data)
        self._diaries[diary_id] = restored
        self._persist()
        return restored

    def clear(self) -> int:
        count = len(self._diaries)
        self._diaries.clear()
        self._persist()
        return count

    def upsert_many(self, diaries: list[DiaryRead]) -> int:
        for diary in diaries:
            self._diaries[diary.id] = diary
        self._persist()
        return len(diaries)

    def statistics_overview(self, now: datetime | None = None) -> DiaryStatisticsOverview:
        current_at = now or datetime.now(timezone.utc)
        diaries = self.all()
        return DiaryStatisticsOverview(
            generated_at=current_at,
            total_count=len(diaries),
            current_month_count=len(
                [
                    diary
                    for diary in diaries
                    if diary.entry_date.year == current_at.year
                    and diary.entry_date.month == current_at.month
                ]
            ),
            streak_days=self._streak_days(current_at.date(), diaries),
            mood_breakdown=[
                DiaryMoodBreakdown(
                    mood=mood,
                    count=len([diary for diary in diaries if diary.mood == mood]),
                )
                for mood in DiaryMood
            ],
        )

    def _matches_keyword(self, diary: DiaryRead, keyword: str) -> bool:
        fields = [
            diary.title,
            diary.content,
            diary.weather or "",
        ]
        return any(keyword in field.casefold() for field in fields)

    def _streak_days(self, today: date, diaries: list[DiaryRead]) -> int:
        recorded_dates = {diary.entry_date for diary in diaries}
        streak = 0
        current_date = today
        while current_date in recorded_dates:
            streak += 1
            current_date = date.fromordinal(current_date.toordinal() - 1)
        return streak

    def _load(self) -> None:
        path = settings.local_diary_path
        if not path.exists():
            return
        try:
            raw_items = json.loads(path.read_text(encoding="utf-8"))
            diaries = [DiaryRead.model_validate(item) for item in raw_items]
        except (OSError, ValueError, TypeError):
            return
        self._diaries = {diary.id: diary for diary in diaries}

    def _persist(self) -> None:
        path = settings.local_diary_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(
                [
                    diary.model_dump(mode="json")
                    for diary in sorted(
                        self._diaries.values(),
                        key=lambda item: (item.entry_date, item.created_at),
                        reverse=True,
                    )
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temp_path.replace(path)


diary_store = LocalDiaryStore()
