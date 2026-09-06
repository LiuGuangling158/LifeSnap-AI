# 外部依赖没就绪不能阻塞开发——为什么要有本地 Mock AI 服务

> **系列**：LifeSnap AI Agent 踩坑日志
> **关键词**：Mock、本地服务、外部依赖、协议对齐、self-test、current_datetime

---

## 一、如果等真实外部 AI/OCR 接入再开发会怎样？

外部 OCR 和 AI 解析服务的接口、计费、鉴权都还没定，最容易陷入的局面是：

```text
"业务逻辑写完了，但外部服务没通，联调不了。"
```

于是前端、候选流程、连通性探测、冒烟测试全卡住，等一个还没就绪的外部依赖。

**结论**：外部依赖未就绪时，需要一个和真实服务协议一致的本地替身，让开发先跑起来。

---

## 二、Mock 服务遵循同一套协议

本地 Mock 暴露和真实服务一样的入口：

```python
def do_POST(self):
    if self.path == "/parse":
        self._send_json(parse_payload(payload))
    if self.path == "/recognize":
        self._send_json(recognize_payload(payload))
```

`/parse` 内部按 `kind` 分发，和真实服务对齐：

```python
def parse_payload(payload):
    kind = str(payload.get("kind") or "").strip()
    if kind == "chat_intent":
        return route_chat(text)
    if kind == "bill":
        return parse_bill(text)
    if kind == "task":
        return parse_task(text, payload)
```

请求体带 `schema_version`、`kind`、`text`、`source`、`current_datetime`，切换到真实服务时业务代码不用改。

---

## 三、Mock 本身要能自测

Mock 如果自己坏了，会反过来误导开发。所以内置了 `--self-test`：

```python
def run_self_test():
    assert route_chat("明天 9 点提醒我交房租")["intent"] == "create_task"
    assert route_chat("午餐 28 元 微信支付")["intent"] == "create_bill"
    assert parse_bill("瑞幸咖啡\n微信支付\n实付 18.50 元")["data"]["amount"] == "18.50"
```

跑一次就知道 Mock 本身是否健康。

---

## 四、相对时间要可确定

"明天下午 3 点"这种相对时间，必须依据一个确定的时间基准来解析，否则结果每次跑都不一样：

```python
def parse_task(text, payload):
    target_at = extract_target_at(text, payload.get("current_datetime"))
```

真实服务也会收到 `current_datetime`，两边行为一致，切换时不会出现时间语义差异。

---

## 核心要点

1. **外部依赖未就绪时，用本地 Mock 推进开发**；
2. **Mock 必须遵循和真实服务一致的协议**；
3. **Mock 要可自测、相对时间要可确定**。
