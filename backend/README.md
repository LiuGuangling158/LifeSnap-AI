# LifeSnap AI Backend

FastAPI backend for LifeSnap AI.

## Current Increment

The backend currently provides the MVP shell, health check, bill management,
task/reminder management, attachment metadata, dashboard summary, and rule-based
AI candidate flows for bills and tasks.

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

Frontend bootstrap:

```text
GET /app/capabilities
GET /app/bootstrap
GET /app/bootstrap?recent_bill_limit=5&candidate_limit=5
```

`/app/capabilities` exposes MVP feature flags, supported attachment types,
attachment size limits, parser providers, storage backend, and known
limitations. `/app/bootstrap` combines capabilities, privacy settings, local
data counts, and dashboard summary for frontend startup.

Bill statistics:

```text
GET /bills/statistics/monthly
GET /bills/statistics/monthly?year=2026&month=8
GET /bills/statistics/overview?year=2026&month=8&trend_months=6&top_merchant_limit=5
```

`/bills/statistics/overview` is intended for chart screens. It returns monthly
totals, category percentages, a zero-filled daily breakdown, recent monthly
trend rows, and top expense merchants.

Run backend smoke test:

```powershell
cd ..
.\backend\.venv\Scripts\python.exe backend\scripts\smoke_test.py
```

The smoke test starts a temporary backend server, verifies the core API flow, and
then shuts the temporary server down. It does not use the existing `8000` server.

## Error Responses

HTTP errors keep FastAPI's familiar `detail` field and add a stable `error`
object for frontend handling:

```json
{
  "detail": "Bill not found",
  "error": {
    "code": "not_found",
    "message": "Bill not found",
    "status_code": 404,
    "path": "/bills/00000000-0000-0000-0000-000000000000"
  }
}
```

Validation errors return `error.code: "validation_error"` and include
`error.issues` with field-level details.

## Soft Delete

Bills and tasks use soft delete. `DELETE /bills/{id}` and `DELETE /tasks/{id}`
hide records from default detail, list, dashboard, statistics, and export views,
but keep them recoverable.

```text
GET /bills?deleted_only=true
GET /bills/{id}?include_deleted=true
POST /bills/{id}/restore

GET /tasks?deleted_only=true
GET /tasks/{id}?include_deleted=true
POST /tasks/{id}/restore
```

`GET /data/summary` includes `deleted_bill_count` and `deleted_task_count` for
frontend recycle-bin indicators.

Task statistics:

```text
GET /tasks/statistics/overview
GET /tasks/statistics/overview?upcoming_days=7&item_limit=10
```

The task overview returns pending/done/cancelled counts, overdue count, due
today count, upcoming reminder count, unscheduled pending count, status/type/
priority/category breakdowns, and limited lists for overdue tasks, today tasks,
and upcoming reminders.

Request tracing:

```text
X-Request-ID: optional-client-request-id
```

Every response includes `X-Request-ID`. Standard error responses also include
`error.request_id` so frontend logs can match backend diagnostics.

Audit log:

```text
GET /audit/events
GET /audit/events?action=data_exported
GET /audit/events?entity_type=bill&page=1&page_size=20
```

Audit events are in-memory for the MVP backend and keep only operation metadata,
resource IDs, route path, method, and request ID. Raw OCR text, request bodies,
notes, and long free text are not stored in audit metadata.

## Idempotency

Create and state-changing endpoints support an optional `Idempotency-Key` header
for weak-network retries. Repeating the same endpoint with the same key and same
payload returns the first successful result instead of applying the action again.
Reusing the same key with a different payload returns `409 Conflict`.

Example:

```http
POST /tasks
Idempotency-Key: create-rent-task-001
Content-Type: application/json

{
  "title": "交房租",
  "category": "居住",
  "task_type": "todo",
  "due_at": "2026-08-01T09:00:00+08:00",
  "source": "manual"
}
```

Currently covered endpoints:

- `POST /bills`
- `POST /tasks`
- `POST /tasks/{task_id}/complete`
- `POST /tasks/{task_id}/snooze`
- `POST /agent/bill-candidates/{candidate_id}/confirm`
- `POST /agent/task-candidates/{candidate_id}/confirm`
- `POST /chat/confirm-action`
- `POST /chat/discard-action`

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

List pending bill candidates:

