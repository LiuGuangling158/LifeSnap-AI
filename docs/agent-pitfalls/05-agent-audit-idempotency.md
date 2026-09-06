# Agent 操作必须可追溯——确认、丢弃、重试都要有审计和幂等

> **系列**：LifeSnap AI Agent 踩坑日志
> **关键词**：Agent、审计日志、幂等、候选确认、重复提交

---

## 一、如果确认按钮可以重复提交会怎样？

用户在聊天页看到一个待办候选：

```text
明天下午 3 点提醒我去医院复诊
```

点击“确认保存”。

如果网络慢，用户连续点两次，后端可能创建两条待办。

**风险清单**：

1. **重复确认生成重复账单/待办**；
2. **用户不知道哪次操作成功**；
3. **候选已删除后再次确认，状态混乱**；
4. **排查问题时没有日志可追溯**。

**结论**：Agent 写操作必须有幂等保护和审计记录。

---

## 二、当前项目的确认链路

```sql
Chat Candidate
   │
   ▼
POST /chat/confirm-action
   │
   ▼
Idempotency Store
   │
   ▼
Candidate Store Confirm
   │
   ▼
Audit Log
```

---

## 三、幂等保护

```python
idempotency_store.run(
    scope="POST /chat/confirm-action",
    key=idempotency_key,
    fingerprint=payload.model_dump(mode="json"),
    factory=lambda: _confirm_candidate(payload),
)
```

同一个 `Idempotency-Key` 和同一个 payload 重试，只返回第一次结果，不重复创建。

---

## 四、审计记录

```python
audit_log_store.record(
    action="chat_action_confirmed",
    entity_type="chat_action",
    entity_id=payload.candidate_id,
    metadata={
        "action_type": payload.action_type,
        "created_bill_id": response.created_bill.id if response.created_bill else None,
        "created_task_id": response.created_task.id if response.created_task else None,
    },
)
```

以后排查问题时可以知道：

```text
谁在什么时候确认了哪个候选，最终创建了哪条账单/待办
```

---

## 核心要点

1. **Agent 相关写操作必须幂等**；
2. **候选确认和丢弃都要记录审计日志**；
3. **出了问题不能靠猜，必须能回溯操作链路**。
