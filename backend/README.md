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

Filter bills by month:

```text
GET /bills?year=2026&month=7
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
