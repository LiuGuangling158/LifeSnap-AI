from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url

    def request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, Any]:
        data = None
        request_headers = headers.copy() if headers else {}
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            request_headers["Content-Type"] = "application/json"

        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers=request_headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                body = response.read().decode("utf-8")
                return response.status, json.loads(body) if body else None
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            return exc.code, json.loads(body) if body else None

    def upload_png(self) -> tuple[int, Any]:
        boundary = "----LifeSnapSmokeBoundary"
        body = b"".join(
            [
                f"--{boundary}\r\n".encode(),
                b'Content-Disposition: form-data; name="file"; filename="receipt.png"\r\n',
                b"Content-Type: image/png\r\n\r\n",
                b"fake-image-bytes",
                f"\r\n--{boundary}--\r\n".encode(),
            ]
        )
        request = urllib.request.Request(
            f"{self.base_url}/attachments/upload",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))


def main() -> int:
    port = _free_port()
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=BACKEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    client = ApiClient(f"http://127.0.0.1:{port}")

    try:
        _wait_until_ready(client)
        _run_checks(client)
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()

    print("Smoke test passed")
    return 0


def _run_checks(client: ApiClient) -> None:
    _check_health(client)
    _check_chat_task_candidate_confirmation(client)
    _check_bill_idempotency(client)
    _check_task_snooze_idempotency(client)
    _check_privacy_switch(client)
    _check_ocr_fallback_flow(client)
    _check_data_export_and_clear(client)


def _check_health(client: ApiClient) -> None:
    status, body = client.request("GET", "/health")
    _assert(status == 200, "GET /health should return 200")
    _assert(body["status"] == "ok", "GET /health should return ok")


def _check_chat_task_candidate_confirmation(client: ApiClient) -> None:
    message = "\u660e\u5929\u4e0b\u5348 3 \u70b9\u63d0\u9192\u6211\u53bb\u533b\u9662\u590d\u8bca"
    status, body = client.request("POST", "/chat/messages", {"message": message})
    _assert(status == 200, "POST /chat/messages should return 200")
    _assert(body["intent"] == "create_task", "Chat should create a task candidate")

    candidate_id = body["candidate_id"]
    headers = {"Idempotency-Key": "smoke-confirm-task-001"}
    status, first = client.request(
        "POST",
        f"/agent/task-candidates/{candidate_id}/confirm",
        headers=headers,
    )
    status_again, second = client.request(
        "POST",
        f"/agent/task-candidates/{candidate_id}/confirm",
        headers=headers,
    )
    _assert(status == 200 and status_again == 200, "Candidate confirmation should be repeatable")
    _assert(first["id"] == second["id"], "Repeated confirmation should return the first task")


def _check_bill_idempotency(client: ApiClient) -> None:
    payload = {
        "amount": 18.5,
        "merchant": "\u65e9\u9910\u5e97",
        "category": "\u9910\u996e",
        "transaction_type": "expense",
        "source": "manual",
    }
    headers = {"Idempotency-Key": "smoke-bill-001"}
    status, first = client.request("POST", "/bills", payload, headers=headers)
    status_again, second = client.request("POST", "/bills", payload, headers=headers)
    _assert(status == 201 and status_again == 201, "Repeated bill create should return 201")
    _assert(first["id"] == second["id"], "Repeated bill create should return the first bill")

    conflict_payload = payload | {"amount": 19}
    conflict_status, _ = client.request("POST", "/bills", conflict_payload, headers=headers)
    _assert(conflict_status == 409, "Same Idempotency-Key with different payload should conflict")


def _check_task_snooze_idempotency(client: ApiClient) -> None:
    payload = {
        "title": "\u533b\u9662\u590d\u8bca",
        "category": "\u533b\u7597",
        "task_type": "reminder",
        "remind_at": "2026-08-02T15:00:00+08:00",
        "source": "manual",
    }
    status, task = client.request(
        "POST",
        "/tasks",
        payload,
        headers={"Idempotency-Key": "smoke-task-001"},
    )
    _assert(status == 201, "POST /tasks should create a task")

    headers = {"Idempotency-Key": "smoke-snooze-001"}
    status, first = client.request(
        "POST",
        f"/tasks/{task['id']}/snooze",
        {"minutes": 30},
        headers=headers,
    )
    status_again, second = client.request(
        "POST",
        f"/tasks/{task['id']}/snooze",
        {"minutes": 30},
        headers=headers,
    )
    _assert(status == 200 and status_again == 200, "Repeated snooze should return 200")
    _assert(
        first["remind_at"] == second["remind_at"] == "2026-08-02T15:30:00+08:00",
        "Repeated snooze should not move the reminder twice",
    )


def _check_privacy_switch(client: ApiClient) -> None:
    status, _ = client.request(
        "PATCH",
        "/settings/privacy",
        {"allow_ai_text_processing": False},
    )
    _assert(status == 200, "PATCH /settings/privacy should return 200")

    message = "\u660e\u5929 9 \u70b9\u63d0\u9192\u6211\u4ea4\u623f\u79df"
    status, body = client.request("POST", "/chat/messages", {"message": message})
    _assert(status == 200, "Disabled AI chat should still return a handled response")
    _assert(
        body["warnings"] == ["ai_text_processing_disabled"],
        "Disabled AI chat should expose a stable warning",
    )

    status, _ = client.request(
        "PATCH",
        "/settings/privacy",
        {"allow_ai_text_processing": True},
    )
    _assert(status == 200, "AI text processing should be re-enabled")


def _check_ocr_fallback_flow(client: ApiClient) -> None:
    status, attachment = client.upload_png()
    _assert(status == 201, "Attachment upload should return 201")

    attachment_id = attachment["id"]
    status, body = client.request("POST", "/ocr/recognize", {"attachment_id": attachment_id})
    _assert(status == 200, "OCR fallback should return 200")
    _assert(body["status"] == "manual_required", "Missing OCR text should require manual entry")

    ocr_text = "\u745e\u5e78\u5496\u5561\n\u5fae\u4fe1\u652f\u4ed8\n\u5b9e\u4ed8 18.50 \u5143"
    status, _ = client.request(
        "PATCH",
        f"/attachments/{attachment_id}/ocr-text",
        {"ocr_text": ocr_text},
    )
    _assert(status == 200, "OCR text update should return 200")

    status, body = client.request("POST", "/ocr/recognize", {"attachment_id": attachment_id})
    _assert(status == 200, "Stored OCR recognize should return 200")
    _assert(body["status"] == "recognized", "Stored OCR text should be recognized")


def _check_data_export_and_clear(client: ApiClient) -> None:
    status, body = client.request("GET", "/data/export")
    _assert(status == 200, "GET /data/export should return 200")
    _assert(body["bills"], "Data export should include created bills")
    _assert(body["tasks"], "Data export should include created tasks")

    status, body = client.request("POST", "/data/clear", {"include_bills": True})
    _assert(status == 400, "Data clear should require explicit confirmation")
    _assert(body["detail"] == "Set confirm to true before clearing local data", "Clear guard message changed")

    status, body = client.request("POST", "/data/clear", {"confirm": True})
    _assert(status == 200, "Confirmed data clear should return 200")
    _assert(body["after"]["bill_count"] == 0, "Bills should be cleared")
    _assert(body["after"]["task_count"] == 0, "Tasks should be cleared")


def _wait_until_ready(client: ApiClient) -> None:
    for _ in range(40):
        try:
            status, _ = client.request("GET", "/health")
            if status == 200:
                return
        except Exception:
            time.sleep(0.25)
    raise RuntimeError("Server did not become ready")


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


if __name__ == "__main__":
    raise SystemExit(main())
