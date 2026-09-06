# OCR 不是账单——为什么图片识别后还要二次解析

> **系列**：LifeSnap AI Agent 踩坑日志
> **关键词**：OCR、账单解析、附件、隐私设置、手动兜底

---

## 一、如果 OCR 结果直接当账单会怎样？

上传支付截图后，最简单的想法是：

```python
ocr_text = ocr_service.recognize(attachment_id)
bill = bill_parser.parse_bill(ocr_text)
bill_store.create(bill)
```

看似顺滑，但真实场景很快踩坑。

**风险清单**：

1. **OCR 只负责文字，不理解账单结构**；
2. **截图里可能有广告、余额、优惠券金额**；
3. **同一张图可能有多个金额**；
4. **图片可能没有保留原文件，外部 OCR 无法调用**；
5. **隐私模式开启时，外部 OCR 必须被阻断**。

**结论**：OCR 结果不能直接落账，必须先作为文本证据，再交给账单解析器生成候选。

---

## 二、正确链路

```sql
附件上传
   │
   ▼
OCR 识别文本
   │
   ▼
保存 OCR Text / 手动补录
   │
   ▼
Agent 解析为账单候选
   │
   ▼
用户确认
```

---

## 三、当前项目做法

OCR 返回的是识别状态：

```json
{
  "status": "manual_required",
  "text": null,
  "manual_entry_required": true,
  "warnings": ["ocr_engine_not_configured"]
}
```

当没有真实 OCR 或隐私阻断时，不让流程失败，而是进入手动兜底。

---

## 四、外部 OCR 的坑

外部 OCR 需要原始文件：

```python
original = attachment_store.original_content(attachment_id)
if original is None:
    return manual_required("original_attachment_missing")
```

而项目默认：

```json
{
  "save_original_attachments_by_default": false
}
```

所以如果用户没有保留原图，外部 OCR 没法识别，只能手动填 OCR 文本。

---

## 核心要点

1. **OCR 只是文字提取，不等于账单生成**；
2. **图片识别必须支持手动兜底**；
3. **外部 OCR 必须尊重隐私设置和原始附件保存策略**。
