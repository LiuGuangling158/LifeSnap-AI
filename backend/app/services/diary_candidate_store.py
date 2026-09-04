from __future__ import annotations

import json
from uuid import UUID

from app.core.config import settings
from app.schemas.agent import DiaryCandidateData, DiaryCandidateUpdate, ParseDiaryResponse
from app.schemas.diary import DiaryCreate, DiaryRead
from app.services.diary_store import diary_store


class LocalDiaryCandidateStore:
    def __init__(self) -> None:
        self._candidates: dict[UUID, ParseDiaryResponse] = {}
        self._load()

    def save(self, candidate: ParseDiaryResponse) -> ParseDiaryResponse:
        self._candidates[candidate.candidate_id] = candidate
        self._persist()
        return candidate

    def get(self, candidate_id: UUID) -> ParseDiaryResponse | None:
        return self._candidates.get(candidate_id)

    def all(self) -> list[ParseDiaryResponse]:
        return list(self._candidates.values())

    def update(
        self,
        candidate_id: UUID,
        payload: DiaryCandidateUpdate,
    ) -> ParseDiaryResponse | None:
        candidate = self.get(candidate_id)
        if candidate is None:
            return None

        data = candidate.data.model_dump()
        updates = payload.model_dump(exclude_unset=True)
        for field in ("mood", "source"):
            if field in updates and updates[field] is None:
                updates.pop(field)
        data.update(updates)

        candidate.data = DiaryCandidateData(**data)
        candidate.warnings = self._warnings(candidate.data)
        candidate.field_confidence = self._field_confidence(candidate.data)
        candidate.confidence = self._overall_confidence(candidate.field_confidence)
        return self.save(candidate)

    def confirm(self, candidate_id: UUID) -> DiaryRead | None:
        candidate = self.get(candidate_id)
        if candidate is None:
            return None
        payload = self.to_diary_create(candidate)
        if payload is None:
            return None

        diary = diary_store.upsert_by_date(payload.entry_date, payload)
        del self._candidates[candidate_id]
        self._persist()
        return diary

    def delete(self, candidate_id: UUID) -> bool:
        if candidate_id not in self._candidates:
            return False
        del self._candidates[candidate_id]
        self._persist()
        return True

    def is_confirmable(self, candidate: ParseDiaryResponse) -> bool:
        return (
            candidate.data.entry_date is not None
            and candidate.data.title is not None
            and candidate.data.content is not None
        )

    def to_diary_create(self, candidate: ParseDiaryResponse) -> DiaryCreate | None:
        entry_date = candidate.data.entry_date
        title = candidate.data.title
        content = candidate.data.content
        if entry_date is None or title is None or content is None:
            return None

        return DiaryCreate(
            entry_date=entry_date,
            title=title,
            content=content,
            mood=candidate.data.mood,
            weather=candidate.data.weather,
            source=candidate.data.source,
            tags=candidate.data.tags,
        )

    def clear(self) -> int:
        count = len(self._candidates)
        self._candidates.clear()
        self._persist()
        return count

    def upsert_many(self, candidates: list[ParseDiaryResponse]) -> int:
        for candidate in candidates:
            self._candidates[candidate.candidate_id] = candidate
        self._persist()
        return len(candidates)

    def _warnings(self, data: DiaryCandidateData) -> list[str]:
        warnings: list[str] = []
        if data.entry_date is None:
            warnings.append("entry_date_missing")
        if data.title is None:
            warnings.append("title_missing")
        if data.content is None:
            warnings.append("content_missing")
        if not data.tags:
            warnings.append("tags_missing")
        return warnings

    def _field_confidence(self, data: DiaryCandidateData) -> dict[str, float]:
        return {
            "entry_date": 1.0 if data.entry_date is not None else 0.0,
            "title": 0.9 if data.title else 0.0,
            "content": 0.9 if data.content else 0.0,
            "mood": 0.75,
            "weather": 0.8 if data.weather else 0.0,
            "tags": 0.8 if data.tags else 0.0,
        }

    def _overall_confidence(self, field_confidence: dict[str, float]) -> float:
        important_fields = ["entry_date", "title", "content", "mood"]
        score = sum(field_confidence[field] for field in important_fields) / len(important_fields)
        return round(score, 2)

    def _load(self) -> None:
        path = settings.local_diary_candidate_path
        if not path.exists():
            return
        try:
            raw_items = json.loads(path.read_text(encoding="utf-8"))
            candidates = [ParseDiaryResponse.model_validate(item) for item in raw_items]
        except (OSError, ValueError, TypeError):
            return
        self._candidates = {candidate.candidate_id: candidate for candidate in candidates}

    def _persist(self) -> None:
        path = settings.local_diary_candidate_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(
                [
                    candidate.model_dump(mode="json")
                    for candidate in sorted(
                        self._candidates.values(),
                        key=lambda item: str(item.candidate_id),
                    )
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temp_path.replace(path)


diary_candidate_store = LocalDiaryCandidateStore()
