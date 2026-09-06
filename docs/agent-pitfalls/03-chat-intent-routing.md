# Chat Agent 不能只靠关键词——从“点”字误判到外部意图路由

> **系列**：LifeSnap AI Agent 踩坑日志
> **关键词**：聊天助手、意图识别、关键词误判、chat_intent、fallback

---

## 一、只靠关键词判断意图会怎样？

最早聊天助手可以这样写：

```python
if "提醒" in text or "明天" in text:
    intent = "create_task"
elif "元" in text:
    intent = "create_bill"
```

但真实输入很快出问题。

**踩坑案例**：

```text
我今天有点累
```

因为包含“点”，可能被误判成提醒。

```text
工资收入 6800 元
```

因为有“元”，会被当成支出账单，而不是收入。

```text
下周预算控制一下
```

既像待办，又像统计查询，关键词不够判断。

**结论**：聊天入口不能只靠关键词，至少要有可插拔的意图路由层。

---

## 二、改进后的链路

```sql
用户聊天
   │
   ▼
外部 AI chat_intent 路由
   │
   ├── create_bill
   ├── create_task
   └── unsupported
   │
   ▼
对应 Parser 生成候选
```

---

## 三、当前项目做法

外部 AI 解析统一走：

```json
{
  "kind": "chat_intent",
  "text": "明天 9 点提醒我交房租",
  "source": "ai_chat"
}
```

返回：

```json
{
  "intent": "create_task",
  "confidence": 0.88,
  "reply": "我先整理成一个待确认事项，你确认或修改后再保存。"
}
```

---

## 四、真实踩坑：失败时不能连打两次外部服务

如果 `chat_intent` 调用外部 AI 失败，再进入账单/待办 parser 时又调用一次外部 AI，就会造成一次聊天卡两轮超时。

所以现在回落逻辑是：

```python
if external_chat_failed:
    force_rule_based_parser = True
```

外部路由失败后，只走本地规则解析。

---

## 核心要点

1. **聊天意图识别不能完全依赖关键词**；
2. **外部 AI 失败必须快速回落**；
3. **一次用户消息不能因为 fallback 连续等待多个超时**。
