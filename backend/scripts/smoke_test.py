from __future__ import annotations

import csv
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
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
    with TemporaryDirectory(prefix="lifesnap-smoke-") as data_dir:
        return _run_isolated_smoke(data_dir)


def _run_isolated_smoke(data_dir: str) -> int:
    test_env = os.environ.copy()
    test_env["LIFESNAP_DATA_DIR"] = data_dir
    test_env["LIFESNAP_OCR_ENDPOINT"] = ""
    test_env["LIFESNAP_AI_PARSE_ENDPOINT"] = ""
    test_env["LIFESNAP_LLM_BASE_URL"] = ""
    test_env["LIFESNAP_LLM_API_KEY"] = ""
    test_env["LIFESNAP_LLM_MODEL"] = ""
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
        env=test_env,
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
            process.wait(timeout=5)

    print("Smoke test passed")
    return 0


def _run_checks(client: ApiClient) -> None:
    _check_health(client)
    _check_standard_error_responses(client)
    _check_demo_data_seed(client)
    _check_app_bootstrap(client)
    _check_agent_runtime_profile(client)
    _check_integration_diagnostics(client)
    _check_bill_statistics_overview(client)
    _check_task_statistics_overview(client)
    _check_candidate_discard_flow(client)
    _check_candidate_edit_flow(client)
    _check_chat_clarifying_questions(client)
    _check_workflow_regressions(client)
    _check_agent_context_workflow(client)
    _check_chat_task_candidate_confirmation(client)
    _check_chat_diary_reflection(client)
    _check_chat_diary_candidate_confirmation(client)
    _check_bill_idempotency(client)
    _check_soft_delete_and_restore(client)
    _check_bill_candidate_duplicate_detection(client)
    _check_task_snooze_idempotency(client)
    _check_privacy_switch(client)
    _check_category_settings(client)
    _check_budget_settings(client)
    _check_tag_settings(client)
    _check_attachment_duplicate_detection(client)
    _check_ocr_fallback_flow(client)
    _check_audit_log_and_request_id(client)
    _check_data_import_restore(client)
    _check_local_snapshot_persistence(client)
    _check_data_quality_diagnostics(client)
    _check_dashboard_summary(client)
    _check_data_export_and_clear(client)
    _check_diary_csv_export(client)


def _check_diary_csv_export(client: ApiClient) -> None:
    payload = {
        "entry_date": "2001-02-03",
        "title": '日记, "导出"',
        "content": '第一行,保留逗号\n第二行 "保留引号"',
        "mood": "calm",
        "weather": None,
        "tags": ["生活", "记录"],
    }
    status, diary = client.request("POST", "/diaries", payload)
    _assert(status == 201, "CSV fixture diary should be created")
    with urllib.request.urlopen(f"{client.base_url}/data/export/diaries.csv", timeout=5) as response:
        _assert(response.status == 200, "Diary CSV should return 200")
        _assert("text/csv" in response.headers["Content-Type"], "Diary export must be CSV")
        _assert("lifesnap-diaries.csv" in response.headers["Content-Disposition"], "CSV should be downloadable")
        rows = list(csv.DictReader(StringIO(response.read().decode("utf-8"))))
    row = next(item for item in rows if item["id"] == diary["id"])
    for field in ("entry_date", "title", "content", "mood"):
        _assert(row[field] == payload[field], f"Diary CSV should preserve {field}")
    _assert(row["tags"] == "生活;记录", "Diary CSV should export tags")
    _assert(row["weather"] == "", "Null weather should be empty")
    _assert(row["source"] == "manual", "Diary source should use the enum value")
    status, _ = client.request("DELETE", f"/diaries/{diary['id']}")
    _assert(status == 204, "CSV fixture should be soft-deleted")
    status, exported = client.request("GET", "/data/export/diaries.csv")
    _assert(status == 200, "Diary CSV should still work after deletion")
    rows = list(csv.DictReader(StringIO(exported)))
    _assert(all(item["id"] != diary["id"] for item in rows), "Deleted diaries must not be exported")


def _check_health(client: ApiClient) -> None:
    status, body = client.request("GET", "/health")
    _assert(status == 200, "GET /health should return 200")
    _assert(body["status"] == "ok", "GET /health should return ok")


def _check_workflow_regressions(client: ApiClient) -> None:
    fixtures = [
        ("/bills", {"amount": "28", "transaction_type": "expense", "note": "editable"},
         ["amount", "currency", "category", "transaction_type", "source", "paid_at"], "merchant"),
        ("/tasks", {"title": "Meeting", "description": "editable"},
         ["title", "category", "task_type", "status", "priority", "source"], "description"),
        ("/diaries", {"entry_date": "2002-03-04", "title": "Day", "content": "Notes", "weather": "Sunny"},
         ["entry_date", "title", "content", "mood", "source", "attachment_ids", "tags"], "weather"),
    ]
    for path, payload, required_fields, nullable_field in fixtures:
        status, created = client.request("POST", path, payload)
        _assert(status == 201, f"{path} fixture should be created")
        item_path = f"{path}/{created['id']}"
        for field in required_fields:
            status, error = client.request("PATCH", item_path, {field: None})
            _assert(status == 422, f"{path}.{field} null must be rejected before saving")
            _assert(error["error"]["code"] == "validation_error", "Use the standard validation response")
        status, unchanged = client.request("GET", item_path)
        _assert(unchanged == created, "Rejected updates must not mutate the saved record")
        status, updated = client.request("PATCH", item_path, {nullable_field: None})
        _assert(status == 200 and updated[nullable_field] is None, "Optional fields must remain clearable")
        client.request("DELETE", item_path)

    for message, intent, transaction_type, category in [
        ("今天点了咖啡 28 元", "create_bill", "expense", "餐饮"),
        ("今天打车去公司 36 元", "create_bill", "expense", "交通"),
        ("工资收入 6800 元", "create_bill", "income", "工资"),
        ("商店退款 28 元", "create_bill", "refund", None),
        ("提醒我明天 10 点支付 28 元", "create_task", None, None),
    ]:
        status, result = client.request("POST", "/chat/messages", {"message": message})
        _assert(status == 200 and result["intent"] == intent, f"Incorrect routing for {message}")
        if transaction_type is not None:
            _assert(result["candidate"]["data"]["transaction_type"] == transaction_type, "Preserve transaction meaning")
        if category is not None:
            _assert(result["candidate"]["data"]["category"] == category, f"Infer bill category for {message}")
        client.request("POST", "/chat/discard-action", {
            "action_type": result["action_type"], "candidate_id": result["candidate_id"],
        })

    for message, category in [
        ("淘宝买衣服 199 元", "购物"),
        ("超市买纸巾 18 元", "日用"),
        ("药店买药 48 元", "医疗"),
        ("电影票 80 元", "娱乐"),
        ("Python 课程 99 元", "学习"),
        ("房租 2800 元", "住房"),
    ]:
        status, candidate = client.request(
            "POST",
            "/agent/parse-bill",
            {"text": message, "source": "ai_chat"},
        )
        _assert(status == 200, f"Category candidate should parse for {message}")
        _assert(candidate["data"]["category"] == category, f"Infer {category} for {message}")
        client.request("DELETE", f"/agent/bill-candidates/{candidate['candidate_id']}")

    status, candidate = client.request("POST", "/agent/parse-bill", {"text": "Cafe\n0 元"})
    _assert(status == 200 and candidate["data"]["amount"] is None, "Zero amounts should need clarification")
    candidate_path = f"/agent/bill-candidates/{candidate['candidate_id']}"
    for payload in ({"currency": None}, {"category": None}, {"amount": -1}):
        status, _ = client.request("PATCH", candidate_path, payload)
        _assert(status == 422, "Invalid candidate edits must be rejected")
    status, _ = client.request("PATCH", candidate_path, {"amount": "28"})
    _assert(status == 200, "Candidate should remain editable after validation errors")
    action = {"action_type": "bill_candidate", "candidate_id": candidate["candidate_id"]}
    headers = {"Idempotency-Key": f"workflow-confirm-{candidate['candidate_id']}"}
    status, first = client.request("POST", "/chat/confirm-action", action, headers)
    _assert(status == 200, "Corrected candidate should confirm")
    status, replay = client.request("POST", "/chat/confirm-action", action, headers)
    _assert(status == 200 and replay == first, "Retry must return the original confirmation")

    status, minimal_candidate = client.request("POST", "/agent/parse-bill", {"text": "28 元", "source": "ai_chat"})
    _assert(status == 200, "Minimal bill candidate should parse")
    _assert(minimal_candidate["data"]["merchant"] is None, "Merchant should be optional for candidates")
    status, minimal_bill = client.request("POST", "/chat/confirm-action", {
        "action_type": "bill_candidate", "candidate_id": minimal_candidate["candidate_id"],
    })
    _assert(status == 200, "Bill candidate with amount and type only should confirm")
    _assert(minimal_bill["created_bill"]["merchant"] is None, "Saved bill should allow empty merchant")
    client.request("DELETE", f"/bills/{minimal_bill['created_bill']['id']}")


