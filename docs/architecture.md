# Architecture

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
| Domain services | Own bill, task, diary, attachment, dashboard, idempotency, audit, and settings behavior. |
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
