import json
from dataclasses import dataclass
from typing import Any, Callable


class IdempotencyConflictError(ValueError):
    pass


@dataclass
class IdempotencyRecord:
    fingerprint: str
    response: Any


class InMemoryIdempotencyStore:
    def __init__(self) -> None:
        self._records: dict[tuple[str, str], IdempotencyRecord] = {}

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
        )
        return response

    def clear(self) -> int:
        count = len(self._records)
        self._records.clear()
        return count

    def _normalize_fingerprint(self, fingerprint: object) -> str:
        return json.dumps(
            fingerprint,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )


idempotency_store = InMemoryIdempotencyStore()
