# Agent 不能直接落库——为什么 LifeSnap AI 要先生成 Candidate

> **系列**：LifeSnap AI Agent 踩坑日志
> **关键词**：Agent、候选记录、用户确认、误操作防护、账单解析、待办解析

---

## 一、如果让 Agent 直接创建账单会怎样？

一开始最直觉的方案是：

```python
bill = bill_store.create(agent_parsed_bill)
```

用户发一句：

```text
午餐 28 元 微信支付
```

Agent 解析后直接保存账单。

**风险清单**：

1. **金额识别错误**：OCR 把 `28.00` 识别成 `2800`，直接落库会污染账本；
2. **分类不确定**：`苹果 18 元` 可能是水果，也可能是 App Store 消费；
3. **商户缺失**：用户只说“花了 20”，Agent 无法知道商户；
4. **重复记录**：用户重复发送、网络重试、聊天确认重复点，都可能生成重复账单。

**结论**：Agent 不能直接创建正式数据，必须先生成候选记录。

---

## 二、防误落库链路

```sql
用户输入 / OCR 文本
   │
   ▼
Agent Parser
   │
   ▼
BillCandidate / TaskCandidate
   │
   ▼
用户检查、编辑、确认
   │
   ▼
正式 Bill / Task
```

---

## 三、当前项目做法

```python
candidate = bill_parser.parse_bill(payload)
saved_candidate = bill_candidate_store.save(candidate)
```

Agent 只负责生成：

```json
{
  "candidate_id": "...",
  "confidence": 0.72,
  "data": {
    "amount": "28.00",
    "merchant": null,
    "category": "餐饮"
  },
  "warnings": ["merchant_missing"],
  "need_user_confirmation": true
}
```

正式保存必须走：

```http
POST /agent/bill-candidates/{candidate_id}/confirm
```

---

## 四、踩坑后的关键改进

1. 候选记录持久化到 JSON，刷新页面后不丢；
2. 候选可编辑，用户能补金额、商户、分类；
3. 缺少必要字段时不能确认；
4. 确认后才进入正式账单/待办。

---

## 核心要点

1. **Agent 只生成建议，不直接写正式数据**；
2. **所有 AI 结果默认需要用户确认**；
3. **Candidate 是 Agent 和真实数据之间的安全缓冲层**。
