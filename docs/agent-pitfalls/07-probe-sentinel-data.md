# 探测不能拿真实数据去试——哨兵数据、confirm 门控、隐私前置

> **系列**：LifeSnap AI Agent 踩坑日志
> **关键词**：连通性探测、哨兵数据、confirm、隐私阻断、preview

---

## 一、如果探测直接拿真实数据去试会怎样？

要验证外部 OCR 到底通不通，最省事的写法是拿一条真实附件去 `recognize` 一下：

```python
attachment = attachment_store.all()[0]
ocr_service._call_external_ocr(
    attachment_id=attachment.id,
    filename=attachment.filename,
    content=attachment_store.original_content(attachment.id),
)
```

看似"用真实数据最真实"，但代价很大。

**风险清单**：

1. **隐私泄露**：真实附件/聊天文本被发到外部服务，可能被记录或缓存；
2. **真实费用**：外部 OCR/AI 按次计费，探测一次就是一次成本；
3. **污染外部服务**：探测数据混进外部服务的日志、缓存、用量统计。

**结论**：探测必须用可识别的假数据，且出网前要有一道门控。

---

## 二、三道防线

```sql
POST /diagnostics/integrations/probe
   │
   ├── confirm=true 门控（否则 400）
   │
   ├── 隐私阻断前置检查（local_only / 禁止 AI 处理 → skip）
   │
   └── 哨兵数据（固定 UUID + 固定假字节）
```

---

## 三、当前项目做法

confirm 门控在 API 层：

```python
if not payload.confirm:
    raise HTTPException(
        status_code=400,
        detail="Set confirm=true to run external integration probes.",
    )
```

隐私阻断在探测前就生效：

```python
def _external_ai_privacy_blockers(self):
    privacy_settings = settings_store.get_privacy_settings()
    blockers = []
    if privacy_settings.local_only_mode:
        blockers.append("local_only_mode_enabled")
    if not privacy_settings.allow_ai_text_processing:
        blockers.append("ai_text_processing_disabled")
    return blockers
```

哨兵数据一眼可辨，且不落库：

```python
response = ocr_service._call_external_ocr(
    attachment_id=UUID("00000000-0000-0000-0000-000000000001"),
    filename="lifesnap-probe-receipt.png",
    content_type="image/png",
    content=b"lifesnap-probe-receipt",
)
```

---

## 四、结果只给 preview

探测返回的 `response_preview` 被 `_preview_text` 截断到 80 字符，只用于人眼判断，不生成候选、不写正式数据。

---

## 核心要点

1. **探测必须用哨兵数据，不用真实用户数据**；
2. **会出网的探测要 confirm 门控**；
3. **隐私阻断要在出网之前就生效**。
