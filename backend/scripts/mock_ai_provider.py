from __future__ import annotations

import argparse
import base64
import json
import re
from datetime import datetime, time, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


LOCAL_TZ = timezone(timedelta(hours=8))


class MockAiProviderHandler(BaseHTTPRequestHandler):
    server_version = "LifeSnapMockAiProvider/0.1"

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json({"status": "ok", "service": "lifesnap_mock_ai_provider"})
            return
        self._send_json({"detail": "Not found"}, status=404)

    def do_POST(self) -> None:
        payload = self._read_json()
        if payload is None:
            self._send_json({"detail": "Invalid JSON"}, status=400)
            return

        if self.path == "/parse":
            self._send_json(parse_payload(payload))
            return
        if self.path == "/recognize":
            self._send_json(recognize_payload(payload))
            return

        self._send_json({"detail": "Not found"}, status=404)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[mock-ai] {self.address_string()} - {format % args}")

    def _read_json(self) -> dict[str, Any] | None:
        content_length = int(self.headers.get("Content-Length") or "0")
        body = self.rfile.read(content_length)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return payload if isinstance(payload, dict) else None

    def _send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def parse_payload(payload: dict[str, Any]) -> dict[str, Any]:
    kind = str(payload.get("kind") or "").strip()
    text = str(payload.get("text") or "").strip()
    if kind == "chat_intent":
        return route_chat(text)
    if kind == "bill":
        return parse_bill(text)
    if kind == "task":
        return parse_task(text, payload)
    return {
        "confidence": 0.0,
        "warnings": ["unsupported_parse_kind"],
    }


def recognize_payload(payload: dict[str, Any]) -> dict[str, Any]:
    content_base64 = str(payload.get("content_base64") or "")
    warnings: list[str] = []
    if content_base64:
        try:
            base64.b64decode(content_base64, validate=True)
        except ValueError:
            warnings.append("invalid_base64_ignored")

    filename = str(payload.get("filename") or "").casefold()
    if "salary" in filename or "income" in filename:
        text = "工资收入\n建设银行\n到账 6800 元"
    elif "task" in filename or "todo" in filename:
        text = "明天下午 3 点提醒我开项目会，准备周报"
    else:
        text = "瑞幸咖啡\n微信支付\n实付 18.50 元\n支付成功"

    return {
        "text": text,
        "confidence": 0.91,
        "provider": "lifesnap_mock_ocr",
        "warnings": warnings,
    }


def route_chat(text: str) -> dict[str, Any]:
    if looks_like_task(text):
        return {
            "intent": "create_task",
            "confidence": 0.88,
            "reply": "我先整理成一个待确认事项，你确认或修改后再保存。",
            "warnings": [],
        }
    if looks_like_bill(text):
        return {
            "intent": "create_bill",
            "confidence": 0.89,
            "reply": "我先整理成一个待确认账单，你确认或修改后再保存。",
            "warnings": [],
        }
    return {
        "intent": "unsupported",
        "confidence": 0.6,
        "reply": "这条消息暂时不能直接转换成账单或提醒。",
        "warnings": ["mock_intent_low_confidence"],
    }


def parse_bill(text: str) -> dict[str, Any]:
    amount = extract_amount(text)
    merchant = extract_merchant(text)
    transaction_type = "income" if looks_like_income(text) else "expense"
    category = "收入" if transaction_type == "income" else extract_bill_category(text)
    payment_method = extract_payment_method(text)
    warnings: list[str] = []
    if amount is None:
        warnings.append("amount_missing")
    if merchant is None:
        warnings.append("merchant_missing")
    if payment_method is None and transaction_type == "expense":
        warnings.append("payment_method_missing")

    return {
        "confidence": 0.9 if amount is not None else 0.55,
        "data": {
            "amount": f"{amount:.2f}" if amount is not None else None,
            "currency": "CNY",
            "merchant": merchant,
            "category": category,
            "payment_method": payment_method,
            "transaction_type": transaction_type,
            "note": "本地 mock AI 解析生成的候选账单",
        },
        "field_confidence": {
            "amount": 0.95 if amount is not None else 0.0,
            "merchant": 0.8 if merchant is not None else 0.0,
            "category": 0.82,
            "payment_method": 0.8 if payment_method is not None else 0.0,
        },
        "warnings": warnings,
    }


def parse_task(text: str, payload: dict[str, Any]) -> dict[str, Any]:
    task_type = "reminder" if looks_like_reminder(text) else "todo"
    target_at = extract_target_at(text, payload.get("current_datetime"))
    category = extract_task_category(text)
    title = extract_task_title(text)
    warnings: list[str] = []
    if title is None:
        warnings.append("title_missing")
    if task_type == "reminder" and target_at is None:
        warnings.append("remind_time_missing")

    return {
        "confidence": 0.87,
        "data": {
            "title": title,
            "description": text[:500],
            "category": category,
            "task_type": task_type,
            "due_at": target_at if task_type == "todo" else None,
            "remind_at": target_at if task_type == "reminder" else None,
            "priority": "high" if any_word(text, ["紧急", "重要", "尽快"]) else "medium",
        },
        "warnings": warnings,
    }


def looks_like_bill(text: str) -> bool:
    bill_keywords = ["记账", "记一笔", "花了", "消费", "支出", "收入", "工资", "付款"]
    return extract_amount(text) is not None or any_word(text, bill_keywords)


def looks_like_task(text: str) -> bool:
    task_keywords = ["提醒", "待办", "任务", "记得", "别忘", "明天", "后天", "会议"]
    return any_word(text, task_keywords)


def looks_like_reminder(text: str) -> bool:
    return any_word(text, ["提醒", "记得", "别忘"]) or extract_clock(text) is not None


