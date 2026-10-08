from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch
from urllib.error import URLError

from app.services.model_invocation_service import ModelInvocationService


class _Response:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        import json

        return json.dumps(self._payload).encode("utf-8")


class ModelInvocationServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.settings = SimpleNamespace(
            model_invocation_max_retries=1,
            model_invocation_retry_base_seconds=0.01,
            model_invocation_circuit_failure_threshold=2,
            model_invocation_circuit_reset_seconds=30.0,
            llm_agent_input_cost_per_million_usd=1.0,
            llm_agent_output_cost_per_million_usd=2.0,
            local_model_usage_path="model_usage.json",
        )

    @patch("app.services.model_invocation_service.time.sleep")
    @patch("app.services.model_invocation_service.urlopen")
    @patch("app.services.model_invocation_service.sqlite_state_store.save_json")
    @patch("app.services.model_invocation_service.sqlite_state_store.load_json", return_value=None)
    @patch("app.services.model_invocation_service.settings")
    def test_retry_records_provider_usage_and_cost(
        self,
        runtime_settings,
        _load_json,
        _save_json,
        urlopen,
        sleep,
    ) -> None:
        runtime_settings.__dict__.update(self.settings.__dict__)
        urlopen.side_effect = [
            URLError("temporary failure"),
            _Response({"usage": {"prompt_tokens": 10, "completion_tokens": 4}}),
        ]
        service = ModelInvocationService()

        result = service.invoke_json(
            provider="deepseek",
            model="deepseek-chat",
            endpoint="https://example.test/v1/chat/completions",
            headers={"Content-Type": "application/json"},
            request_body={"model": "deepseek-chat", "messages": []},
            timeout_seconds=3,
        )

        summary = service.summary()
        self.assertIsNotNone(result.payload)
        self.assertEqual(result.warnings, ["llm_agent_retried"])
        self.assertEqual(urlopen.call_count, 2)
        sleep.assert_called_once()
        self.assertEqual(summary.request_count, 1)
        self.assertEqual(summary.success_count, 1)
        self.assertEqual(summary.retry_count, 1)
        self.assertEqual(summary.input_tokens, 10)
        self.assertEqual(summary.output_tokens, 4)
        self.assertEqual(summary.estimated_cost_usd, 0.000018)

    @patch("app.services.model_invocation_service.urlopen", side_effect=URLError("offline"))
    @patch("app.services.model_invocation_service.sqlite_state_store.save_json")
    @patch("app.services.model_invocation_service.sqlite_state_store.load_json", return_value=None)
    @patch("app.services.model_invocation_service.settings")
    def test_circuit_opens_after_consecutive_failures(
        self,
        runtime_settings,
        _load_json,
        _save_json,
        urlopen,
    ) -> None:
        runtime_settings.__dict__.update({
            **self.settings.__dict__,
            "model_invocation_max_retries": 0,
        })
        service = ModelInvocationService()
        kwargs = {
            "provider": "deepseek",
            "model": "deepseek-chat",
            "endpoint": "https://example.test/v1/chat/completions",
            "headers": {"Content-Type": "application/json"},
            "request_body": {"messages": []},
            "timeout_seconds": 3,
        }

        service.invoke_json(**kwargs)
        service.invoke_json(**kwargs)
        blocked = service.invoke_json(**kwargs)

        summary = service.summary()
        self.assertEqual(blocked.warnings, ["llm_agent_circuit_open"])
        self.assertEqual(urlopen.call_count, 2)
        self.assertEqual(summary.failure_count, 2)
        self.assertEqual(summary.circuit_rejection_count, 1)
        self.assertEqual(summary.active_circuit_count, 1)


if __name__ == "__main__":
    unittest.main()
