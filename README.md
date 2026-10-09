# LifeSnap AI

[简体中文](README.zh-CN.md) | English

![LifeSnap AI concept visual](docs/assets/lifesnap-ai-demo-hero.png)

> The image is a presentation concept visual, not an application screenshot.

LifeSnap AI is a local-first personal finance workspace that turns messages,
receipts, and lightweight daily notes into reviewable actions. It is built as
an Agent engineering project: model output is grounded with managed knowledge,
constrained by tools, confirmed before writes, evaluated before releases, and
observable after deployment.

## Why This Project

Most AI bookkeeping demos stop at extraction or chat. LifeSnap AI focuses on
the operational path after a model responds:

1. Capture a bill, task, diary entry, image, or question.
2. Run privacy checks, knowledge retrieval, intent routing, and tool selection.
3. Produce a candidate rather than mutating financial data immediately.
4. Let the user edit, confirm, or discard the candidate.
5. Record privacy-safe traces, feedback, evaluation evidence, and operational
   signals for continuous improvement.

## Highlights

| Area | Included capabilities |
| --- | --- |
| Personal workspace | Bills, budget and spending reports, tasks, diary entries, attachments, import/export, snapshots, and dashboard summaries |
| Bill capture | Manual entry, image receipt recognition, duplicate checks, field-level candidate review, and explicit confirmation before saving |
| Agent runtime | Intent routing, RAG retrieval, function calling, model/rule fallback, execution steps, and privacy-safe explanations |
| RAG | Editable business knowledge, BM25 retrieval by default, optional embedding fusion, retrieval testing, version history, reindexing, and rollback |
| Quality governance | Offline admission evaluation, RAG-specific evaluation, live shadow evaluation, regression comparison, release snapshots, and rollback controls |
| Feedback loop | User verdicts link to execution traces; administrators review them and promote sanitized examples into regression cases |
| Reliability | Bounded retries, per-provider/model circuit breakers, local fallback, Token and estimated-cost aggregation, and model health alerts |
| Operations | SQLite transactions, durable leased jobs, idempotency controls, audit events, diagnostics, Prometheus metrics, alert state, and layered tests |

## Agent Execution Flow

```text
User message / image
        |
Privacy guard and attachment validation
        |
RAG retrieval (BM25, optionally fused with embeddings)
        |
Intent routing (LLM when configured, deterministic fallback otherwise)
        |
Function calling: knowledge search / bill candidate / task / diary / analysis
        |
Candidate session with revision and conflict control
        |
User edit + explicit confirm or discard
        |
SQLite persistence, audit event, Agent trace, metrics, and feedback loop
```

The Agent never treats a model response as authorization to write a bill, task,
or diary record. Write-oriented tools return a candidate first. The user must
explicitly confirm it, and stale candidate revisions are rejected.

## Architecture At A Glance

```text
frontend/                 Static bilingual web client
    |
FastAPI application       APIs, middleware, validation, static delivery
    |
service layer             Agent, RAG, OCR, reports, jobs, observability
    |
SQLite + managed files    Transactions, state, candidates, traces, audit data
    |
optional providers        DeepSeek / SiliconFlow / Kimi / OpenAI-compatible embeddings
```

The default deployment profile is a single local workspace. Business APIs do
not expose registration or login. Sensitive governance operations, such as RAG
writes, release actions, job controls, and feedback review, use a short-lived
administrator session issued from a server-side admin key.

## Quick Start

### Prerequisites

- Python 3.12 recommended
- Node.js 22 recommended for frontend browser tests
- No external AI credential is required for the local fallback experience

### Run Locally

```powershell
Copy-Item .env.example .env

Set-Location backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt

uvicorn app.main:app --host 127.0.0.1 --port 8023
```

