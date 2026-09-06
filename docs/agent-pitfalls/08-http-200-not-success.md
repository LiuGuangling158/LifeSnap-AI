# 外部服务返回 200 不代表成功——探测还要二次校验响应结构

> **系列**：LifeSnap AI Agent 踩坑日志
> **关键词**：连通性探测、HTTP 状态码、响应校验、失败分类、InvalidResponse

---

## 一、如果只看 HTTP 状态码会怎样？

外部 OCR 返回 `200 OK`，直觉上就当作识别成功了：

```python
with urlopen(request, timeout=...) as response:
    data = json.loads(response.read().decode("utf-8"))
text = data["text"]  # 直接取
```

但 `200` 只代表"服务器有响应"，不代表"响应内容正确"。

**可能遇到的 200**：

1. **body 是空字符串**，`json.loads` 直接抛异常；
2. **body 不是对象**，是列表或字符串；
3. **缺关键字段**：没有 `text`；
4. **`text` 是空字符串**：有字段但没识别出内容；
5. **字段类型不对**：`text` 是数字或对象。

**结论**：HTTP 状态码之外，必须对响应体做二次结构校验。

---

## 二、逐层校验

```python
if not isinstance(response, dict):
    return failed(..., error="InvalidResponse")

if "text" not in response:
    return failed(..., error="MissingText")

text = str(response.get("text") or "").strip()
if not text:
    warnings.append("external_ocr_empty_text")
```

每一层都对应一种独立的失败原因。

---

## 三、失败必须分类

```python
except (HTTPError, URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError):
    return failed(..., warnings=["external_ocr_failed"], error=type(error).__name__)
```

- **网络/超时异常**（`HTTPError` / `URLError` / `TimeoutError` / `OSError`）→ `external_ocr_failed`；
- **响应结构不对** → `InvalidResponse` / `MissingText`。

两者的排查方向完全不同：前者是"连不上"，后者是"连上了但协议不匹配"。

---

## 四、和生产路径保持一致

`ocr_service` 的真实识别路径同样不信任裸 200：

```python
text = str(response.get("text") or "").strip()
if not text:
    return self._manual_required(..., warnings=["external_ocr_empty_text"])
```

识别不出就落手动兜底，而不是让流程"假成功"。

---

## 核心要点

1. **HTTP 200 只代表有响应，不代表响应正确**；
2. **探测要二次校验响应结构，不能只信状态码**；
3. **失败要分类，区分"连不上"和"协议不匹配"**。