```text
GET /agent/bill-candidates
GET /agent/bill-candidates?confirmable_only=true
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

Check whether a bill candidate looks duplicated before confirmation:

```text
POST /agent/bill-candidates/{candidate_id}/check-duplicate?time_window_minutes=10
```

This uses the same duplicate rule as `POST /bills/check-duplicate`. Candidates
missing required fields, such as `amount` or `merchant`, return `400`.

Confirm a bill candidate and save it as a bill:

```text
POST /agent/bill-candidates/{candidate_id}/confirm
```

Candidates missing required fields, such as `amount` or `merchant`, cannot be confirmed directly. The user should edit the result and save it through `POST /bills`.

Discard a pending bill candidate:

```text
DELETE /agent/bill-candidates/{candidate_id}
```

Parse chat text into a task or reminder candidate:

```http
POST /agent/parse-task
Content-Type: application/json

{
  "text": "明天下午 3 点提醒我去医院复诊，记得带医保卡和检查报告。",
  "source": "ai_chat"
}
```

This endpoint returns a candidate only. It does not create a saved task. The
user still needs to confirm or edit the result before it is saved.

Get a task candidate:

```text
GET /agent/task-candidates/{candidate_id}
```

List pending task candidates:

```text
GET /agent/task-candidates
GET /agent/task-candidates?confirmable_only=true
```

List all pending candidates together:

```text
GET /agent/candidates
GET /agent/candidates?confirmable_only=true
```

Update a task candidate before confirmation:

```http
PATCH /agent/task-candidates/{candidate_id}
Content-Type: application/json

{
  "title": "去医院复诊",
  "category": "医疗",
  "task_type": "reminder",
  "remind_at": "2026-08-01T15:00:00+08:00",
  "priority": "high"
}
```

Confirm a task candidate and save it as a task:

```text
POST /agent/task-candidates/{candidate_id}/confirm
```

Reminder candidates missing required fields, such as `title` or `remind_at`,
cannot be confirmed directly. Todo candidates require at least a `title`.

Discard a pending task candidate:

```text
DELETE /agent/task-candidates/{candidate_id}
```

## Chat

Send a user message to the MVP AI entry:

```http
POST /chat/messages
Content-Type: application/json

{
  "message": "明天下午 3 点提醒我去医院复诊，记得带医保卡和检查报告。"
}
```

The endpoint returns one of three outcomes:

- a bill candidate
- a task or reminder candidate
- an MVP fallback message for unsupported intents

Example bill input:

```json
{
  "message": "记一笔 18 元早餐"
}
```

Example unsupported input:

```json
{
  "message": "帮我管理这个会员订阅，下个月扣费前提醒"
}
```

Chat responses do not create formal bills or tasks directly. If the response
contains `candidate_id`, the user still needs to confirm it through the related
candidate confirmation endpoint, or through the unified chat action endpoint.
The user can also discard an unwanted candidate from the same chat flow.

Confirm the candidate returned by `POST /chat/messages`:

```http
POST /chat/confirm-action
Idempotency-Key: chat-confirm-001
Content-Type: application/json

{
  "action_type": "task_candidate",
  "candidate_id": "00000000-0000-0000-0000-000000000000"
}
```

Supported `action_type` values are `bill_candidate` and `task_candidate`. The
response includes `created_bill` or `created_task` when the candidate is saved.
Candidates with incomplete required fields still need to be edited first.

Discard the candidate returned by `POST /chat/messages`:

```http
POST /chat/discard-action
Idempotency-Key: chat-discard-001
Content-Type: application/json

{
  "action_type": "bill_candidate",
  "candidate_id": "00000000-0000-0000-0000-000000000000"
}
```

The discard action removes the pending candidate only. It does not delete any
formal bill or task that has already been confirmed.

## Settings

Get privacy settings:

```text
GET /settings/privacy
```

Update privacy settings:

```http
PATCH /settings/privacy
Content-Type: application/json

{
  "local_only_mode": true,
  "allow_ai_text_processing": true,
  "save_original_attachments_by_default": false,
  "keep_ocr_text": true
}
```

When `save_original_attachments_by_default` is enabled, attachment uploads that
do not pass `save_original` will keep the original file in memory. When
`allow_ai_text_processing` is disabled, chat and parse endpoints stop generating
AI candidates. When `keep_ocr_text` is disabled, attachment OCR text is removed
after parsing.

## Local Data

Get local data summary:

```text
GET /data/summary
```

Seed demo data for frontend integration:

```http
POST /data/seed-demo
Idempotency-Key: seed-demo-001
Content-Type: application/json

