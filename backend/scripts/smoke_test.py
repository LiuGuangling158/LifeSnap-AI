from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


BACKEND_DIR = Path(__file__).resolve().parents[1]
LOCAL_TZ = timezone(timedelta(hours=8))


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
                return response.status, self._parse_body(body)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            return exc.code, self._parse_body(body)

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

    def _parse_body(self, body: str) -> Any:
        if not body:
            return None
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return body


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
            "--no-access-log",
            "--log-level",
            "warning",
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
    _check_candidate_discard_flow(client)
    _check_chat_task_candidate_confirmation(client)
    _check_bill_idempotency(client)
    _check_bill_candidate_duplicate_detection(client)
    _check_task_snooze_idempotency(client)
    _check_privacy_switch(client)
    _check_attachment_duplicate_detection(client)
    _check_ocr_fallback_flow(client)
    _check_dashboard_summary(client)
    _check_data_export_and_clear(client)


def _check_health(client: ApiClient) -> None:
    status, body = client.request("GET", "/health")
    _assert(status == 200, "GET /health should return 200")
    _assert(body["status"] == "ok", "GET /health should return ok")


def _check_candidate_discard_flow(client: ApiClient) -> None:
    status, bill_candidate = client.request(
        "POST",
        "/agent/parse-bill",
        {
            "text": "\u4fbf\u5229\u5e97\n\u5b9e\u4ed8 9 \u5143",
            "source": "ai_chat",
        },
    )
    _assert(status == 200, "Discard setup bill candidate should be parsed")
    bill_candidate_id = bill_candidate["candidate_id"]

    status, _ = client.request("DELETE", f"/agent/bill-candidates/{bill_candidate_id}")
    _assert(status == 204, "Bill candidate discard should return 204")

    status, _ = client.request("GET", f"/agent/bill-candidates/{bill_candidate_id}")
    _assert(status == 404, "Discarded bill candidate should not be readable")

    status, chat_bill_candidate = client.request(
        "POST",
        "/agent/parse-bill",
        {
            "text": "\u9762\u5305\u5e97\n\u5b9e\u4ed8 12 \u5143",
            "source": "ai_chat",
        },
    )
    _assert(status == 200, "Chat discard bill candidate should be parsed")
    chat_bill_candidate_id = chat_bill_candidate["candidate_id"]
    headers = {"Idempotency-Key": "smoke-chat-discard-bill-001"}
    discard_payload = {
        "action_type": "bill_candidate",
        "candidate_id": chat_bill_candidate_id,
    }
    status, first_discard = client.request(
        "POST",
        "/chat/discard-action",
        discard_payload,
        headers=headers,
    )
    status_again, second_discard = client.request(
        "POST",
        "/chat/discard-action",
        discard_payload,
        headers=headers,
    )
    _assert(
        status == 200 and status_again == 200,
        "Repeated chat bill discard should return 200",
    )
    _assert(
        first_discard["candidate_id"] == second_discard["candidate_id"],
        "Repeated chat bill discard should return the first discard result",
    )
    _assert(first_discard["discarded"], "Chat bill discard should mark discarded")

    status, _ = client.request("GET", f"/agent/bill-candidates/{chat_bill_candidate_id}")
    _assert(status == 404, "Chat-discarded bill candidate should not be readable")

    status, task_candidate = client.request(
        "POST",
        "/agent/parse-task",
        {
            "text": "\u660e\u5929 8 \u70b9\u63d0\u9192\u6211\u53d6\u5feb\u9012",
            "source": "ai_chat",
        },
    )
    _assert(status == 200, "Discard setup task candidate should be parsed")
    task_candidate_id = task_candidate["candidate_id"]

    status, _ = client.request("DELETE", f"/agent/task-candidates/{task_candidate_id}")
    _assert(status == 204, "Task candidate discard should return 204")

    status, _ = client.request("GET", f"/agent/task-candidates/{task_candidate_id}")
    _assert(status == 404, "Discarded task candidate should not be readable")

    status, chat_task_candidate = client.request(
        "POST",
        "/agent/parse-task",
        {
            "text": "\u660e\u5929 10 \u70b9\u63d0\u9192\u6211\u4e70\u725b\u5976",
            "source": "ai_chat",
        },
    )
    _assert(status == 200, "Chat discard task candidate should be parsed")
    chat_task_candidate_id = chat_task_candidate["candidate_id"]
    status, discarded_task = client.request(
        "POST",
        "/chat/discard-action",
        {
            "action_type": "task_candidate",
            "candidate_id": chat_task_candidate_id,
        },
    )
    _assert(status == 200, "Chat task discard should return 200")
    _assert(discarded_task["discarded"], "Chat task discard should mark discarded")

    status, _ = client.request("GET", f"/agent/task-candidates/{chat_task_candidate_id}")
    _assert(status == 404, "Chat-discarded task candidate should not be readable")


