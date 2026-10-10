from __future__ import annotations

import unittest
from uuid import uuid4

from app.services.distributed_job_signal_bus import RedisJobSignalBus


class FakeRedisList:
    def __init__(self) -> None:
        self.values: list[str] = []

    def lpush(self, _name: str, *values: str) -> int:
        self.values[0:0] = values
        return len(self.values)

    def ltrim(self, _name: str, start: int, end: int) -> bool:
        self.values = self.values[start : end + 1]
        return True

    def rpop(self, _name: str) -> str | None:
        return self.values.pop() if self.values else None


class FailingRedisList(FakeRedisList):
    def lpush(self, _name: str, *values: str) -> int:
        raise OSError("Redis is unreachable")

    def rpop(self, _name: str) -> str | None:
        raise OSError("Redis is unreachable")


class RedisJobSignalBusTests(unittest.TestCase):
    def test_redis_signal_is_consumed_with_duplicates_deduplicated(self) -> None:
        client = FakeRedisList()
        bus = RedisJobSignalBus(
            redis_url="redis://example.test:6379/0",
            queue_name="test:jobs",
            enabled=True,
            client_factory=lambda _url: client,
        )
        job_id = uuid4()

        self.assertTrue(bus.publish(job_id))
        self.assertTrue(bus.publish(job_id))
        self.assertEqual(bus.consume(limit=4), [job_id])

        status = bus.status()
        self.assertEqual(status.backend, "redis")
        self.assertTrue(status.configured)
        self.assertTrue(status.redis_available)
        self.assertEqual(status.signal_failure_count, 0)

    def test_redis_failure_keeps_database_fallback_usable(self) -> None:
        bus = RedisJobSignalBus(
            redis_url="redis://example.test:6379/0",
            queue_name="test:jobs",
            enabled=True,
            client_factory=lambda _url: FailingRedisList(),
        )

        self.assertFalse(bus.publish(uuid4()))
        self.assertEqual(bus.consume(limit=2), [])

        status = bus.status()
        self.assertFalse(status.redis_available)
        self.assertGreaterEqual(status.signal_failure_count, 1)
        self.assertIn("unreachable", status.last_error or "")

    def test_database_mode_does_not_require_redis(self) -> None:
        bus = RedisJobSignalBus(
            redis_url=None,
            queue_name="test:jobs",
            enabled=False,
        )

        self.assertFalse(bus.publish(uuid4()))
        self.assertEqual(bus.consume(limit=1), [])
        self.assertEqual(bus.status().backend, "database")
        self.assertIsNone(bus.status().redis_available)


if __name__ == "__main__":
    unittest.main()