def _check_agent_context_workflow(client: ApiClient) -> None:
    status, bill_body = client.request("POST", "/chat/messages", {"message": "记一笔早餐"})
    _assert(status == 200 and bill_body["intent"] == "create_bill", "Agent should start a bill candidate")
    _assert_agent_function_calls(
        bill_body,
        {"privacy_guard", "knowledge_search", "route_chat_intent", "parse_bill_candidate", "classify_bill_category"},
        "Agent bill context setup",
    )
    bill_candidate_id = bill_body["candidate_id"]
    _assert(bill_body["candidate"]["data"]["amount"] is None, "Bill candidate should wait for amount")

    status, updated_bill = client.request(
        "POST",
        "/chat/messages",
        {
            "message": "金额 18 元，商家是便利蜂，用支付宝，分类餐饮",
            "context_action_type": "bill_candidate",
            "context_candidate_id": bill_candidate_id,
        },
    )
    _assert(status == 200, "Agent should update an existing bill candidate")
    _assert(updated_bill["updated_existing_candidate"] is True, "Bill update should be marked as contextual")
    _assert_agent_function_calls(
        updated_bill,
        {"privacy_guard", "knowledge_search", "route_chat_intent", "update_candidate"},
        "Agent bill context update",
    )
    _assert(updated_bill["candidate_id"] == bill_candidate_id, "Bill context update should keep candidate id")
    bill_data = updated_bill["candidate"]["data"]
    _assert(float(bill_data["amount"]) == 18, "Bill context update should fill amount")
    _assert(bill_data["merchant"] == "便利蜂", "Bill context update should fill merchant")
    _assert(bill_data["category"] == "餐饮", "Bill context update should fill category")
    _assert(bill_data["payment_method"] == "支付宝", "Bill context update should fill payment method")

    status, confirmed_bill = client.request(
        "POST",
        "/chat/messages",
        {
            "message": "确认保存",
            "context_action_type": "bill_candidate",
            "context_candidate_id": bill_candidate_id,
        },
    )
    _assert(status == 200, "Agent should confirm a bill candidate from chat context")
    _assert_agent_function_calls(
        confirmed_bill,
        {"privacy_guard", "knowledge_search", "route_chat_intent", "confirm_candidate"},
        "Agent bill context confirmation",
    )
    _assert(confirmed_bill["created_bill"]["merchant"] == "便利蜂", "Context-confirmed bill should be saved")
    status, _ = client.request("GET", f"/agent/bill-candidates/{bill_candidate_id}")
    _assert(status == 404, "Context-confirmed bill candidate should leave pending list")
    client.request("DELETE", f"/bills/{confirmed_bill['created_bill']['id']}")

    status, task_body = client.request("POST", "/chat/messages", {"message": "提醒我提交周报"})
    _assert(status == 200 and task_body["intent"] == "create_task", "Agent should start a task candidate")
    _assert_agent_function_calls(
        task_body,
        {"privacy_guard", "knowledge_search", "route_chat_intent", "parse_task_candidate"},
        "Agent task context setup",
    )
    task_candidate_id = task_body["candidate_id"]
    _assert(task_body["candidate"]["data"]["remind_at"] is None, "Reminder should wait for time")
    status, updated_task = client.request(
        "POST",
        "/chat/messages",
        {
            "message": "提醒时间是明天上午 9 点",
            "context_action_type": "task_candidate",
            "context_candidate_id": task_candidate_id,
        },
    )
    _assert(status == 200 and updated_task["updated_existing_candidate"] is True, "Agent should update reminder time")
    _assert_agent_function_calls(
        updated_task,
        {"privacy_guard", "knowledge_search", "route_chat_intent", "update_candidate"},
        "Agent task context update",
    )
    _assert(updated_task["candidate"]["data"]["remind_at"], "Reminder context update should fill remind_at")
    status, discarded_task = client.request(
        "POST",
        "/chat/messages",
        {
            "message": "不保存",
            "context_action_type": "task_candidate",
            "context_candidate_id": task_candidate_id,
        },
    )
    _assert(status == 200 and discarded_task["discarded"] is True, "Agent should discard a task candidate from chat context")
    _assert_agent_function_calls(
        discarded_task,
        {"privacy_guard", "knowledge_search", "route_chat_intent", "discard_candidate"},
        "Agent task context discard",
    )
    status, _ = client.request("GET", f"/agent/task-candidates/{task_candidate_id}")
    _assert(status == 404, "Context-discarded task candidate should leave pending list")

    status, diary_body = client.request(
        "POST",
        "/chat/messages",
        {"message": "写日记：今天完成项目复盘，心情很开心"},
    )
    _assert(status == 200 and diary_body["intent"] == "create_diary", "Agent should start a diary candidate")
    _assert_agent_function_calls(
        diary_body,
        {"privacy_guard", "knowledge_search", "route_chat_intent", "parse_diary_candidate"},
        "Agent diary context setup",
    )
    diary_candidate_id = diary_body["candidate_id"]
    status, updated_diary = client.request(
        "POST",
        "/chat/messages",
        {
            "message": "标题改成项目复盘完成，天气晴天，标签工作、成长",
            "context_action_type": "diary_candidate",
            "context_candidate_id": diary_candidate_id,
        },
    )
    _assert(status == 200 and updated_diary["updated_existing_candidate"] is True, "Agent should update diary metadata")
    _assert_agent_function_calls(
        updated_diary,
        {"privacy_guard", "knowledge_search", "route_chat_intent", "update_candidate"},
        "Agent diary context update",
    )
    diary_data = updated_diary["candidate"]["data"]
    _assert(diary_data["title"] == "项目复盘完成", "Diary context update should change title")
    _assert(diary_data["weather"] == "晴天", "Diary context update should change weather")
    _assert(diary_data["tags"] == ["工作", "成长"], "Diary context update should change tags")
    client.request("DELETE", f"/agent/diary-candidates/{diary_candidate_id}")




def _check_standard_error_responses(client: ApiClient) -> None:
    status, body = client.request(
        "GET",
        "/bills/00000000-0000-0000-0000-000000000000",
    )
    _assert(status == 404, "Standard 404 setup should return 404")
    _assert(body["detail"] == "Bill not found", "Standard 404 should preserve detail")
    _assert(body["error"]["code"] == "not_found", "Standard 404 should include error code")
    _assert(
        body["error"]["path"].endswith("/bills/00000000-0000-0000-0000-000000000000"),
        "Standard 404 should include request path",
    )
    _assert(body["error"]["request_id"], "Standard 404 should include request id")

    status, body = client.request(
        "GET",
        "/bills/00000000-0000-0000-0000-000000000000",
        headers={"X-Request-ID": "smoke-request-id-001"},
    )
    _assert(status == 404, "Custom request id setup should return 404")
    _assert(
        body["error"]["request_id"] == "smoke-request-id-001",
        "Error response should echo custom request id",
    )

    status, body = client.request("POST", "/data/clear", {"include_bills": True})
    _assert(status == 400, "Standard 400 setup should return 400")
    _assert(
        body["detail"] == "Set confirm to true before clearing local data",
        "Standard 400 should preserve detail",
    )
    _assert(body["error"]["code"] == "bad_request", "Standard 400 should include error code")

    status, body = client.request(
        "POST",
        "/bills",
        {
            "amount": -1,
            "merchant": "Invalid",
            "category": "Demo",
            "transaction_type": "expense",
            "source": "manual",
        },
    )
    _assert(status == 422, "Standard validation setup should return 422")
    _assert(
        body["error"]["code"] == "validation_error",
        "Standard validation response should include validation error code",
    )
    _assert(body["error"]["issues"], "Standard validation response should include issues")