def _check_chat_task_candidate_confirmation(client: ApiClient) -> None:
    message = "\u660e\u5929\u4e0b\u5348 3 \u70b9\u63d0\u9192\u6211\u53bb\u533b\u9662\u590d\u8bca"
    status, body = client.request("POST", "/chat/messages", {"message": message})
    _assert(status == 200, "POST /chat/messages should return 200")
    _assert(body["intent"] == "create_task", "Chat should create a task candidate")

    candidate_id = body["candidate_id"]
    status, patched = client.request(
        "PATCH",
        f"/agent/task-candidates/{candidate_id}",
        {"priority": "high"},
    )
    _assert(status == 200, "Task candidate partial update should return 200")
    _assert(
        patched["data"]["priority"] == "high",
        "Task candidate partial update should apply provided fields",
    )
    status, task_candidates = client.request("GET", "/agent/task-candidates")
    _assert(status == 200, "Task candidate list should return 200")
    _assert(
        any(candidate["candidate_id"] == candidate_id for candidate in task_candidates["items"]),
        "Task candidate list should include the pending candidate",
    )

    status, confirmable_candidates = client.request(
        "GET",
        "/agent/candidates?confirmable_only=true",
    )
    _assert(status == 200, "Unified confirmable candidate list should return 200")
    _assert(
        any(
            candidate["candidate_id"] == candidate_id
            for candidate in confirmable_candidates["task_candidates"]
        ),
        "Unified candidate list should include the confirmable task candidate",
    )

    headers = {"Idempotency-Key": "smoke-confirm-task-001"}
    confirm_payload = {
        "action_type": "task_candidate",
        "candidate_id": candidate_id,
    }
    status, first = client.request(
        "POST",
        "/chat/confirm-action",
        confirm_payload,
        headers=headers,
    )
    status_again, second = client.request(
        "POST",
        "/chat/confirm-action",
        confirm_payload,
        headers=headers,
    )
    _assert(status == 200 and status_again == 200, "Candidate confirmation should be repeatable")
    _assert(
        first["created_task"]["id"] == second["created_task"]["id"],
        "Repeated confirmation should return the first task",
    )
    _assert(first["action_type"] == "task_candidate", "Chat confirmation should keep action type")

    status, task_candidates = client.request("GET", "/agent/task-candidates")
    _assert(status == 200, "Task candidate list after confirmation should return 200")
    _assert(
        all(candidate["candidate_id"] != candidate_id for candidate in task_candidates["items"]),
        "Confirmed task candidate should leave the pending candidate list",
    )


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


