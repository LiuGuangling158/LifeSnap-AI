# LifeSnap AI Backend

FastAPI backend for LifeSnap AI.

## Current Increment

The backend currently provides the MVP shell, health check, bill management,
task/reminder management, attachment metadata, dashboard summary, and rule-based
AI candidate flows for bills and tasks. OCR and AI parsing can also delegate to
configured external HTTP providers while keeping local fallback behavior.

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

Audit events are stored at `backend/data/audit_events.json` with a rolling
limit of 500 events. They keep only operation metadata, resource IDs, route
path, method, and request ID. Raw OCR text, request bodies, notes, and long free
text are not stored in audit metadata.

Data import:

```text
POST /data/import
```

Use the JSON returned by `GET /data/export` as `snapshot`. `dry_run=true`
validates and counts records without changing local data. Real imports require
`confirm=true`; `reset_existing=true` clears selected local datasets before
restoring the snapshot.

Local snapshot persistence:

```text
GET /data/snapshot/status
POST /data/snapshot/save
POST /data/snapshot/load
DELETE /data/snapshot
```

Snapshots are stored at `backend/data/local_snapshot.json`, which is ignored by
Git. Loading supports `dry_run=true`; real loads require `confirm=true` and reuse
the same selective import flags as `/data/import`. Snapshot saves include
soft-deleted bills and tasks so the restore bin survives local persistence.
Deleting a snapshot also requires `confirm=true`.

Local JSON persistence:

Bills are stored at `backend/data/bills.json`, tasks are stored at
`backend/data/tasks.json`, and diary entries are stored at
`backend/data/diaries.json`. These files are ignored by Git and are updated
automatically when records are created, edited, soft-deleted, restored, cleared,
or imported from a snapshot.

Privacy settings are stored at `backend/data/settings.json` and are updated
when settings are changed, reset, or imported from a snapshot.

Pending bill and task candidates are stored at
`backend/data/bill_candidates.json` and `backend/data/task_candidates.json`.
They are updated when AI parsing creates a candidate, the user edits it,
confirms it, discards it, clears local data, or imports a snapshot.

Attachment metadata is stored at `backend/data/attachments.json`. Retained
original attachment files are stored under `backend/data/attachment_files/`.
Snapshot export includes attachment metadata, OCR text, and checksum data, but
not retained original file bytes.

Audit events are stored at `backend/data/audit_events.json`, and idempotency
records are stored at `backend/data/idempotency.json`. Idempotency records are
cleared automatically when local data is cleared or imported.

Diagnostics:

```text
GET /diagnostics/data-quality
GET /diagnostics/data-quality?duplicate_time_window_minutes=10&issue_limit=50
```

Data-quality diagnostics surface frontend-friendly issues such as possible
duplicate bills, missing OCR text, pending candidates, overdue tasks,
unscheduled pending tasks, recycle-bin counts, and privacy setting warnings.

## Idempotency

Create and state-changing endpoints support an optional `Idempotency-Key` header
for weak-network retries. Repeating the same endpoint with the same key and same
payload returns the first successful result instead of applying the action again.
Reusing the same key with a different payload returns `409 Conflict`.
Successful idempotency records are persisted to `backend/data/idempotency.json`,
so retry protection survives backend restarts.

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

This endpoint returns a candidate only. It does not create a saved bill. The
user still needs to confirm or edit the result before saving through
`POST /bills`.

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

## AI Parser

Bill and task parsing can use either the built-in rule-based parser or a
configured external HTTP AI parser. When no external parser is configured, all
parse endpoints keep the current rule-based fallback behavior.

Configure an external AI parser:

```powershell
$env:LIFESNAP_AI_PARSE_ENDPOINT = "https://your-ai-service.example.com/parse"
$env:LIFESNAP_AI_PARSE_API_KEY = "optional-secret"
$env:LIFESNAP_AI_PARSE_PROVIDER = "external_http"
$env:LIFESNAP_AI_PARSE_TIMEOUT_SECONDS = "20"
```

The backend sends this JSON payload to the endpoint:

```json
{
  "schema_version": "lifesnap.ai.parse.v1",
  "kind": "bill",
  "text": "记一笔 18 元早餐",
  "source": "ai_chat",
  "locale": "zh-CN",
  "current_datetime": "2026-08-20T09:30:00+07:00"
}
```