def _check_demo_data_seed(client: ApiClient) -> None:
    payload = {
        "confirm": True,
        "reset_existing": True,
        "include_attachment": True,
        "include_candidates": True,
    }
    headers = {"Idempotency-Key": f"smoke-seed-demo-{time.time_ns()}"}
    status, first = client.request(
        "POST",
        "/data/seed-demo",
        payload,
        headers=headers,
    )
    status_again, second = client.request(
        "POST",
        "/data/seed-demo",
        payload,
        headers=headers,
    )
    _assert(status == 200 and status_again == 200, "Demo seed should be repeatable")
    _assert(first["after"]["bill_count"] == 3, "Demo seed should create demo bills")
    _assert(first["after"]["task_count"] == 2, "Demo seed should create demo tasks")
    _assert(first["after"]["attachment_count"] == 1, "Demo seed should create an attachment")
    _assert(
        first["after"]["bill_candidate_count"] == 1
        and first["after"]["task_candidate_count"] == 1
        and first["after"]["diary_candidate_count"] == 1,
        "Demo seed should create pending candidates",
    )
    _assert(
        first["created_bills"][0]["id"] == second["created_bills"][0]["id"],
        "Repeated demo seed should return the first result",
    )

    status, summary = client.request("GET", "/data/summary")
    _assert(status == 200, "Data summary after demo seed should return 200")
    _assert(
        summary["bill_count"] == first["after"]["bill_count"],
        "Demo seed idempotency should not duplicate bills",
    )


def _check_app_bootstrap(client: ApiClient) -> None:
    status, capabilities = client.request("GET", "/app/capabilities")
    _assert(status == 200, "GET /app/capabilities should return 200")
    _assert(capabilities["api_status"] == "ok", "App capabilities should report ok")
    _assert(
        "image/png" in capabilities["supported_attachment_content_types"],
        "App capabilities should expose supported attachment types",
    )
    _assert(
        capabilities["feature_flags"]["demo_data_seed"],
        "App capabilities should expose demo seed feature flag",
    )
    _assert(
        not capabilities["feature_flags"]["real_ocr_engine"],
        "App capabilities should expose unavailable real OCR feature",
    )
    _assert(
        capabilities["feature_flags"]["diary_candidates"],
        "App capabilities should expose diary candidate feature flag",
    )
    _assert(
        "POST /agent/diary-candidates/{candidate_id}/confirm" in capabilities["idempotency_supported_endpoints"],
        "App capabilities should expose diary candidate confirm idempotency",
    )
    tool_ids = {tool["id"] for tool in capabilities["assistant_tools"]}
    _assert(
        {"bill_candidate", "task_candidate", "diary_candidate", "diary_reflection", "attachment_bill_recognition"}
        <= tool_ids,
        "App capabilities should expose supported assistant tools",
    )

    status, bootstrap = client.request(
        "GET",
        "/app/bootstrap?recent_bill_limit=2&candidate_limit=2",
    )
    _assert(status == 200, "GET /app/bootstrap should return 200")
    _assert(
        bootstrap["privacy_settings"]["local_only_mode"],
        "App bootstrap should include privacy settings",
    )
    _assert(
        bootstrap["category_settings"]["bill_categories"],
        "App bootstrap should include category settings",
    )
    _assert(
        float(bootstrap["budget_settings"]["monthly_budget"]) >= 0,
        "App bootstrap should include budget settings",
    )
    _assert(
        bootstrap["tag_settings"]["tags"],
        "App bootstrap should include tag settings",
    )
    _assert(
        bootstrap["data_summary"]["bill_count"] >= 1,
        "App bootstrap should include data summary",
    )
    _assert(
        bootstrap["dashboard"]["recent_bill_count"] <= 2,
        "App bootstrap should pass dashboard recent bill limit",
    )
    _assert(
        bootstrap["capabilities"]["app_version"] == capabilities["app_version"],
        "App bootstrap should include the same capabilities version",
    )
    _assert(
        len(bootstrap["capabilities"]["assistant_tools"]) >= 4,
        "App bootstrap should include assistant tools",
    )


def _check_agent_runtime_profile(client: ApiClient) -> None:
    status, runtime = client.request("GET", "/agent/runtime")
    _assert(status == 200, "Agent runtime profile should return 200")
    _assert(runtime["rag_enabled"], "Agent runtime should expose RAG support")
    _assert(runtime["function_calling_enabled"], "Agent runtime should expose function calling support")
    _assert(runtime["fine_tuning_ready"], "Agent runtime should expose fine-tuning readiness")
    function_names = {tool["name"] for tool in runtime["function_tools"]}
    _assert(
        {"privacy_guard", "knowledge_search", "parse_bill_candidate", "classify_bill_category", "confirm_candidate"}
        <= function_names,
        "Agent runtime should expose core callable tools",
    )
    _assert(
        runtime["model_profile"]["rag_enabled"] and runtime["model_profile"]["function_calling_enabled"],
        "Agent model profile should include RAG and function calling flags",
    )

    status, hits = client.request("GET", "/agent/knowledge/search?q=RAG%20%E7%9F%A5%E8%AF%86%E5%BA%93%20%E5%BE%AE%E8%B0%83%20%E5%87%BD%E6%95%B0%E8%B0%83%E7%94%A8&limit=5")
    _assert(status == 200 and len(hits) >= 3, "Agent knowledge search should retrieve RAG documents")
    _assert(
        any(hit["source_id"] == "fine_tuning_policy" for hit in hits),
        "Agent knowledge search should include fine-tuning policy",
    )

    status, dataset = client.request("GET", "/agent/fine-tuning/examples?limit=5")
    _assert(status == 200, "Agent fine-tuning examples should return 200")
    _assert(dataset["total"] >= 1, "Agent fine-tuning dataset should use local records")
    _assert(dataset["examples"][0]["messages"], "Agent fine-tuning examples should include messages")
    target_content = dataset["examples"][0]["messages"][-1]["content"]
    _assert("created_at" not in target_content and "updated_at" not in target_content, "Fine-tuning examples should export candidate targets, not storage metadata")

    status, answer = client.request(
        "POST",
        "/chat/messages",
        {"message": "你有 RAG 知识库、函数调用和大模型微调吗？"},
    )
    _assert(status == 200, "Agent capability chat should return 200")
    _assert(answer["intent"] == "knowledge_answer", "Agent should answer capability questions from knowledge")
    _assert(answer["knowledge_hits"], "Agent capability answer should expose knowledge hits")
    _assert_agent_function_calls(answer, {"privacy_guard", "knowledge_search"}, "Agent capability chat")
    _assert(answer["model_trace"]["fine_tuning_status"], "Agent chat should expose model/fine-tuning trace")

    status, bill_answer = client.request(
        "POST",
        "/chat/messages",
        {"message": "星巴克咖啡花了 38 元"},
    )
    _assert(status == 200 and bill_answer["intent"] == "create_bill", "Agent bill chat should return a candidate")
    _assert(bill_answer["candidate"]["data"]["category"] == "餐饮", "Agent bill chat should infer category")
    _assert_agent_function_calls(
        bill_answer,
        {"privacy_guard", "knowledge_search", "route_chat_intent", "parse_bill_candidate", "classify_bill_category"},
        "Agent bill chat",
    )
    client.request("DELETE", f"/agent/bill-candidates/{bill_answer['candidate_id']}")


def _check_integration_diagnostics(client: ApiClient) -> None:
    status, diagnostics = client.request("GET", "/diagnostics/integrations")
    _assert(status == 200, "GET /diagnostics/integrations should return 200")
    _assert(
        diagnostics["status"] == "fallback",
        "Integration diagnostics should report local fallback by default",
    )
    _assert(
        diagnostics["check_count"] == 3,
        "Integration diagnostics should include OCR, AI parser and chat intent checks",
    )
    checks = {check["name"]: check for check in diagnostics["checks"]}
    _assert(
        set(checks) == {"ocr", "ai_parser", "chat_intent"},
        "Integration diagnostics should expose expected integration names",
    )
    _assert(
        checks["ocr"]["warnings"] == ["ocr_engine_not_configured"],
        "Integration diagnostics should explain missing OCR provider",
    )
    _assert(
        checks["ai_parser"]["warnings"] == ["rule_based_parser_fallback"],
        "Integration diagnostics should explain parser fallback",
    )
    _assert(
        checks["chat_intent"]["warnings"] == ["keyword_router_fallback"],
        "Integration diagnostics should explain chat routing fallback",
    )

    status, body = client.request("POST", "/diagnostics/integrations/probe")
    _assert(status == 400, "Integration probe should require explicit confirmation")
    _assert(
        "confirm=true" in body["detail"],
        "Integration probe should explain the confirmation requirement",
    )

    status, probe = client.request(
        "POST",
        "/diagnostics/integrations/probe",
        {"confirm": True},
    )
    _assert(status == 200, "Confirmed integration probe should return 200")
    _assert(
        probe["status"] == "skipped",
        "Integration probe should skip external calls when providers are not configured",
    )
    _assert(
        probe["probe_count"] == 4,
        "Integration probe should include OCR, bill parser, task parser and chat intent",
    )
    probe_results = {result["name"]: result for result in probe["results"]}
    _assert(
        set(probe_results) == {"ocr", "ai_bill_parser", "ai_task_parser", "chat_intent"},
        "Integration probe should expose expected probe names",
    )
    _assert(
        all(not result["attempted"] for result in probe_results.values()),
        "Integration probe should not attempt unconfigured providers",
    )


