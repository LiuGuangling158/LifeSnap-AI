from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from math import ceil
from typing import Any
from uuid import UUID, uuid4

from fastapi import Request

from app.schemas.audit import AuditEvent, AuditEventListResponse


class InMemoryAuditLogStore:
    def __init__(self, max_events: int = 500) -> None:
        self._events: list[AuditEvent] = []
        self._max_events = max_events

    def record(
        self,
        *,
        action: str,
        entity_type: str,
        entity_id: object | None = None,
        request: Request | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=uuid4(),
            occurred_at=datetime.now(timezone.utc),
            action=action,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            request_id=self._request_id(request),
            method=request.method if request is not None else None,
            path=str(request.url.path) if request is not None else None,
            metadata=self._safe_metadata(metadata or {}),
        )
        self._events.append(event)
        if len(self._events) > self._max_events:
            self._events = self._events[-self._max_events :]
        return event

    def list(
        self,
        *,
        action: str | None = None,
        entity_type: str | None = None,
        request_id: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> AuditEventListResponse:
        events = list(reversed(self._events))
        if action is not None:
            events = [event for event in events if event.action == action]
        if entity_type is not None:
            events = [event for event in events if event.entity_type == entity_type]
        if request_id is not None:
            events = [event for event in events if event.request_id == request_id]

        total = len(events)
        start = (page - 1) * page_size
        end = start + page_size
        return AuditEventListResponse(
            items=events[start:end],
            total=total,
            page=page,
            page_size=page_size,
            total_pages=ceil(total / page_size) if total else 0,
        )

    def clear(self) -> int:
        count = len(self._events)
        self._events.clear()
        return count

    def _request_id(self, request: Request | None) -> str | None:
        if request is None:
            return None
        return getattr(request.state, "request_id", None)

    def _safe_metadata(self, metadata: dict[str, Any]) -> dict[str, Any]:
        safe: dict[str, Any] = {}
        for key, value in list(metadata.items())[:20]:
            normalized_key = str(key)
            if normalized_key.lower() in _SENSITIVE_METADATA_KEYS:
                safe[normalized_key] = "[redacted]"
                continue
            safe[normalized_key] = self._safe_value(value)
        return safe

    def _safe_value(self, value: Any) -> Any:
        if value is None or isinstance(value, bool | int | float):
            return value
        if isinstance(value, Enum):
            return value.value
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, datetime):
            return value.isoformat()
        if isinstance(value, str):
            return value[:120]
        if isinstance(value, list | tuple | set):
            return {"count": len(value)}
        if isinstance(value, dict):
            return {"keys": sorted(str(key) for key in value.keys())[:20]}
        return str(value)[:120]


_SENSITIVE_METADATA_KEYS = {
    "body",
    "content",
    "description",
    "note",
    "ocr_text",
    "payload",
    "raw_text",
    "text",
}


audit_log_store = InMemoryAuditLogStore()
