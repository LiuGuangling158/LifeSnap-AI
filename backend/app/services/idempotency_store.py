from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable

from pydantic import BaseModel

from app.core.config import settings
from app.schemas.bill import BillRead
from app.schemas.chat import ChatConfirmActionResponse, ChatDiscardActionResponse
from app.schemas.diary import DiaryRead
from app.schemas.settings import DemoDataSeedResponse
from app.schemas.task import TaskRead


class IdempotencyConflictError(ValueError):
    pass


@dataclass
class IdempotencyRecord:
    fingerprint: str
    response: Any
    response_type: str | None = None


class LocalIdempotencyStore:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], IdempotencyRecord] = {}
        self._load()

    def run(
        self,
        scope: str,
        key: str | None,
        fingerprint: object,
        factory: Callable[[], Any],
    ) -> Any:
        if key is None:
            return factory()

        normalized_fingerprint = self._normalize_fingerprint(fingerprint)
        record_key = (scope, key)
        existing = self._records.get(record_key)
        if existing is not None:
            if existing.fingerprint != normalized_fingerprint:
                raise IdempotencyConflictError("Idempotency-Key conflicts with another request")
            return existing.response

        response = factory()
        self._records[record_key] = IdempotencyRecord(
            fingerprint=normalized_fingerprint,
            response=response,
            response_type=self._response_type(response),
        )
        self._persist()
        return response

    def clear(self) -> int:
        count = len(self._records)
        self._records.clear()
        self._persist()
        return count

    def _normalize_fingerprint(self, fingerprint: object) -> str:
        return json.dumps(
            fingerprint,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

    def _load(self) -> None:
        path = settings.local_idempotency_path
        if not path.exists():
            return
        try:
            raw_items = json.loads(path.read_text(encoding="utf-8"))
            records: dict[tuple[str, str], IdempotencyRecord] = {}
            for item in raw_items:
                scope = str(item["scope"])
                key = str(item["key"])
                response_type = item.get("response_type")
                records[(scope, key)] = IdempotencyRecord(
                    fingerprint=str(item["fingerprint"]),
                    response=self._deserialize_response(
                        response_type,
                        item.get("response"),
                    ),
                    response_type=response_type,
                )
        except (OSError, ValueError, TypeError, KeyError):
            return
        self._records = records

    def _persist(self) -> None:
        path = settings.local_idempotency_path
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".tmp")
        temp_path.write_text(
            json.dumps(
                [
                    {
                        "scope": scope,
                        "key": key,
                        "fingerprint": record.fingerprint,
                        "response_type": record.response_type
                        or self._response_type(record.response),
                        "response": self._serialize_response(record.response),
                    }
                    for (scope, key), record in sorted(self._records.items())
                ],
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        temp_path.replace(path)

    def _serialize_response(self, response: Any) -> Any:
        if isinstance(response, BaseModel):
            return response.model_dump(mode="json")
        return json.loads(json.dumps(response, ensure_ascii=False, default=str))

    def _deserialize_response(self, response_type: str | None, response: Any) -> Any:
        if response_type is None:
            return response
        model_type = _RESPONSE_MODEL_TYPES.get(response_type)
        if model_type is None:
            return response
        return model_type.model_validate(response)

    def _response_type(self, response: Any) -> str | None:
        if isinstance(response, BaseModel):
            return f"{response.__class__.__module__}.{response.__class__.__name__}"
        return None


_RESPONSE_MODEL_TYPES = {
    f"{model.__module__}.{model.__name__}": model
    for model in (
        BillRead,
        ChatConfirmActionResponse,
        ChatDiscardActionResponse,
        DemoDataSeedResponse,
        DiaryRead,
        TaskRead,
    )
}


idempotency_store = LocalIdempotencyStore()