Supported `kind` values are `bill`, `task`, and `chat_intent`. `bill` and
`task` return structured candidate fields. `chat_intent` only routes a chat
message to `create_bill`, `create_task`, or `unsupported`; the backend then
reuses the bill/task parser and candidate confirmation flow.

For bills, the provider should return either top-level candidate fields or a
`data` object containing fields compatible with `BillCandidateData`:

```json
{
  "confidence": 0.92,
  "data": {
    "amount": "18.00",
    "currency": "CNY",
    "merchant": "早餐店",
    "category": "餐饮",
    "payment_method": "微信支付",
    "transaction_type": "expense",
    "note": "AI 解析生成的候选账单"
  },
  "field_confidence": {
    "amount": 0.95,
    "merchant": 0.8,
    "category": 0.9,
    "payment_method": 0.85
  },
  "warnings": []
}
```

For tasks, return fields compatible with `TaskCandidateData`:

```json
{
  "confidence": 0.9,
  "data": {
    "title": "去医院复诊",
    "description": "带医保卡和检查报告",
    "category": "医疗",
    "task_type": "reminder",
    "remind_at": "2026-08-21T15:00:00+08:00",
    "priority": "high"
  },
  "warnings": []
}
```

For chat intent routing, return an intent and optional reply:

```json
{
  "intent": "create_task",
  "confidence": 0.88,
  "reply": "我先整理成一个待确认事项，你确认或修改后再保存。",
  "warnings": []
}
```

The backend always keeps the original request `source`, validates the provider
response against current schemas, and still requires user confirmation before
creating formal bills or tasks. If the external parser fails, returns invalid
JSON, or is blocked by local-only privacy mode, parsing falls back to the
rule-based parser with a warning such as `external_ai_parser_failed`. Chat
intent routing also falls back to the local keyword router with warnings such as
`external_chat_intent_invalid_response`.

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

When `LIFESNAP_AI_PARSE_ENDPOINT` is configured and privacy settings allow
external processing, chat intent routing first calls the external provider with
`kind: "chat_intent"`. If that call fails or local-only mode is enabled, the
backend falls back to the built-in keyword router.

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
do not pass `save_original` will keep the original file under
`backend/data/attachment_files/`. When
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

View a retained original attachment file:

```text
GET /attachments/{attachment_id}/content
```

This returns the original image or PDF only when the upload kept
`save_original=true`; otherwise it returns `404`.

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

This uses stored OCR text and the configured bill parser. If no external AI
parser is configured, it falls back to the rule-based bill parser.

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

OCR can use either stored OCR text or a configured external HTTP provider. When
`LIFESNAP_OCR_ENDPOINT` is not set, the backend returns stored OCR text when
available. If the attachment has no OCR text, it returns:

```json
{
  "status": "manual_required",
  "text": null,
  "manual_entry_required": true,
  "warnings": ["ocr_engine_not_configured", "manual_entry_required"]
}
```

Configure an external OCR provider:

```powershell
$env:LIFESNAP_OCR_ENDPOINT = "https://your-ocr-service.example.com/recognize"
$env:LIFESNAP_OCR_API_KEY = "optional-secret"
$env:LIFESNAP_OCR_PROVIDER = "external_http"
$env:LIFESNAP_OCR_TIMEOUT_SECONDS = "15"
```

The backend sends this JSON payload to the endpoint:

```json
{
  "attachment_id": "00000000-0000-0000-0000-000000000000",
  "filename": "payment.png",
  "content_type": "image/png",
  "content_base64": "..."
}
```

The provider should return:

```json
{
  "text": "瑞幸咖啡\n微信支付\n实付 18.50 元",
  "confidence": 0.93,
  "provider": "your_ocr_provider",
  "warnings": []
}
```

External OCR requires the original attachment bytes. With the default privacy
setting `save_original_attachments_by_default=false`, uploads are not retained
for external OCR. Enable original attachment retention before upload, or send
OCR text manually through `PATCH /attachments/{attachment_id}/ocr-text`.
External OCR is also blocked while local-only mode or AI text processing
privacy switches are disabled.

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