Open [http://127.0.0.1:8023](http://127.0.0.1:8023). API documentation is
available at [http://127.0.0.1:8023/docs](http://127.0.0.1:8023/docs), and
Prometheus-format metrics are available at `/metrics`.

On macOS or Linux, use `python3 -m venv .venv` and `source .venv/bin/activate`
instead of the PowerShell activation command.

## Optional AI Provider Setup

Start with `.env.example`; leave a provider unset to keep its local fallback.
Credentials stay on the server and must never be committed.

| Need | Main settings |
| --- | --- |
| Chat intent and Agent routing | `LIFESNAP_LLM_PROVIDER`, `LIFESNAP_LLM_BASE_URL`, `LIFESNAP_LLM_MODEL`, `LIFESNAP_DEEPSEEK_CHAT_API_KEY` |
| Default bill/task/diary parsing | `LIFESNAP_DEFAULT_AI_PROVIDER`, `LIFESNAP_DEFAULT_AI_BASE_URL`, `LIFESNAP_DEFAULT_AI_MODEL`, `LIFESNAP_DEFAULT_AI_API_KEY` |
| Receipt image recognition | `LIFESNAP_OCR_PROVIDER`, `LIFESNAP_OCR_ENDPOINT`, `LIFESNAP_OCR_MODEL`, `LIFESNAP_IMAGE_BILL_API_KEY` |
| Semantic RAG fusion | `LIFESNAP_RAG_EMBEDDING_BASE_URL`, `LIFESNAP_RAG_EMBEDDING_MODEL`, `LIFESNAP_RAG_EMBEDDING_API_KEY` |
| Model resilience and cost | `LIFESNAP_MODEL_MAX_RETRIES`, `LIFESNAP_MODEL_CIRCUIT_FAILURE_THRESHOLD`, input/output cost-per-million settings |
| Administration | `LIFESNAP_ADMIN_KEY` |

The invocation gateway retries transient failures only, opens a temporary
circuit breaker after consecutive final failures, and falls back to local rules
where the workflow supports it. Model usage records are aggregated by provider
and model; prompts, responses, images, and keys are not stored in these
metrics.

## Administration And Quality Loop

The **Admin** page supports non-JSON knowledge management and Agent governance:

- Edit, search, test, version, reindex, reset, and roll back RAG knowledge.
- Run offline admission and optional live shadow evaluations.
- Create, promote, or roll back Agent release snapshots bound to RAG and model
  fingerprints.
- Inspect asynchronous jobs, traces, alerts, model resilience, and aggregated
  cost information.
- Review user feedback. Only an administrator-written sanitized sample and an
  expected intent can become a regression test case; raw user chat content is
  not copied into the evaluation suite.

The offline gate is also executable in CI:

```powershell
Set-Location backend
python scripts/agent_eval_gate.py
```

## Test And Verify

Backend tests use a temporary `LIFESNAP_DATA_DIR`, so they do not modify a
developer's local workspace. Run these commands from the repository root:

```powershell
.\backend\.venv\Scripts\python.exe .\backend\scripts\test_runner.py all
.\backend\.venv\Scripts\python.exe .\backend\scripts\agent_eval_gate.py

npm --prefix frontend ci
npm --prefix frontend run check
npm --prefix frontend run test
```

Test layers cover unit services, HTTP contracts, a real Uvicorn workflow smoke
test, offline Agent/RAG admission, and Playwright usability checks across
desktop and mobile layouts. GitHub Actions runs these checks for pull requests
and pushes to `main`.

## Repository Guide

| Path | Description |
| --- | --- |
| `frontend/` | Static web application, bilingual runtime translation, styles, and Playwright smoke test |
| `backend/app/api/` | FastAPI route layer and HTTP contracts |
| `backend/app/services/` | Domain services, Agent runtime, RAG, OCR, jobs, persistence, and operations |
| `backend/evaluations/` | Versioned Agent admission and RAG retrieval suites |
| `backend/tests/` | Unit and integration coverage |
| `docs/` | Architecture, demo guides, product review, security, and upgrade reference |
| `monitoring/` | Prometheus scrape configuration and starter alert rules |
| `.github/workflows/` | Continuous-integration workflow |

## Documentation

- [Architecture](docs/architecture.md) / [技术架构](docs/architecture.zh-CN.md)
- [Demo runbook](docs/demo-runbook.md) / [演示脚本](docs/demo-runbook.zh-CN.md)
- [Business-flow review](docs/business-flow-review.md)
- [Testing strategy](docs/testing-strategy.md)
- [Security and access boundaries](docs/security.md)
- [Enterprise upgrade reference](docs/enterprise-upgrade-reference.md)

## Current Boundary

LifeSnap AI is intentionally a local, single-workspace reference implementation.
Before a public multi-user deployment, move to a managed relational database,
add an identity provider and tenant isolation, place secrets in managed storage,
move attachments and vector indexes to managed services, and protect metrics
and administration with network controls. See the security and enterprise
upgrade documents for the detailed path.