def _check_bill_candidate_duplicate_detection(client: ApiClient) -> None:
    payload = {
        "amount": 21,
        "merchant": "\u5496\u5561\u5e97",
        "category": "\u9910\u996e",
        "payment_method": "\u5fae\u4fe1\u652f\u4ed8",
        "transaction_type": "expense",
        "paid_at": "2026-08-01T09:00:00+08:00",
        "source": "manual",
    }
    status, bill = client.request(
        "POST",
        "/bills",
        payload,
        headers={"Idempotency-Key": "smoke-candidate-duplicate-bill"},
    )
    _assert(status == 201, "Duplicate setup bill should be created")

    status, candidate = client.request(
        "POST",
        "/agent/parse-bill",
        {
            "text": "\u5496\u5561\u5e97\n\u5fae\u4fe1\u652f\u4ed8\n\u5b9e\u4ed8 21 \u5143",
            "source": "ai_chat",
        },
    )
    _assert(status == 200, "Bill candidate should be parsed")

    status, candidate = client.request(
        "PATCH",
        f"/agent/bill-candidates/{candidate['candidate_id']}",
        {
            "amount": payload["amount"],
            "merchant": payload["merchant"],
            "category": payload["category"],
            "payment_method": payload["payment_method"],
            "paid_at": payload["paid_at"],
        },
    )
    _assert(status == 200, "Bill candidate should be editable")

    status, duplicate = client.request(
        "POST",
        f"/agent/bill-candidates/{candidate['candidate_id']}/check-duplicate",
    )
    _assert(status == 200, "Bill candidate duplicate check should return 200")
    _assert(duplicate["is_duplicate"], "Bill candidate duplicate check should find a match")
    _assert(
        duplicate["matches"][0]["bill"]["id"] == bill["id"],
        "Bill candidate duplicate check should include the matching bill",
    )

    status, bill_candidates = client.request(
        "GET",
        "/agent/bill-candidates?confirmable_only=true",
    )
    _assert(status == 200, "Bill candidate list should return 200")
    _assert(
        any(
            item["candidate_id"] == candidate["candidate_id"]
            for item in bill_candidates["items"]
        ),
        "Bill candidate list should include the confirmable bill candidate",
    )