{
  "confirm": true,
  "reset_existing": true,
  "include_attachment": true,
  "include_candidates": true
}
```

This creates demo bills, tasks, one attachment with OCR text, and pending bill
and task candidates. Use `reset_existing: true` when you want a clean demo
workspace before frontend testing.

Export local data as JSON:

```text
GET /data/export
```

Export local data as CSV:

```text
GET /data/export/bills.csv
GET /data/export/tasks.csv
GET /data/export/attachments.csv
GET /data/export/bill-candidates.csv
GET /data/export/task-candidates.csv
```

CSV exports include structured records only. Attachment CSV exports metadata and
OCR presence, not original file bytes. Candidate CSV exports include pending
candidate fields, warnings, and field confidence values.

Clear local data:

```http
POST /data/clear
Content-Type: application/json

{
  "confirm": true,
  "include_bills": true,
  "include_tasks": true,
  "include_attachments": true,
  "include_candidates": true,
  "reset_privacy_settings": false
}
```

The clear endpoint returns data counts before and after the operation. It
requires `confirm: true` to avoid accidental deletion.

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

Check duplicate attachments by checksum:

```text
GET /attachments/{attachment_id}/duplicates
```

Uploading the same file bytes again does not block the upload. The second
attachment returns `duplicate_of` in its metadata, and the duplicate query
returns all current attachments with the same checksum.

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

Recognize an attachment and parse it into a bill candidate when text is
available:

```text
POST /attachments/{attachment_id}/recognize-and-parse-bill
```

If the attachment has no OCR text yet, this returns `manual_required` instead of
failing the flow. After the user provides OCR text through
`PATCH /attachments/{attachment_id}/ocr-text`, the same endpoint can create a
pending bill candidate.

Delete an attachment:

```text
DELETE /attachments/{attachment_id}
```

## OCR

Recognize text from an uploaded attachment:

```http
POST /ocr/recognize
Content-Type: application/json

{
  "attachment_id": "00000000-0000-0000-0000-000000000000"
}
```

This increment does not run a real OCR engine yet. It returns stored OCR text
when available. If the attachment has no OCR text, it returns:

```json
{
  "status": "manual_required",
  "text": null,
  "manual_entry_required": true,
  "warnings": ["ocr_engine_not_configured", "manual_entry_required"]
}
```

The fallback flow is:

```text
POST /attachments/upload
POST /ocr/recognize
PATCH /attachments/{attachment_id}/ocr-text
POST /ocr/recognize
POST /attachments/{attachment_id}/parse-bill
```

For frontend flows that prefer fewer steps, use:

```text
POST /attachments/{attachment_id}/recognize-and-parse-bill
PATCH /attachments/{attachment_id}/ocr-text
POST /attachments/{attachment_id}/recognize-and-parse-bill
```

## Dashboard

Get homepage summary:

```text
GET /dashboard/summary
GET /dashboard/summary?year=2026&month=7&upcoming_days=7
GET /dashboard/summary?recent_bill_limit=5&candidate_limit=5
```

The dashboard summary includes:

- local data counts
- monthly bill statistics
- recent bills
- today's pending todo items
- upcoming reminders
- pending bill and task candidates

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

Check whether a bill looks duplicated:

```http
POST /bills/check-duplicate?time_window_minutes=10
Content-Type: application/json

{
  "amount": 18.5,
  "merchant": "瑞幸咖啡",
  "category": "餐饮",
  "payment_method": "微信支付",
  "transaction_type": "expense",
  "paid_at": "2026-07-31T09:30:00+08:00",
  "source": "screenshot"
}
```

The duplicate check only returns possible matches. It does not block `POST /bills`.

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

Snooze a reminder or todo:

```http
POST /tasks/{task_id}/snooze
Content-Type: application/json

{
  "minutes": 30
}
```

Or snooze to a specific time:

```http
POST /tasks/{task_id}/snooze
Content-Type: application/json

{
  "snooze_until": "2026-08-02T16:00:00+08:00"
}
```

Only pending tasks can be snoozed. Reminder tasks update `remind_at`; todo tasks
update `due_at`.

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