def _check_bill_statistics_overview(client: ApiClient) -> None:
    bills = [
        {
            "amount": 100,
            "merchant": "Stats Anchor Merchant",
            "category": "Dining",
            "transaction_type": "expense",
            "paid_at": "2026-08-01T09:00:00+08:00",
            "source": "manual",
        },
        {
            "amount": 25,
            "merchant": "Stats Anchor Merchant",
            "category": "Dining",
            "transaction_type": "expense",
            "paid_at": "2026-08-01T12:00:00+08:00",
            "source": "manual",
        },
        {
            "amount": 35,
            "merchant": "Stats Metro",
            "category": "Transport",
            "transaction_type": "expense",
            "paid_at": "2026-08-02T08:00:00+08:00",
            "source": "manual",
        },
        {
            "amount": 300,
            "merchant": "Stats Salary",
            "category": "Income",
            "transaction_type": "income",
            "paid_at": "2026-08-03T10:00:00+08:00",
            "source": "manual",
        },
        {
            "amount": 15,
            "merchant": "Stats Previous Month",
            "category": "Shopping",
            "transaction_type": "expense",
            "paid_at": "2026-07-15T10:00:00+08:00",
            "source": "manual",
        },
    ]
    for index, payload in enumerate(bills, start=1):
        status, _ = client.request(
            "POST",
            "/bills",
            payload,
            headers={"Idempotency-Key": f"smoke-statistics-bill-{index}"},
        )
        _assert(status == 201, "Statistics overview setup bills should be created")

    status, overview = client.request(
        "GET",
        "/bills/statistics/overview?year=2026&month=8&trend_months=2&top_merchant_limit=2",
    )
    _assert(status == 200, "GET /bills/statistics/overview should return 200")
    _assert(overview["year"] == 2026 and overview["month"] == 8, "Overview period changed")
    _assert(len(overview["daily_breakdown"]) == 31, "August daily breakdown should be zero-filled")
    _assert(
        overview["daily_breakdown"][0]["bill_count"] >= 2,
        "Daily breakdown should include fixed August 1 bills",
    )
    _assert(
        len(overview["monthly_trend"]) == 2
        and overview["monthly_trend"][0]["month"] == 7
        and overview["monthly_trend"][1]["month"] == 8,
        "Monthly trend should include July and August",
    )
    _assert(
        overview["top_merchants"][0]["merchant"] == "Stats Anchor Merchant",
        "Top merchants should be sorted by expense amount",
    )
    dining = next(
        item
        for item in overview["monthly_statistics"]["category_breakdown"]
        if item["category"] == "Dining"
    )
    _assert(float(dining["percentage"]) > 0, "Category breakdown should include percentage")


def _check_task_statistics_overview(client: ApiClient) -> None:
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    today_noon = now.replace(hour=12, minute=0)
    task_payloads = [
        {
            "title": "Task Stats Overdue",
            "category": "Task Stats QA",
            "task_type": "todo",
            "due_at": (now - timedelta(hours=2)).isoformat(),
            "priority": "high",
            "source": "manual",
        },
        {
            "title": "Task Stats Today",
            "category": "Task Stats QA",
            "task_type": "todo",
            "due_at": today_noon.isoformat(),
            "priority": "medium",
            "source": "manual",
        },
        {
            "title": "Task Stats Reminder",
            "category": "Task Stats QA",
            "task_type": "reminder",
            "remind_at": (now + timedelta(days=1)).isoformat(),
            "priority": "low",
            "source": "manual",
        },
        {
            "title": "Task Stats Unscheduled",
            "category": "Task Stats QA",
            "task_type": "todo",
            "priority": "medium",
            "source": "manual",
        },
        {
            "title": "Task Stats Done",
            "category": "Task Stats QA",
            "task_type": "todo",
            "priority": "medium",
            "source": "manual",
        },
        {
            "title": "Task Stats Cancelled",
            "category": "Task Stats QA",
            "task_type": "todo",
            "priority": "medium",
            "source": "manual",
        },
    ]
    created_tasks: list[dict[str, Any]] = []
    for index, payload in enumerate(task_payloads, start=1):
        status, task = client.request(
            "POST",
            "/tasks",
            payload,
            headers={"Idempotency-Key": f"smoke-statistics-task-{index}"},
        )
        _assert(status == 201, "Task statistics setup tasks should be created")
        created_tasks.append(task)

    status, _ = client.request(
        "POST",
        f"/tasks/{created_tasks[4]['id']}/complete",
        headers={"Idempotency-Key": "smoke-statistics-task-complete"},
    )
    _assert(status == 200, "Task statistics done setup should complete a task")

    status, _ = client.request(
        "PATCH",
        f"/tasks/{created_tasks[5]['id']}",
        {"status": "cancelled"},
    )
    _assert(status == 200, "Task statistics cancelled setup should cancel a task")

    status, overview = client.request(
        "GET",
        "/tasks/statistics/overview?upcoming_days=3&item_limit=50",
    )
    _assert(status == 200, "GET /tasks/statistics/overview should return 200")
    _assert(overview["pending_count"] >= 4, "Task overview should count pending tasks")
    _assert(overview["done_count"] >= 1, "Task overview should count done tasks")
    _assert(overview["cancelled_count"] >= 1, "Task overview should count cancelled tasks")
    _assert(overview["overdue_count"] >= 1, "Task overview should count overdue tasks")
    _assert(overview["due_today_count"] >= 1, "Task overview should count due-today tasks")
    _assert(
        overview["upcoming_reminder_count"] >= 1,
        "Task overview should count upcoming reminders",
    )
    _assert(
        overview["unscheduled_pending_count"] >= 1,
        "Task overview should count unscheduled pending tasks",
    )
    _assert(
        any(task["title"] == "Task Stats Overdue" for task in overview["overdue_tasks"]),
        "Task overview should include overdue task rows",
    )
    _assert(
        any(task["title"] == "Task Stats Today" for task in overview["today_tasks"]),
        "Task overview should include today task rows",
    )
    _assert(
        any(task["title"] == "Task Stats Reminder" for task in overview["upcoming_reminders"]),
        "Task overview should include upcoming reminder rows",
    )
    _assert(
        any(item["category"] == "Task Stats QA" for item in overview["category_breakdown"]),
        "Task overview should include category breakdown",
    )


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


