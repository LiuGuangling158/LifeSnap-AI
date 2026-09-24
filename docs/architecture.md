# Architecture

[简体中文](architecture.zh-CN.md) | English

## System Boundary

LifeSnap AI is a FastAPI application that serves both the public API and the
static frontend. It is intentionally deployable as one local process for
personal use, while keeping service boundaries explicit enough to move SQLite,
provider adapters, monitoring, or the frontend independently when needed.

    Web client
        |
        v
    FastAPI API -----> Logs, metrics, quality
        |
        +---- Domain services and SQLite
        |
        +---- Agent runtime ---> RAG knowledge base
        |           |
        |           +-----------> Function tool registry ---> SQLite
        |           |
        |           +-----------> External AI providers
        |
        v
    Static frontend

## Core Components

| Component | Responsibility |
| --- | --- |
| Frontend | Presents bills, tasks, diaries, charts, administration, and review states. It does not hold provider secrets. |
| API layer | Validates requests, maps domain errors to stable response shapes, and exposes capabilities, diagnostics, metrics, and application data. |
| Domain services | Own bill, task, diary, attachment, dashboard, report, idempotency, audit, and settings behavior. |
| SQLite state store | Persists application state with WAL mode, schema migration metadata, and immediate transactions for confirmation flows. |
| Agent runtime | Routes intent, retrieves knowledge, chooses supported tools, validates tool results, and returns a reviewable response. |
| RAG knowledge base | Stores managed knowledge entries and versions; administrators can inspect, update, test, and roll back knowledge. |
| Provider adapters | Call configured OpenAI-compatible chat or vision endpoints with timeouts and local fallback behavior. |
| Quality and observability | Records privacy-safe Agent traces, collects feedback and evaluation runs, and exports Prometheus-compatible metrics. |

## Agent Execution

    User -> Web client: message or bill image
    Web client -> Agent runtime: intent and permitted context
    Agent runtime -> RAG knowledge base: retrieve relevant policy and category knowledge
    Agent runtime -> AI provider: structured intent when configured
    Agent runtime -> Function tool: invoke an allow-listed action
    Function tool -> SQLite: read or prepare domain state
    SQLite -> Agent runtime: typed, validated result
    Agent runtime -> Web client: candidate, chart data, or answer
    User -> Web client: review, edit, confirm, or correct
    Agent runtime -> quality and metrics: privacy-safe trace

The Agent never directly writes a bill merely because a model produced text.
Write-like actions create a candidate that the user can edit and confirm.
Read-only questions can return analysis and chart-ready data without changing
personal records.

Each chat candidate is paired with a persisted server-side session containing
an action type, candidate ID, lifecycle status and monotonically increasing
revision. Edit, confirm and discard requests carry the expected revision and
run their domain mutation plus session transition inside one SQLite
transaction. A stale browser tab receives HTTP 409 instead of overwriting the
latest candidate state.

## Data and Security Boundaries

- External model calls are opt-in through environment configuration. Credentials
  stay server-side in environment variables and must never be shipped to the
  browser.
- Request logs and Agent traces omit chat text, OCR text, attachment bytes, and
  credentials.
- Uploaded attachment bytes are managed as files; transactional application
  state lives in SQLite.
- The application is local single-user by design. Knowledge-base writes require
  a separately issued, short-lived administrator session.
- The Prometheus endpoint is operationally useful but should be network
  restricted in a production deployment.

## Operational Signals

The application exports request counts, latency summaries, Agent execution
counts, Agent P95 latency, and uptime at /metrics. The included monitoring
configuration and alert rules are starter assets: production deployment must
replace the scrape target and configure a real alert delivery destination.

## Evolution Path

1. Keep the current single-process deployment for local and pilot use.
2. Move SQLite to a managed relational database when concurrent multi-user
   writes become a requirement.
3. Move attachments to object storage and RAG embeddings to a managed vector
   service when data volume requires it.
4. Add identity, tenant isolation, secret management, and a network policy
   before exposing the service publicly.

## Hybrid RAG Retrieval

Knowledge documents are split into traceable chunks and retrieved with local BM25 first. When an OpenAI-compatible Embeddings provider is configured and local-only mode is disabled, query and chunk vectors are generated and fused with BM25 using cosine similarity.

- GET /agent/knowledge/search returns the matched chunk_id, retrieval method, BM25 score, and vector score.
- POST /agent/knowledge/reindex requires an administrator session and prebuilds the vector cache for active knowledge chunks.
- The vector cache keeps chunk fingerprints and float vectors only; document text remains in the application database.
- Privacy restrictions, local-only mode, missing Embedding configuration, or provider failures automatically fall back to local BM25 without blocking Agent retrieval.

See .env.example for LIFESNAP_RAG_EMBEDDING_BASE_URL, LIFESNAP_RAG_EMBEDDING_MODEL, LIFESNAP_RAG_EMBEDDING_API_KEY, and LIFESNAP_RAG_SEMANTIC_WEIGHT.

## Agent Evaluation Admission

The versioned suite at backend/evaluations/agent_admission_v1.json is the offline release gate. It covers bill classification, candidate confirmation, tasks, diaries, spending analysis, RAG tool invocation, and rejection of unsafe requests.

- The dataset declares the minimum pass rate; the current baseline is 100 percent.
- Any failed critical case rejects admission even when the aggregate pass rate is met.
- Offline mode bypasses LLM and Embedding providers so CI does not use production credentials, expose evaluation prompts, or consume external quota.
- Run backend/scripts/agent_eval_gate.py. A rejected admission exits non-zero and GitHub Actions blocks the change.
- Administrators can run quality evaluation; stored results include dataset version, mode, critical failures, and the admission decision.

- A same-dataset, same-mode baseline is selected from the latest prior run. Newly failed cases or a lower pass rate are quality regressions and reject admission when `require_no_regression` is enabled.
