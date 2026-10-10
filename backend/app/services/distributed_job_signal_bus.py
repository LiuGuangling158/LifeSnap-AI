from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Protocol
from uuid import UUID


logger = logging.getLogger(__name__)


class RedisListClient(Protocol):
    def lpush(self, name: str, *values: str) -> int: ...

    def ltrim(self, name: str, start: int, end: int) -> bool: ...

    def rpop(self, name: str) -> str | bytes | None: ...


@dataclass(frozen=True)
class DistributedQueueStatus:
    backend: str
    configured: bool
    queue_name: str | None
    redis_available: bool | None
    signal_failure_count: int
    last_error: str | None


class RedisJobSignalBus:
    """Best-effort Redis wake-up channel for durable database jobs.

    Redis does not hold the authoritative task state. Every signal is resolved
    through the database's idempotent lease claim, and periodic database scans
    recover from missed or unavailable Redis messages.
    """

    def __init__(
        self,
        *,
        redis_url: str | None,
        queue_name: str,
        enabled: bool | None = None,
        client_factory: Callable[[str], RedisListClient] | None = None,
    ) -> None:
        self._redis_url = redis_url
        self._queue_name = queue_name
        self._enabled = bool(redis_url) if enabled is None else enabled
        self._client_factory = client_factory or self._default_client_factory
        self._lock = threading.RLock()
        self._client: RedisListClient | None = None
        self._redis_available: bool | None = None
        self._signal_failure_count = 0
        self._last_error: str | None = None
        self._last_failure_logged_at = 0.0

    @property
    def configured(self) -> bool:
        return not self._enabled or bool(self._redis_url)

    def publish(self, job_id: UUID) -> bool:
        if not self._enabled:
            return False
        if not self._redis_url:
            self._record_error(RuntimeError("LIFESNAP_REDIS_URL is required for Redis dispatch"))
            return False
        try:
            client = self._get_client()
            client.lpush(self._queue_name, str(job_id))
            # Signals may duplicate safely. Cap the wake-up list so a prolonged
            # database outage cannot make the Redis key grow without bound.
            client.ltrim(self._queue_name, 0, 9_999)
        except Exception as error:
            self._record_error(error)
            return False
        self._record_success()
        return True

    def consume(self, limit: int) -> list[UUID]:
        if not self._enabled or limit <= 0:
            return []
        if not self._redis_url:
            return []
        try:
            client = self._get_client()
            values = [client.rpop(self._queue_name) for _ in range(limit)]
        except Exception as error:
            self._record_error(error)
            return []
        self._record_success()
        job_ids: list[UUID] = []
        seen: set[UUID] = set()
        for value in values:
            if value is None:
                continue
            raw = value.decode("utf-8") if isinstance(value, bytes) else str(value)
            try:
                job_id = UUID(raw)
            except ValueError:
                logger.warning("Discarded malformed Redis async-job signal")
                continue
            if job_id not in seen:
                seen.add(job_id)
                job_ids.append(job_id)
        return job_ids

    def status(self) -> DistributedQueueStatus:
        with self._lock:
            return DistributedQueueStatus(
                backend="redis" if self._enabled else "database",
                configured=self.configured,
                queue_name=self._queue_name if self._enabled else None,
                redis_available=self._redis_available,
                signal_failure_count=self._signal_failure_count,
                last_error=self._last_error,
            )

    def _get_client(self) -> RedisListClient:
        with self._lock:
            if self._client is None:
                if not self._enabled or not self._redis_url:
                    raise RuntimeError("Redis URL is not configured")
                self._client = self._client_factory(self._redis_url)
            return self._client

    def _record_success(self) -> None:
        with self._lock:
            self._redis_available = True
            self._last_error = None

    def _record_error(self, error: Exception) -> None:
        should_log = False
        with self._lock:
            now = time.monotonic()
            should_log = (
                self._redis_available is not False
                or now - self._last_failure_logged_at >= 60
            )
            self._redis_available = False
            self._signal_failure_count += 1
            self._last_error = str(error)[:240] or error.__class__.__name__
            if should_log:
                self._last_failure_logged_at = now
        if should_log:
            logger.warning("Redis async-job signal unavailable; using database polling: %s", error)

    @staticmethod
    def _default_client_factory(redis_url: str) -> RedisListClient:
        try:
            import redis
        except ImportError as error:  # Keeps local fallback usable before optional install.
            raise RuntimeError("redis package is not installed") from error
        return redis.Redis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