def _check_candidate_edit_flow(client: ApiClient) -> None:
    status, bill_candidate = client.request(
        "POST",
        "/agent/parse-bill",
        {
            "text": "午餐 28 元 微信支付",
            "source": "ai_chat",
        },
    )
    _assert(status == 200, "Bill candidate edit setup should parse bill")
    bill_candidate_id = bill_candidate["candidate_id"]
    status, patched_bill = client.request(
        "PATCH",
        f"/agent/bill-candidates/{bill_candidate_id}",
        {
            "amount": 32.5,
            "merchant": "沙县小吃",
            "category": "餐饮",
            "payment_method": "微信支付",
        },
    )
    _assert(status == 200, "Bill candidate update should return 200")
    _assert(float(patched_bill["data"]["amount"]) == 32.5, "Bill candidate amount should update")
    _assert(patched_bill["data"]["merchant"] == "沙县小吃", "Bill candidate merchant should update")

    status, task_candidate = client.request(
        "POST",
        "/agent/parse-task",
        {
            "text": "明天 8 点提醒我交材料",
            "source": "ai_chat",
        },
    )
    _assert(status == 200, "Task candidate edit setup should parse task")
    task_candidate_id = task_candidate["candidate_id"]
    status, patched_task = client.request(
        "PATCH",
        f"/agent/task-candidates/{task_candidate_id}",
        {
            "title": "提交项目材料",
            "category": "工作",
            "priority": "high",
        },
    )
    _assert(status == 200, "Task candidate update should return 200")
    _assert(patched_task["data"]["title"] == "提交项目材料", "Task candidate title should update")
    _assert(patched_task["data"]["priority"] == "high", "Task candidate priority should update")

    status, diary_body = client.request(
        "POST",
        "/chat/messages",
        {"message": "写日记：今天完成了候选编辑联调，晴天，心情很平静"},
    )
    _assert(status == 200, "Diary candidate edit setup should create candidate")
    diary_candidate_id = diary_body["candidate_id"]
    status, patched_diary = client.request(
        "PATCH",
        f"/agent/diary-candidates/{diary_candidate_id}",
        {
            "title": "候选编辑联调完成",
            "content": "今天补齐了候选编辑接口测试，确认前可以更稳地修改 AI 结果。",
            "mood": "calm",
            "weather": "晴天",
            "tags": ["工作", "成长"],
        },
    )
    _assert(status == 200, "Diary candidate update should return 200")
    _assert(patched_diary["data"]["title"] == "候选编辑联调完成", "Diary candidate title should update")
    _assert(patched_diary["data"]["tags"] == ["工作", "成长"], "Diary candidate tags should update")

def _check_chat_clarifying_questions(client: ApiClient) -> None:
    status, bill_body = client.request("POST", "/chat/messages", {"message": "记一笔早餐"})
    _assert(status == 200, "Incomplete bill chat should still be handled")
    _assert(bill_body["intent"] == "create_bill", "Incomplete bill should keep bill intent")
    _assert(
        bill_body["candidate"]["data"]["amount"] is None,
        "Incomplete bill should keep missing amount empty",
    )
    _assert(
        "金额" in bill_body["reply"] and "补充" in bill_body["reply"],
        "Incomplete bill should ask the user for missing amount",
    )
    _assert(
        bill_body["agent_steps"][-1]["status"] == "blocked",
        "Incomplete bill should wait for user-supplied fields",
    )

    status, task_body = client.request(
        "POST",
        "/chat/messages",
        {"message": "提醒我去医院复诊"},
    )
    _assert(status == 200, "Incomplete reminder chat should still be handled")
    _assert(task_body["intent"] == "create_task", "Incomplete reminder should keep task intent")
    _assert(
        task_body["candidate"]["data"]["remind_at"] is None,
        "Incomplete reminder should keep missing reminder time empty",
    )
    _assert(
        "提醒时间" in task_body["reply"] and "补充" in task_body["reply"],
        "Incomplete reminder should ask the user for missing reminder time",
    )
    _assert(
        task_body["agent_steps"][-1]["status"] == "blocked",
        "Incomplete reminder should wait for user-supplied fields",
    )

def _check_chat_task_candidate_confirmation(client: ApiClient) -> None:
    message = "\u660e\u5929\u4e0b\u5348 3 \u70b9\u63d0\u9192\u6211\u53bb\u533b\u9662\u590d\u8bca"
    status, body = client.request("POST", "/chat/messages", {"message": message})
    _assert(status == 200, "POST /chat/messages should return 200")
    _assert(body["intent"] == "create_task", "Chat should create a task candidate")
    _assert(
        body["assistant_tool_id"] == "task_candidate",
        "Chat task response should expose selected assistant tool",
    )
    _assert(body["agent_steps"], "Chat task response should include agent steps")
    _assert(
        body["agent_steps"][-1]["status"] == "needs_confirmation",
        "Chat task response should ask for confirmation in agent steps",
    )

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


def _check_chat_diary_reflection(client: ApiClient) -> None:
    message = "\u65e5\u8bb0\u8ffd\u95ee\uff1a\u4eca\u5929\u6700\u5f00\u5fc3\u7684\u4e8b\u662f\u4ec0\u4e48\uff1f"
    status, body = client.request("POST", "/chat/messages", {"message": message})
    _assert(status == 200, "POST /chat/messages should support diary reflection")
    _assert(
        body["intent"] == "diary_reflection",
        "Chat should recognize diary reflection prompts",
    )
    _assert(
        body["action_type"] == "none",
        "Diary reflection should not create a candidate action",
    )
    _assert(
        body["assistant_tool_id"] == "diary_reflection",
        "Diary reflection should expose selected assistant tool",
    )
    _assert(
        body["need_user_confirmation"] is False,
        "Diary reflection should not require candidate confirmation",
    )
    _assert(body["agent_steps"], "Diary reflection should include agent steps")
    _assert(
        "\u5f00\u5fc3" in body["reply"],
        "Diary reflection reply should guide the selected prompt",
    )


