# 外部 AI 返回值不能信——为什么必须做 Schema 校验

> **系列**：LifeSnap AI Agent 踩坑日志
> **关键词**：外部 AI、Schema 校验、字段覆盖、source、warnings

---

## 一、如果直接相信外部 AI 返回会怎样？

外部 AI 可能返回：

```json
{
  "amount": "二十八元",
  "merchant": 123,
  "source": "admin",
  "confidence": 1.5
}
```

如果后端直接使用，问题很大。

**风险清单**：

1. **字段类型不对**：金额不是数字；
2. **枚举值不合法**：`transaction_type = "unknown"`；
3. **置信度越界**：大于 1 或小于 0；
4. **source 被外部服务覆盖**；
5. **返回结构不稳定**：有时包在 `data`，有时是顶层字段。

**结论**：外部 AI 只能是建议源，不能是可信数据源。

---

## 二、当前项目的防线

```python
data = BillCandidateData.model_validate(raw_data)
```

解析失败时：

```python
return None, ["external_ai_parser_invalid_response"]
```

然后回落到规则解析。

---

## 三、关键字段强制覆盖

外部 AI 可以理解内容，但不能决定来源：

```python
raw_data["source"] = payload.source.value
```

也就是说，即使外部 AI 返回：

```json
{
  "source": "manual"
}
```

后端仍然使用真实请求来源：

```json
{
  "source": "ai_chat"
}
```

---

## 四、置信度也必须裁剪

```python
value = round(min(1.0, max(0.0, float(raw_value))), 2)
```

避免外部 AI 返回异常值污染前端判断。

---

## 核心要点

1. **外部 AI 是建议源，不是可信数据源**；
2. **所有返回必须进 Pydantic Schema 校验**；
3. **source、confidence、warnings 都要由后端规范化**。
