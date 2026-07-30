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