def _check_chat_diary_candidate_confirmation(client: ApiClient) -> None:
    message = "\u5199\u65e5\u8bb0\uff1a\u4eca\u5929\u5b8c\u6210\u4e86\u9879\u76ee\u590d\u76d8\uff0c\u6674\u5929\uff0c\u5fc3\u60c5\u5f88\u8f7b\u677e"
    status, body = client.request("POST", "/chat/messages", {"message": message})
    _assert(status == 200, "POST /chat/messages should create diary candidates")
    _assert(body["intent"] == "create_diary", "Chat should recognize diary creation")
    _assert(
        body["action_type"] == "diary_candidate",
        "Diary creation should expose a confirmable candidate action",
    )
    _assert(
        body["assistant_tool_id"] == "diary_candidate",
        "Diary candidate should expose selected assistant tool",
    )
    _assert(body["need_user_confirmation"] is True, "Diary candidate should require confirmation")
    _assert(body["candidate"]["data"]["title"], "Diary candidate should include a title")
    _assert(body["candidate"]["data"]["content"], "Diary candidate should include content")
    candidate_id = body["candidate_id"]

    headers = {"Idempotency-Key": "smoke-chat-diary-confirm-001"}
    status, first = client.request(
        "POST",
        "/chat/confirm-action",
        {"action_type": "diary_candidate", "candidate_id": candidate_id},
        headers=headers,
    )
    status_again, second = client.request(
        "POST",
        "/chat/confirm-action",
        {"action_type": "diary_candidate", "candidate_id": candidate_id},
        headers=headers,
    )
    _assert(status == 200 and status_again == 200, "Diary candidate confirmation should be repeatable")
    _assert(
        first["created_diary"]["id"] == second["created_diary"]["id"],
        "Repeated diary confirmation should return the first diary",
    )
    _assert(first["action_type"] == "diary_candidate", "Diary confirmation should keep action type")

    status, diary_candidates = client.request("GET", "/agent/diary-candidates")
    _assert(status == 200, "Diary candidate list after confirmation should return 200")
    _assert(
        all(candidate["candidate_id"] != candidate_id for candidate in diary_candidates["items"]),
        "Confirmed diary candidate should leave the pending candidate list",
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


def _check_soft_delete_and_restore(client: ApiClient) -> None:
    bill_payload = {
        "amount": 35,
        "merchant": "Soft Delete Demo Merchant",
        "category": "QA",
        "transaction_type": "expense",
        "source": "manual",
    }
    status, bill = client.request(
        "POST",
        "/bills",
        bill_payload,
        headers={"Idempotency-Key": "smoke-soft-delete-bill-create"},
    )
    _assert(status == 201, "Soft delete setup bill should be created")
    bill_id = bill["id"]

    task_payload = {
        "title": "Soft Delete Demo Task",
        "category": "QA",
        "task_type": "todo",
        "source": "manual",
    }
    status, task = client.request(
        "POST",
        "/tasks",
        task_payload,
        headers={"Idempotency-Key": "smoke-soft-delete-task-create"},
    )
    _assert(status == 201, "Soft delete setup task should be created")
    task_id = task["id"]

    status, _ = client.request("DELETE", f"/bills/{bill_id}")
    _assert(status == 204, "Soft bill delete should return 204")
    status, _ = client.request("DELETE", f"/tasks/{task_id}")
    _assert(status == 204, "Soft task delete should return 204")

    status, _ = client.request("GET", f"/bills/{bill_id}")
    _assert(status == 404, "Soft-deleted bill should be hidden by default")
    status, deleted_bill = client.request("GET", f"/bills/{bill_id}?include_deleted=true")
    _assert(status == 200, "Soft-deleted bill should be readable when requested")
    _assert(deleted_bill["deleted_at"], "Soft-deleted bill should expose deleted_at")

    status, bills = client.request("GET", "/bills?deleted_only=true&page_size=100")
    _assert(status == 200, "Deleted bill list should return 200")
    _assert(
        any(item["id"] == bill_id for item in bills["items"]),
        "Deleted bill list should include the soft-deleted bill",
    )
    status, active_bills = client.request(
        "GET",
        "/bills?q=Soft%20Delete%20Demo%20Merchant",
    )
    _assert(status == 200, "Default bill list should return 200 after soft delete")
    _assert(active_bills["total"] == 0, "Default bill list should hide soft-deleted bills")

    status, _ = client.request("GET", f"/tasks/{task_id}")
    _assert(status == 404, "Soft-deleted task should be hidden by default")
    status, deleted_task = client.request("GET", f"/tasks/{task_id}?include_deleted=true")
    _assert(status == 200, "Soft-deleted task should be readable when requested")
    _assert(deleted_task["deleted_at"], "Soft-deleted task should expose deleted_at")

    status, tasks = client.request("GET", "/tasks?deleted_only=true&page_size=100")
    _assert(status == 200, "Deleted task list should return 200")
    _assert(
        any(item["id"] == task_id for item in tasks["items"]),
        "Deleted task list should include the soft-deleted task",
    )
    status, active_tasks = client.request("GET", "/tasks?category=QA")
    _assert(status == 200, "Default task list should return 200 after soft delete")
    _assert(
        all(item["id"] != task_id for item in active_tasks["items"]),
        "Default task list should hide soft-deleted tasks",
    )

    status, summary = client.request("GET", "/data/summary")
    _assert(status == 200, "Data summary should return 200 after soft delete")
    _assert(summary["deleted_bill_count"] >= 1, "Data summary should count deleted bills")
    _assert(summary["deleted_task_count"] >= 1, "Data summary should count deleted tasks")

    restore_bill_headers = {"Idempotency-Key": "smoke-soft-delete-bill-restore"}
    status, restored_bill = client.request(
        "POST",
        f"/bills/{bill_id}/restore",
        headers=restore_bill_headers,
    )
    status_again, restored_bill_again = client.request(
        "POST",
        f"/bills/{bill_id}/restore",
        headers=restore_bill_headers,
    )
    _assert(status == 200 and status_again == 200, "Repeated bill restore should return 200")
    _assert(restored_bill["id"] == restored_bill_again["id"], "Repeated bill restore should be stable")
    _assert(restored_bill["deleted_at"] is None, "Restored bill should clear deleted_at")

    restore_task_headers = {"Idempotency-Key": "smoke-soft-delete-task-restore"}
    status, restored_task = client.request(
        "POST",
        f"/tasks/{task_id}/restore",
        headers=restore_task_headers,
    )
    status_again, restored_task_again = client.request(
        "POST",
        f"/tasks/{task_id}/restore",
        headers=restore_task_headers,
    )
    _assert(status == 200 and status_again == 200, "Repeated task restore should return 200")
    _assert(restored_task["id"] == restored_task_again["id"], "Repeated task restore should be stable")
    _assert(restored_task["deleted_at"] is None, "Restored task should clear deleted_at")

    status, bill = client.request("GET", f"/bills/{bill_id}")
    _assert(status == 200 and bill["deleted_at"] is None, "Restored bill should be active")
    status, task = client.request("GET", f"/tasks/{task_id}")
    _assert(status == 200 and task["deleted_at"] is None, "Restored task should be active")


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
    _assert(
        body["agent_steps"][0]["status"] == "blocked",
        "Disabled AI chat should expose a blocked agent step",
    )

    status, _ = client.request(
        "PATCH",
        "/settings/privacy",
        {"allow_ai_text_processing": True},
    )
    _assert(status == 200, "AI text processing should be re-enabled")


def _check_category_settings(client: ApiClient) -> None:
    status, categories = client.request("GET", "/settings/categories")
    _assert(status == 200, "Category settings should return 200")
    _assert(
        categories["bill_categories"],
        "Category settings should include bill categories",
    )
    _assert(
        categories["task_categories"],
        "Category settings should include task categories",
    )
    original_categories = {
        "bill_categories": categories["bill_categories"],
        "task_categories": categories["task_categories"],
    }

    status, updated = client.request(
        "PATCH",
        "/settings/categories",
        {
            "bill_categories": ["餐饮", "咖啡", "餐饮", ""],
            "task_categories": ["工作", "生活", "工作", ""],
        },
    )
    _assert(status == 200, "Category settings update should return 200")
    _assert(
        updated["bill_categories"] == ["餐饮", "咖啡"],
        "Category settings should trim blanks and remove duplicate bill categories",
    )
    _assert(
        updated["task_categories"] == ["工作", "生活"],
        "Category settings should trim blanks and remove duplicate task categories",
    )

    status, snapshot = client.request("GET", "/data/export")
    _assert(status == 200, "Category settings export setup should return 200")
    _assert(
        snapshot["category_settings"]["bill_categories"] == ["餐饮", "咖啡"],
        "Data export should include category settings",
    )

    status, restored = client.request("PATCH", "/settings/categories", original_categories)
    _assert(status == 200, "Category settings restore should return 200")
    _assert(
        restored["bill_categories"] == original_categories["bill_categories"],
        "Category settings should restore original bill categories after test",
    )


def _check_budget_settings(client: ApiClient) -> None:
    status, budget = client.request("GET", "/settings/budget")
    _assert(status == 200, "Budget settings should return 200")
    _assert(
        float(budget["monthly_budget"]) >= 0,
        "Budget settings should include a non-negative monthly budget",
    )
    original_budget = {
        "monthly_budget": budget["monthly_budget"],
        "warning_threshold_percent": budget["warning_threshold_percent"],
    }

    status, updated = client.request(
        "PATCH",
        "/settings/budget",
        {
            "monthly_budget": "3600.50",
            "warning_threshold_percent": 75,
        },
    )
    _assert(status == 200, "Budget settings update should return 200")
    _assert(
        float(updated["monthly_budget"]) == 3600.5,
        "Budget settings should update monthly budget",
    )
    _assert(
        updated["warning_threshold_percent"] == 75,
        "Budget settings should update warning threshold",
    )

    status, snapshot = client.request("GET", "/data/export")
    _assert(status == 200, "Budget settings export setup should return 200")
    _assert(
        float(snapshot["budget_settings"]["monthly_budget"]) == 3600.5,
        "Data export should include budget settings",
    )

    status, restored = client.request("PATCH", "/settings/budget", original_budget)
    _assert(status == 200, "Budget settings restore should return 200")
    _assert(
        float(restored["monthly_budget"]) == float(original_budget["monthly_budget"]),
        "Budget settings should restore original monthly budget after test",
    )


def _check_tag_settings(client: ApiClient) -> None:
    status, tags = client.request("GET", "/settings/tags")
    _assert(status == 200, "Tag settings should return 200")
    _assert(tags["tags"], "Tag settings should include default tags")
    original_tags = {"tags": tags["tags"]}

    status, updated = client.request(
        "PATCH",
        "/settings/tags",
        {"tags": ["轻松", "成长", "轻松", ""]},
    )
    _assert(status == 200, "Tag settings update should return 200")
    _assert(
        updated["tags"] == ["轻松", "成长"],
        "Tag settings should trim blanks and remove duplicate tags",
    )

    status, diary = client.request(
        "PUT",
        "/diaries/by-date/2026-08-18",
        {
            "entry_date": "2026-08-18",
            "title": "Smoke Tag Diary",
            "content": "A diary entry with tags.",
            "mood": "calm",
            "source": "manual",
            "tags": ["轻松", "成长", "轻松", ""],
        },
    )
    _assert(status == 200, "Diary with tags should be saved")
    _assert(
        diary["tags"] == ["轻松", "成长"],
        "Diary tags should trim blanks and remove duplicates",
    )

    status, found = client.request("GET", "/diaries?q=%E6%88%90%E9%95%BF&page_size=5")
    _assert(status == 200, "Diary tag search should return 200")
    _assert(
        any(item["id"] == diary["id"] for item in found["items"]),
        "Diary keyword search should include matching tags",
    )

    status, snapshot = client.request("GET", "/data/export")
    _assert(status == 200, "Tag settings export setup should return 200")
    _assert(
        snapshot["tag_settings"]["tags"] == ["轻松", "成长"],
        "Data export should include tag settings",
    )

    status, restored = client.request("PATCH", "/settings/tags", original_tags)
    _assert(status == 200, "Tag settings restore should return 200")
    _assert(
        restored["tags"] == original_tags["tags"],
        "Tag settings should restore original tags after test",
    )


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


def _check_audit_log_and_request_id(client: ApiClient) -> None:
    status, bill_events = client.request(
        "GET",
        "/audit/events?action=bill_created&entity_type=bill&page_size=5",
    )
    _assert(status == 200, "Audit bill event list should return 200")
    _assert(bill_events["total"] >= 1, "Audit log should include bill creation events")
    _assert(
        bill_events["items"][0]["request_id"],
        "Audit events should include request id",
    )

    status, ocr_events = client.request(
        "GET",
        "/audit/events?action=attachment_ocr_text_updated&entity_type=attachment&page_size=5",
    )
    _assert(status == 200, "Audit OCR event list should return 200")
    _assert(ocr_events["total"] >= 1, "Audit log should include OCR text update events")
    metadata = ocr_events["items"][0]["metadata"]
    _assert(
        "ocr_text_length" in metadata and "ocr_text" not in metadata,
        "Audit OCR event should store length instead of raw OCR text",
    )

    status, chat_events = client.request(
        "GET",
        "/audit/events?action=chat_message_processed&entity_type=chat&page_size=5",
    )
    _assert(status == 200, "Audit chat event list should return 200")
    _assert(chat_events["total"] >= 1, "Audit log should include chat message events")
    chat_metadata = chat_events["items"][0]["metadata"]
    _assert(
        "message_length" in chat_metadata and "message" not in chat_metadata,
        "Audit chat event should store length instead of raw message text",
    )
    _assert(
        chat_metadata.get("agent_step_count", 0) >= 1,
        "Audit chat event should include agent step count",
    )
    _assert(
        "assistant_tool_id" in chat_metadata,
        "Audit chat event should include selected assistant tool",
    )
    _assert(
        chat_events["items"][0]["request_id"],
        "Audit chat events should include request id",
    )


def _check_data_import_restore(client: ApiClient) -> None:
    status, snapshot = client.request("GET", "/data/export")
    _assert(status == 200, "Data import setup export should return 200")
    _assert(snapshot["bills"], "Data import setup should have bills")
    _assert(snapshot["tasks"], "Data import setup should have tasks")
    first_bill_id = snapshot["bills"][0]["id"]
    first_task_id = snapshot["tasks"][0]["id"]

    status, cleared = client.request("POST", "/data/clear", {"confirm": True})
    _assert(status == 200, "Data import setup clear should return 200")
    _assert(cleared["after"]["bill_count"] == 0, "Data import setup should clear bills")
    _assert(cleared["after"]["task_count"] == 0, "Data import setup should clear tasks")

    dry_run_payload = {
        "dry_run": True,
        "reset_existing": True,
        "snapshot": snapshot,
    }
    status, dry_run = client.request("POST", "/data/import", dry_run_payload)
    _assert(status == 200, "Data import dry run should return 200")
    _assert(dry_run["dry_run"], "Data import dry run should mark dry_run")
    _assert(
        dry_run["imported_bill_count"] == len(snapshot["bills"]),
        "Data import dry run should count bills",
    )

    status, summary = client.request("GET", "/data/summary")
    _assert(status == 200, "Data import dry run summary should return 200")
    _assert(summary["bill_count"] == 0, "Data import dry run should not change bills")
    _assert(summary["task_count"] == 0, "Data import dry run should not change tasks")

    status, body = client.request("POST", "/data/import", {"snapshot": snapshot})
    _assert(status == 400, "Data import should require confirmation unless dry run")
    _assert(
        body["detail"] == "Set confirm to true before importing local data",
        "Data import confirmation guard message changed",
    )

    import_payload = {
        "confirm": True,
        "reset_existing": True,
        "snapshot": snapshot,
    }
    status, imported = client.request("POST", "/data/import", import_payload)
    _assert(status == 200, "Confirmed data import should return 200")
    _assert(not imported["dry_run"], "Confirmed data import should not mark dry_run")
    _assert(
        imported["after"]["bill_count"] == len(snapshot["bills"]),
        "Confirmed data import should restore bill count",
    )
    _assert(
        imported["after"]["task_count"] == len(snapshot["tasks"]),
        "Confirmed data import should restore task count",
    )

    status, bill = client.request("GET", f"/bills/{first_bill_id}")
    _assert(status == 200, "Confirmed data import should restore bill ids")
    _assert(bill["id"] == first_bill_id, "Confirmed data import should preserve bill id")

    status, task = client.request("GET", f"/tasks/{first_task_id}")
    _assert(status == 200, "Confirmed data import should restore task ids")
    _assert(task["id"] == first_task_id, "Confirmed data import should preserve task id")

    status, import_events = client.request(
        "GET",
        "/audit/events?action=data_imported&entity_type=data&page_size=5",
    )
    _assert(status == 200, "Audit data import event list should return 200")
    _assert(import_events["total"] >= 1, "Audit log should include data import events")


def _check_local_snapshot_persistence(client: ApiClient) -> None:
    status, body = client.request("DELETE", "/data/snapshot")
    _assert(status == 400, "Snapshot delete should require confirmation")
    _assert(
        body["detail"] == "Set confirm to true before deleting local snapshot",
        "Snapshot delete confirmation guard message changed",
    )

    status, _ = client.request("DELETE", "/data/snapshot", {"confirm": True})
    _assert(status == 200, "Snapshot cleanup should return 200")

    status, snapshot_status = client.request("GET", "/data/snapshot/status")
    _assert(status == 200, "Snapshot status should return 200")
    _assert(not snapshot_status["exists"], "Snapshot status should start without a snapshot")

    status, deleted_bill = client.request(
        "POST",
        "/bills",
        {
            "amount": 19.5,
            "merchant": "Snapshot Deleted Merchant",
            "category": "QA",
            "transaction_type": "expense",
            "source": "manual",
        },
        headers={"Idempotency-Key": "smoke-snapshot-deleted-bill-create"},
    )
    _assert(status == 201, "Snapshot deleted bill setup should create a bill")
    status, deleted_task = client.request(
        "POST",
        "/tasks",
        {
            "title": "Snapshot Deleted Task",
            "category": "QA",
            "task_type": "todo",
            "source": "manual",
        },
        headers={"Idempotency-Key": "smoke-snapshot-deleted-task-create"},
    )
    _assert(status == 201, "Snapshot deleted task setup should create a task")
    deleted_bill_id = deleted_bill["id"]
    deleted_task_id = deleted_task["id"]

    status, _ = client.request("DELETE", f"/bills/{deleted_bill_id}")
    _assert(status == 204, "Snapshot setup should soft-delete a bill")
    status, _ = client.request("DELETE", f"/tasks/{deleted_task_id}")
    _assert(status == 204, "Snapshot setup should soft-delete a task")

    status, saved = client.request("POST", "/data/snapshot/save")
    _assert(status == 200, "Snapshot save should return 200")
    _assert(saved["exists"], "Snapshot save should create a snapshot")
    _assert(saved["file_size_bytes"] > 0, "Snapshot save should write bytes")
    saved_bill_count = saved["snapshot_data_summary"]["bill_count"]
    saved_task_count = saved["snapshot_data_summary"]["task_count"]
    saved_deleted_bill_count = saved["snapshot_data_summary"]["deleted_bill_count"]
    saved_deleted_task_count = saved["snapshot_data_summary"]["deleted_task_count"]
    saved_total_bill_count = saved_bill_count + saved_deleted_bill_count
    saved_total_task_count = saved_task_count + saved_deleted_task_count
    _assert(saved_bill_count >= 1, "Snapshot save setup should include bills")
    _assert(saved_task_count >= 1, "Snapshot save setup should include tasks")
    _assert(
        saved_deleted_bill_count >= 1,
        "Snapshot save should include soft-deleted bills",
    )
    _assert(
        saved_deleted_task_count >= 1,
        "Snapshot save should include soft-deleted tasks",
    )
    _assert(
        saved["current_data_summary"]["deleted_bill_count"] >= 1,
        "Snapshot save should expose current deleted bill count",
    )

    status, cleared = client.request("POST", "/data/clear", {"confirm": True})
    _assert(status == 200, "Snapshot load setup clear should return 200")
    _assert(cleared["after"]["bill_count"] == 0, "Snapshot load setup should clear bills")
    _assert(cleared["after"]["task_count"] == 0, "Snapshot load setup should clear tasks")

    status, snapshot_status = client.request("GET", "/data/snapshot/status")
    _assert(status == 200, "Snapshot status after clear should return 200")
    _assert(
        snapshot_status["snapshot_data_summary"]["bill_count"] == saved_bill_count,
        "Snapshot status should report saved bill count, not current bill count",
    )
    _assert(
        snapshot_status["current_data_summary"]["bill_count"] == 0,
        "Snapshot status should separately report current cleared bill count",
    )

    status, dry_run = client.request(
        "POST",
        "/data/snapshot/load",
        {"dry_run": True},
    )
    _assert(status == 200, "Snapshot load dry run should return 200")
    _assert(dry_run["import_result"]["dry_run"], "Snapshot load dry run should mark dry_run")
    _assert(
        dry_run["import_result"]["imported_bill_count"] == saved_total_bill_count,
        "Snapshot load dry run should count active and soft-deleted bills",
    )

    status, summary = client.request("GET", "/data/summary")
    _assert(status == 200, "Snapshot dry run summary should return 200")
    _assert(summary["bill_count"] == 0, "Snapshot dry run should not restore bills")
    _assert(summary["task_count"] == 0, "Snapshot dry run should not restore tasks")

    status, body = client.request("POST", "/data/snapshot/load", {})
    _assert(status == 400, "Snapshot load should require confirmation unless dry run")
    _assert(
        body["detail"] == "Set confirm to true before loading local snapshot",
        "Snapshot load confirmation guard message changed",
    )

    status, loaded = client.request(
        "POST",
        "/data/snapshot/load",
        {"confirm": True, "reset_existing": True},
    )
    _assert(status == 200, "Confirmed snapshot load should return 200")
    _assert(
        loaded["import_result"]["after"]["bill_count"] == saved_bill_count,
        "Confirmed snapshot load should restore bills",
    )
    _assert(
        loaded["import_result"]["after"]["task_count"] == saved_task_count,
        "Confirmed snapshot load should restore tasks",
    )
    _assert(
        loaded["import_result"]["after"]["deleted_bill_count"] == saved_deleted_bill_count,
        "Confirmed snapshot load should restore soft-deleted bills",
    )
    _assert(
        loaded["import_result"]["after"]["deleted_task_count"] == saved_deleted_task_count,
        "Confirmed snapshot load should restore soft-deleted tasks",
    )
    _assert(
        loaded["import_result"]["imported_bill_count"] == saved_total_bill_count,
        "Confirmed snapshot load should import active and soft-deleted bills",
    )
    _assert(
        loaded["import_result"]["imported_task_count"] == saved_total_task_count,
        "Confirmed snapshot load should import active and soft-deleted tasks",
    )

    status, restored_deleted_bill = client.request(
        "GET",
        f"/bills/{deleted_bill_id}?include_deleted=true",
    )
    _assert(status == 200, "Snapshot load should restore soft-deleted bill id")
    _assert(
        restored_deleted_bill["deleted_at"],
        "Snapshot load should preserve bill deleted_at",
    )
    status, restored_deleted_task = client.request(
        "GET",
        f"/tasks/{deleted_task_id}?include_deleted=true",
    )
    _assert(status == 200, "Snapshot load should restore soft-deleted task id")
    _assert(
        restored_deleted_task["deleted_at"],
        "Snapshot load should preserve task deleted_at",
    )

    status, load_events = client.request(
        "GET",
        "/audit/events?action=data_snapshot_loaded&entity_type=data&page_size=5",
    )
    _assert(status == 200, "Audit snapshot load event list should return 200")
    _assert(load_events["total"] >= 1, "Audit log should include snapshot load events")

    status, deleted = client.request("DELETE", "/data/snapshot", {"confirm": True})
    _assert(status == 200, "Snapshot delete should return 200")
    _assert(deleted["deleted"], "Snapshot delete should remove the saved snapshot")

    status, snapshot_status = client.request("GET", "/data/snapshot/status")
    _assert(status == 200, "Snapshot status after delete should return 200")
    _assert(not snapshot_status["exists"], "Snapshot status should show deleted snapshot")


def _check_data_quality_diagnostics(client: ApiClient) -> None:
    duplicate_bill_payload = {
        "amount": 88.8,
        "merchant": "Diagnostics Duplicate Merchant",
        "category": "QA",
        "transaction_type": "expense",
        "paid_at": "2026-08-01T09:00:00+08:00",
        "source": "manual",
    }
    status, _ = client.request(
        "POST",
        "/bills",
        duplicate_bill_payload,
        headers={"Idempotency-Key": "smoke-diagnostics-duplicate-bill-1"},
    )
    _assert(status == 201, "Diagnostics duplicate setup first bill should be created")
    status, _ = client.request(
        "POST",
        "/bills",
        duplicate_bill_payload | {"paid_at": "2026-08-01T09:05:00+08:00"},
        headers={"Idempotency-Key": "smoke-diagnostics-duplicate-bill-2"},
    )
    _assert(status == 201, "Diagnostics duplicate setup second bill should be created")

    status, _ = client.request(
        "POST",
        "/tasks",
        {
            "title": "Diagnostics Overdue Task",
            "category": "QA",
            "task_type": "todo",
            "due_at": (datetime.now(LOCAL_TZ) - timedelta(hours=2)).isoformat(),
            "priority": "high",
            "source": "manual",
        },
        headers={"Idempotency-Key": "smoke-diagnostics-overdue-task"},
    )
    _assert(status == 201, "Diagnostics overdue setup task should be created")
    status, _ = client.request(
        "POST",
        "/tasks",
        {
            "title": "Diagnostics Unscheduled Task",
            "category": "QA",
            "task_type": "todo",
            "priority": "medium",
            "source": "manual",
        },
        headers={"Idempotency-Key": "smoke-diagnostics-unscheduled-task"},
    )
    _assert(status == 201, "Diagnostics unscheduled setup task should be created")

    status, _ = client.upload_png()
    _assert(status == 201, "Diagnostics attachment setup should upload an attachment")

    status, diagnostics = client.request(
        "GET",
        "/diagnostics/data-quality?duplicate_time_window_minutes=10&issue_limit=100",
    )
    _assert(status == 200, "GET /diagnostics/data-quality should return 200")
    _assert(
        diagnostics["status"] == "action_required",
        "Data quality diagnostics should surface action_required status",
    )
    codes = {issue["code"] for issue in diagnostics["issues"]}
    _assert(
        "possible_duplicate_bill" in codes,
        "Data quality diagnostics should find duplicate bills",
    )
    _assert("overdue_task" in codes, "Data quality diagnostics should find overdue tasks")
    _assert(
        "unscheduled_pending_task" in codes,
        "Data quality diagnostics should find unscheduled pending tasks",
    )
    _assert(
        "attachment_missing_ocr_text" in codes,
        "Data quality diagnostics should find attachments missing OCR text",
    )
    _assert(
        "pending_diary_candidates" in codes,
        "Data quality diagnostics should find pending diary candidates",
    )
    _assert(
        diagnostics["action_required_count"] >= 1
        and diagnostics["warning_count"] >= 1
        and diagnostics["info_count"] >= 1,
        "Data quality diagnostics should include severity counts",
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
    _assert(body["diary_candidates"], "Data export should include diary candidates")

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

    status, diary_candidates_csv = client.request(
        "GET",
        "/data/export/diary-candidates.csv",
    )
    _assert(status == 200, "GET /data/export/diary-candidates.csv should return 200")
    _assert(
        "candidate_id" in diary_candidates_csv and "候选编辑联调完成" in diary_candidates_csv,
        "Diary candidates CSV should include pending diary candidate rows",
    )

    status, data_export_events = client.request(
        "GET",
        "/audit/events?action=data_exported&entity_type=data&page_size=5",
    )
    _assert(status == 200, "Audit data export event list should return 200")
    _assert(data_export_events["total"] >= 1, "Audit log should include data export events")

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


def _assert_agent_function_calls(
    response: dict[str, Any],
    expected_names: set[str],
    context: str,
) -> None:
    calls = response.get("function_calls") or []
    _assert(calls, f"{context} should include function call traces")
    call_names = {call.get("name") for call in calls if isinstance(call, dict)}
    missing = expected_names - call_names
    _assert(not missing, f"{context} missing function calls: {sorted(missing)}")


if __name__ == "__main__":
    raise SystemExit(main())
