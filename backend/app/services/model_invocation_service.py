from __future__ import annotations

import json
import math
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.core.config import settings
from app.core.user_context import SYSTEM_OWNER_ID
from app.schemas.observability import ModelUsageRecord, ModelUsageSummary
from app.services.sqlite_state_store import sqlite_state_store


@dataclass(frozen=True)
class ModelInvocationResult:
    payload: dict | None
    warnings: list[str]


class ModelInvocationService:
    """Centralizes retry, circuit breaking, and privacy-safe model cost telemetry."""

    _namespace = "model_invocation_usage"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._usage = self._load_usage()
        self._circuits: dict[str, dict[str, float | int]] = {}

    def invoke_json(
        self,
        *,
        provider: str,
        model: str | None,
        endpoint: str,
        headers: dict[str, str],
        request_body: dict,
        timeout_seconds: float,
        estimate_usage: bool = True,
    ) -> ModelInvocationResult:
        normalized_provider = provider.strip() or "external_http"
        normalized_model = model.strip() if model else "unspecified"
        key = self._key(normalized_provider, normalized_model)
        if self._circuit_open(key):
            self._record(
                key,
                provider=normalized_provider,
                model=normalized_model,
                success=False,
                retries=0,
                circuit_rejection=True,
                input_tokens=0,
                output_tokens=0,
                estimated_usage=False,
            )
            return ModelInvocationResult(None, ["llm_agent_circuit_open"])

        attempts = settings.model_invocation_max_retries + 1
        retries = 0
        for attempt in range(attempts):
            try:
                request = Request(
                    endpoint,
                    data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
                    headers=headers,
                    method="POST",
                )
                with urlopen(request, timeout=timeout_seconds) as response:
                    response_body = json.loads(response.read().decode("utf-8"))
                if not isinstance(response_body, dict):
                    raise ValueError("model response must be an object")
            except HTTPError as error:
                if self._retryable_status(error.code) and attempt + 1 < attempts:
                    retries += 1
                    self._backoff(retries)
                    continue
                self._record_failure(key, normalized_provider, normalized_model, retries)
                return ModelInvocationResult(None, ["llm_agent_failed"])
            except (URLError, TimeoutError, OSError, ValueError):
                if attempt + 1 < attempts:
                    retries += 1
                    self._backoff(retries)
                    continue
                self._record_failure(key, normalized_provider, normalized_model, retries)
                return ModelInvocationResult(None, ["llm_agent_failed"])

            input_tokens, output_tokens, estimated_usage = self._usage_tokens(
                request_body,
                response_body,
                estimate_usage=estimate_usage,
            )
            self._record(
                key,
                provider=normalized_provider,
                model=normalized_model,
                success=True,
                retries=retries,
                circuit_rejection=False,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_usage=estimated_usage,
            )
            warnings = ["llm_agent_retried"] if retries else []
            return ModelInvocationResult(response_body, warnings)

        return ModelInvocationResult(None, ["llm_agent_failed"])

    def summary(self) -> ModelUsageSummary:
        with self._lock:
            records = [
                ModelUsageRecord(
                    **value,
                    circuit_open=self._circuit_open(key),
                )
                for key, value in self._usage.items()
            ]
        records.sort(key=lambda item: item.updated_at, reverse=True)
        return ModelUsageSummary(
            generated_at=datetime.now(timezone.utc),
            request_count=sum(item.request_count for item in records),
            success_count=sum(item.success_count for item in records),
            failure_count=sum(item.failure_count for item in records),
            retry_count=sum(item.retry_count for item in records),
            circuit_rejection_count=sum(item.circuit_rejection_count for item in records),
            input_tokens=sum(item.input_tokens for item in records),
            output_tokens=sum(item.output_tokens for item in records),
            estimated_usage_count=sum(item.estimated_usage_count for item in records),
            estimated_cost_usd=round(sum(item.estimated_cost_usd for item in records), 8),
            price_configured=bool(
                settings.llm_agent_input_cost_per_million_usd
                or settings.llm_agent_output_cost_per_million_usd
            ),
            active_circuit_count=sum(1 for item in records if item.circuit_open),
            records=records,
        )

    def _record_failure(self, key: str, provider: str, model: str, retries: int) -> None:
        self._record(
            key,
            provider=provider,
            model=model,
            success=False,
            retries=retries,
            circuit_rejection=False,
            input_tokens=0,
            output_tokens=0,
            estimated_usage=False,
        )

    def _record(
        self,
        key: str,
        *,
        provider: str,
        model: str,
        success: bool,
        retries: int,
        circuit_rejection: bool,
        input_tokens: int,
        output_tokens: int,
        estimated_usage: bool,
    ) -> None:
        with self._lock:
            now = datetime.now(timezone.utc)
            current = self._usage.get(key, self._empty_record(provider, model, now))
            cost = (
                input_tokens * settings.llm_agent_input_cost_per_million_usd
                + output_tokens * settings.llm_agent_output_cost_per_million_usd
            ) / 1_000_000
            updated = {
                **current,
                "request_count": int(current["request_count"]) + 1,
                "success_count": int(current["success_count"]) + int(success),
                "failure_count": int(current["failure_count"]) + int(not success and not circuit_rejection),
                "retry_count": int(current["retry_count"]) + retries,
                "circuit_rejection_count": int(current["circuit_rejection_count"]) + int(circuit_rejection),
                "input_tokens": int(current["input_tokens"]) + input_tokens,
                "output_tokens": int(current["output_tokens"]) + output_tokens,
                "estimated_usage_count": int(current["estimated_usage_count"]) + int(estimated_usage),
                "estimated_cost_usd": round(float(current["estimated_cost_usd"]) + cost, 8),
                "updated_at": now,
            }
            self._usage[key] = updated
            circuit = self._circuits.setdefault(key, {"failures": 0, "open_until": 0.0})
            if success:
                circuit["failures"] = 0
                circuit["open_until"] = 0.0
            elif not circuit_rejection:
                circuit["failures"] = int(circuit["failures"]) + 1
                if circuit["failures"] >= settings.model_invocation_circuit_failure_threshold:
                    circuit["open_until"] = time.monotonic() + settings.model_invocation_circuit_reset_seconds
            self._persist()

    def _circuit_open(self, key: str) -> bool:
        with self._lock:
            circuit = self._circuits.get(key)
            if not circuit:
                return False
            return float(circuit["open_until"]) > time.monotonic()

    @staticmethod
    def _retryable_status(status_code: int) -> bool:
        return status_code in {408, 429} or status_code >= 500

    @staticmethod
    def _usage_tokens(
        request_body: dict,
        response_body: dict,
        *,
        estimate_usage: bool,
    ) -> tuple[int, int, bool]:
        usage = response_body.get("usage")
        if isinstance(usage, dict):
            input_tokens = usage.get("prompt_tokens", usage.get("input_tokens"))
            output_tokens = usage.get("completion_tokens", usage.get("output_tokens"))
            if isinstance(input_tokens, int) and isinstance(output_tokens, int):
                return max(0, input_tokens), max(0, output_tokens), False
        if not estimate_usage:
            return 0, 0, False
        return (
            max(1, math.ceil(len(json.dumps(request_body, ensure_ascii=False)) / 4)),
            max(1, math.ceil(len(json.dumps(response_body, ensure_ascii=False)) / 4)),
            True,
        )

    def _backoff(self, retry_number: int) -> None:
        time.sleep(settings.model_invocation_retry_base_seconds * (2 ** max(0, retry_number - 1)))

    @staticmethod
    def _key(provider: str, model: str) -> str:
        return f"{provider}:{model}"

    @staticmethod
    def _empty_record(provider: str, model: str, now: datetime) -> dict:
        return {
            "provider": provider,
            "model": model,
            "request_count": 0,
            "success_count": 0,
            "failure_count": 0,
            "retry_count": 0,
            "circuit_rejection_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "estimated_usage_count": 0,
            "estimated_cost_usd": 0.0,
            "updated_at": now,
        }

    def _load_usage(self) -> dict[str, dict]:
        payload = sqlite_state_store.load_json(
            self._namespace,
            settings.local_model_usage_path,
            owner_id=SYSTEM_OWNER_ID,
        )
        if not isinstance(payload, dict) or not isinstance(payload.get("records"), list):
            return {}
        records: dict[str, dict] = {}
        for item in payload["records"]:
            try:
                record = ModelUsageRecord.model_validate(item)
            except (TypeError, ValueError):
                continue
            records[self._key(record.provider, record.model)] = record.model_dump(
                exclude={"circuit_open"}
            )
        return records

    def _persist(self) -> None:
        sqlite_state_store.save_json(
            self._namespace,
            {"records": list(self._usage.values())},
            owner_id=SYSTEM_OWNER_ID,
        )


model_invocation_service = ModelInvocationService()