def _check_task_snooze_idempotency(client: ApiClient) -> None:
    remind_at = (datetime.now(LOCAL_TZ) + timedelta(days=1)).replace(
        second=0,
        microsecond=0,
    )
    expected_remind_at = (remind_at + timedelta(minutes=30)).isoformat()
    payload = {
        "title": "\u533b\u9662\u590d\u8bca",
        "category": "\u533b\u7597",
        "task_type": "reminder",
        "remind_at": remind_at.isoformat(),
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
        first["remind_at"] == second["remind_at"] == expected_remind_at,
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


def _check_attachment_duplicate_detection(client: ApiClient) -> None:
    first_status, first = client.upload_png()
    second_status, second = client.upload_png()
    _assert(first_status == 201 and second_status == 201, "Duplicate upload setup should work")
    _assert(
        second["duplicate_of"] == first["id"],
        "Second upload of the same bytes should point at the first attachment",
    )

    status, duplicates = client.request("GET", f"/attachments/{second['id']}/duplicates")
    _assert(status == 200, "Duplicate query should return 200")
    _assert(duplicates["is_duplicate"], "Duplicate query should mark duplicate attachments")
    _assert(duplicates["duplicate_count"] == 1, "Duplicate query should include one match")
    _assert(
        duplicates["matches"][0]["id"] == first["id"],
        "Duplicate query should include the original attachment",
    )


def _check_ocr_fallback_flow(client: ApiClient) -> None:
    status, attachment = client.upload_png()
    _assert(status == 201, "Attachment upload should return 201")

    attachment_id = attachment["id"]
    status, body = client.request("POST", "/ocr/recognize", {"attachment_id": attachment_id})
    _assert(status == 200, "OCR fallback should return 200")
    _assert(body["status"] == "manual_required", "Missing OCR text should require manual entry")

    status, flow = client.request(
        "POST",
        f"/attachments/{attachment_id}/recognize-and-parse-bill",
    )
    _assert(status == 200, "Attachment recognize-and-parse fallback should return 200")
    _assert(
        flow["status"] == "manual_required" and flow["manual_entry_required"],
        "Attachment recognize-and-parse should request manual entry when OCR is missing",
    )

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

    status, flow = client.request(
        "POST",
        f"/attachments/{attachment_id}/recognize-and-parse-bill",
    )
    _assert(status == 200, "Attachment recognize-and-parse should return 200")
    _assert(
        flow["status"] == "candidate_created",
        "Attachment recognize-and-parse should create a bill candidate from stored OCR text",
    )
    _assert(
        flow["candidate"]["data"]["merchant"] == "\u745e\u5e78\u5496\u5561",
        "Attachment recognize-and-parse should include parsed bill candidate data",
    )


def _check_dashboard_summary(client: ApiClient) -> None:
    status, dashboard = client.request(
        "GET",
        "/dashboard/summary?recent_bill_limit=3&candidate_limit=3",
    )
    _assert(status == 200, "GET /dashboard/summary should return 200")
    _assert(
        dashboard["data_summary"]["bill_count"] >= 1,
        "Dashboard summary should include local data counts",
    )
    _assert(
        dashboard["monthly_statistics"]["bill_count"] >= 1,
        "Dashboard summary should include monthly bill statistics",
    )
    _assert(dashboard["recent_bills"], "Dashboard summary should include recent bills")
    _assert(
        dashboard["pending_bill_candidates"],
        "Dashboard summary should include pending bill candidates",
    )
    _assert(
        dashboard["recent_bill_count"] == len(dashboard["recent_bills"]),
        "Dashboard recent bill count should match returned rows",
    )


def _check_data_export_and_clear(client: ApiClient) -> None:
    status, task_candidate = client.request(
        "POST",
        "/agent/parse-task",
        {
            "text": "\u660e\u5929 11 \u70b9\u63d0\u9192\u6211\u6253\u7535\u8bdd\u9884\u7ea6\u4f53\u68c0",
            "source": "ai_chat",
        },
    )
    _assert(status == 200, "Data export setup task candidate should be parsed")

    status, body = client.request("GET", "/data/export")
    _assert(status == 200, "GET /data/export should return 200")
    _assert(body["bills"], "Data export should include created bills")
    _assert(body["tasks"], "Data export should include created tasks")
    _assert(body["bill_candidates"], "Data export should include bill candidates")
    _assert(body["task_candidates"], "Data export should include task candidates")

    status, bills_csv = client.request("GET", "/data/export/bills.csv")
    _assert(status == 200, "GET /data/export/bills.csv should return 200")
    _assert("merchant" in bills_csv and "\u65e9\u9910\u5e97" in bills_csv, "Bills CSV should include bill rows")

    status, tasks_csv = client.request("GET", "/data/export/tasks.csv")
    _assert(status == 200, "GET /data/export/tasks.csv should return 200")
    _assert("title" in tasks_csv and "\u533b\u9662\u590d\u8bca" in tasks_csv, "Tasks CSV should include task rows")

    status, attachments_csv = client.request("GET", "/data/export/attachments.csv")
    _assert(status == 200, "GET /data/export/attachments.csv should return 200")
    _assert(
        "checksum" in attachments_csv and "receipt.png" in attachments_csv,
        "Attachments CSV should include attachment metadata",
    )

    status, bill_candidates_csv = client.request(
        "GET",
        "/data/export/bill-candidates.csv",
    )
    _assert(status == 200, "GET /data/export/bill-candidates.csv should return 200")
    _assert(
        "candidate_id" in bill_candidates_csv and "\u5496\u5561\u5e97" in bill_candidates_csv,
        "Bill candidates CSV should include pending bill candidate rows",
    )

    status, task_candidates_csv = client.request(
        "GET",
        "/data/export/task-candidates.csv",
    )
    _assert(status == 200, "GET /data/export/task-candidates.csv should return 200")
    _assert(
        "candidate_id" in task_candidates_csv
        and task_candidate["candidate_id"] in task_candidates_csv,
        "Task candidates CSV should include pending task candidate rows",
    )

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