def looks_like_income(text: str) -> bool:
    return any_word(text, ["收入", "工资", "到账", "收款", "奖金"])


def any_word(text: str, words: list[str]) -> bool:
    normalized = text.casefold()
    return any(word.casefold() in normalized for word in words)


def extract_amount(text: str) -> float | None:
    patterns = [
        r"(?:¥|￥|人民币|金额|实付|支付|付款|花了|到账|收入)\s*([0-9]+(?:\.[0-9]{1,2})?)",
        r"([0-9]+(?:\.[0-9]{1,2})?)\s*(?:元|块|rmb|cny|¥)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return None


def extract_merchant(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    ignored = ["支付", "付款", "金额", "成功", "订单", "交易", "时间", "实付", "到账"]
    for line in lines:
        if any(word in line for word in ignored):
            continue
        if re.search(r"[0-9]+(?:\.[0-9]{1,2})?\s*(?:元|块|rmb|cny|¥)", line, re.IGNORECASE):
            continue
        return line[:120]

    cleaned = re.sub(r"[0-9]+(?:\.[0-9]{1,2})?\s*(?:元|块|rmb|cny|¥)", "", text, flags=re.IGNORECASE)
    cleaned = re.sub(r"^(记一笔|记账|花了|消费|支出|收入|工资)", "", cleaned).strip(" ，,。")
    return cleaned[:120] or None


def extract_payment_method(text: str) -> str | None:
    payment_methods = {
        "微信": "微信支付",
        "wechat": "微信支付",
        "支付宝": "支付宝",
        "alipay": "支付宝",
        "银行卡": "银行卡",
        "建设银行": "建设银行",
        "云闪付": "云闪付",
    }
    normalized = text.casefold()
    for keyword, method in payment_methods.items():
        if keyword.casefold() in normalized:
            return method
    return None


def extract_bill_category(text: str) -> str:
    categories = {
        "餐饮": ["咖啡", "早餐", "午餐", "晚餐", "外卖", "餐"],
        "交通": ["打车", "地铁", "公交", "高铁"],
        "购物": ["超市", "购物", "买"],
        "医疗": ["医院", "药", "复诊"],
        "居住": ["房租", "水电", "物业"],
    }
    for category, keywords in categories.items():
        if any_word(text, keywords):
            return category
    return "其他"


def extract_task_category(text: str) -> str:
    categories = {
        "工作": ["会议", "项目", "周报", "汇报", "客户"],
        "学习": ["作业", "课程", "考试", "学习"],
        "医疗": ["医院", "复诊", "药"],
        "财务": ["房租", "账单", "还款", "报销"],
        "生活": ["快递", "超市", "买菜", "购物"],
    }
    for category, keywords in categories.items():
        if any_word(text, keywords):
            return category
    return "生活"


def extract_task_title(text: str) -> str | None:
    cleaned = re.sub(r"(?:(上午|中午|下午|晚上|今晚|早上)\s*)?[0-2]?\d\s*(?:[:：点时])\s*[0-5]?\d?", "", text)
    for token in ["今天", "今晚", "明天", "后天", "下周", "提醒我", "提醒", "记得", "别忘"]:
        cleaned = cleaned.replace(token, "")
    cleaned = cleaned.strip(" ，,。.;；:：")
    return cleaned[:120] or None


def extract_target_at(text: str, current_datetime: object) -> str | None:
    now = parse_datetime(current_datetime)
    clock = extract_clock(text)
    if "后天" in text:
        target_date = (now + timedelta(days=2)).date()
    elif "明天" in text:
        target_date = (now + timedelta(days=1)).date()
    elif "今天" in text or "今晚" in text:
        target_date = now.date()
    elif clock is not None:
        target_date = now.date()
    else:
        return None

    target_time = clock or time(23, 59)
    target = datetime.combine(target_date, target_time, tzinfo=now.tzinfo)
    if target < now:
        target += timedelta(days=1)
    return target.isoformat()


def extract_clock(text: str) -> time | None:
    match = re.search(
        r"(?:(上午|中午|下午|晚上|今晚|早上)\s*)?([0-2]?\d)\s*(?:[:：点时])\s*([0-5]?\d)?",
        text,
    )
    if match is None:
        return None
    period = match.group(1) or ""
    hour = int(match.group(2))
    minute = int(match.group(3) or 0)
    if hour > 23 or minute > 59:
        return None
    if period in {"下午", "晚上", "今晚"} and hour < 12:
        hour += 12
    if period == "中午" and hour < 11:
        hour += 12
    return time(hour, minute)


def parse_datetime(value: object) -> datetime:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            pass
    return datetime.now(LOCAL_TZ)


def run_self_test() -> None:
    receipt = recognize_payload({"filename": "receipt.png", "content_base64": "ZmFrZQ=="})
    assert receipt["text"]
    assert route_chat("明天 9 点提醒我交房租")["intent"] == "create_task"
    assert route_chat("午餐 28 元 微信支付")["intent"] == "create_bill"
    assert parse_bill("瑞幸咖啡\n微信支付\n实付 18.50 元")["data"]["amount"] == "18.50"
    assert parse_task("明天下午 3 点提醒我开项目会", {})["data"]["remind_at"]
    print("Mock AI provider self-test passed")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a local LifeSnap mock OCR/AI provider.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        run_self_test()
        return 0

    server = ThreadingHTTPServer((args.host, args.port), MockAiProviderHandler)
    base_url = f"http://{args.host}:{args.port}"
    print("LifeSnap mock OCR/AI provider is running")
    print(f"OCR endpoint: {base_url}/recognize")
    print(f"AI parse endpoint: {base_url}/parse")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping mock provider...")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
