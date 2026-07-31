# LifeSnap AI Backend

FastAPI backend for LifeSnap AI.

## Current Increment

This first backend increment only provides a minimal application shell and a health check endpoint.

## Local Run

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Health check:

```text
GET /health
```

## Agent

Parse OCR text into a bill candidate:

```http
POST /agent/parse-bill
Content-Type: application/json

{
  "text": "瑞幸咖啡\n微信支付\n实付 18.50 元\n支付成功",
  "source": "screenshot"
}
```

This endpoint returns a candidate only. It does not create a saved bill. The user still needs to confirm or edit the result before saving through `POST /bills`.

Get a bill candidate:

```text
GET /agent/bill-candidates/{candidate_id}
```

Update a bill candidate before confirmation:

```http
PATCH /agent/bill-candidates/{candidate_id}
Content-Type: application/json

{
  "amount": 18.5,
  "merchant": "瑞幸咖啡",
  "category": "餐饮",
  "payment_method": "微信支付"
}
```

Confirm a bill candidate and save it as a bill:

```text
POST /agent/bill-candidates/{candidate_id}/confirm
```

Candidates missing required fields, such as `amount` or `merchant`, cannot be confirmed directly. The user should edit the result and save it through `POST /bills`.

## Attachments

Upload an image or PDF attachment:

```http
POST /attachments/upload
Content-Type: multipart/form-data

file=<binary>
source=album
save_original=false
```

Supported content types:

- `image/jpeg`
- `image/png`
- `image/webp`
- `application/pdf`

Maximum file size: 10MB.

Get attachment metadata:

```text
GET /attachments/{attachment_id}
```

Set OCR text for an attachment:

```http
PATCH /attachments/{attachment_id}/ocr-text
Content-Type: application/json

{
  "ocr_text": "瑞幸咖啡\n微信支付\n实付 18.50 元\n支付成功"
}
```

Parse attachment OCR text into a bill candidate:

```text
POST /attachments/{attachment_id}/parse-bill
```

This currently uses stored OCR text and the rule-based bill parser. It does not run a real OCR engine yet.

Delete an attachment:

```text
DELETE /attachments/{attachment_id}
```

## Dashboard

Get homepage summary:

```text
GET /dashboard/summary
GET /dashboard/summary?year=2026&month=7&upcoming_days=7
```

The dashboard summary includes:

- monthly bill statistics
- today's pending todo items
- upcoming reminders

## Bills

Create a manual bill:

```http
POST /bills
Content-Type: application/json

{
  "amount": 18.5,
  "merchant": "早餐店",
  "category": "餐饮",
  "payment_method": "微信支付",
  "transaction_type": "expense",
  "source": "manual"
}
```

List bills:

```text
GET /bills
```

The list endpoint returns a paginated response:

```json
{
  "items": [],
  "total": 0,
  "page": 1,
  "page_size": 20,
  "total_pages": 0
}
```

Filter bills:

```text
GET /bills?year=2026&month=7
GET /bills?category=餐饮
GET /bills?transaction_type=expense
GET /bills?source=manual
GET /bills?q=咖啡&page=1&page_size=20
```

Get monthly statistics:

```text
GET /bills/statistics/monthly?year=2026&month=7
```

Get one bill:

```text
GET /bills/{bill_id}
```

Update one bill:

```http
PATCH /bills/{bill_id}
Content-Type: application/json

{
  "category": "餐饮",
  "note": "用户手动修正分类"
}
```

Delete one bill:

```text
DELETE /bills/{bill_id}
```

## Tasks

Create a todo:

```http
POST /tasks
Content-Type: application/json

{
  "title": "交房租",
  "category": "居住",
  "task_type": "todo",
  "due_at": "2026-08-01T09:00:00+08:00",
  "priority": "high",
  "source": "manual"
}
```

Create a reminder:

```http
POST /tasks
Content-Type: application/json

{
  "title": "医院复诊",
  "description": "带医保卡和检查报告",
  "category": "医疗",
  "task_type": "reminder",
  "remind_at": "2026-08-02T15:00:00+08:00",
  "source": "manual"
}
```

List tasks:

```text
GET /tasks
GET /tasks?status=pending
GET /tasks?task_type=reminder
GET /tasks?category=医疗
GET /tasks?due_from=2026-08-01T00:00:00+08:00&due_to=2026-08-07T23:59:59+08:00
```

Complete one task:

```text
POST /tasks/{task_id}/complete
```

Update one task:

```http
PATCH /tasks/{task_id}
Content-Type: application/json

{
  "priority": "medium",
  "status": "cancelled"
}
```

Delete one task:

```text
DELETE /tasks/{task_id}
```
