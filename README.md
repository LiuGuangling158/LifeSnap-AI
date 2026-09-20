# LifeSnap AI

![LifeSnap AI concept visual](docs/assets/lifesnap-ai-demo-hero.png)

LifeSnap AI is a local-first personal finance workspace with bill capture,
expense analysis, and an AI assistant that turns natural-language intent into
reviewable actions. It is designed as a practical reference implementation for
an AI-enabled financial workflow rather than a chat-only demo.

> The image above is a generated concept visual for presentations. It is not a
> screenshot of the application.

## What It Demonstrates

- Bill, task, diary, attachment, and dashboard workflows backed by SQLite.
- Image bill recognition with a review-before-save flow.
- An Agent runtime with intent routing, RAG retrieval, function calling, and
  traceable tool execution.
- Human correction feedback and repeatable quality evaluation cases.
- Production-oriented request logs, Prometheus metrics, alerts, diagnostics,
  and test layers.
- A local single-user mode; RAG administration is protected by a separate,
  short-lived administrator session.

## Quick Start

1. Copy .env.example to .env and set only the providers you want to use.
   Local fallback behavior remains available when no external model is set.
2. Create and activate a virtual environment:

    cd backend
    python -m venv .venv
    .\\.venv\\Scripts\\Activate.ps1
    pip install -r requirements.txt

3. Start the application:

    uvicorn app.main:app --host 127.0.0.1 --port 8023

Open http://127.0.0.1:8023 in a browser.

## Documentation

- [Architecture](docs/architecture.md): runtime boundaries, data flow, and AI
  execution model.
- [Demo runbook](docs/demo-runbook.md): a concise, repeatable product demo.
- [Business flow review](docs/business-flow-review.md): user journeys and
  product decisions.
- [Enterprise upgrade reference](docs/enterprise-upgrade-reference.md):
  delivery roadmap and readiness criteria.
- [Testing strategy](docs/testing-strategy.md): unit, integration, workflow,
  and browser test layers.
- [Security guide](docs/security.md): privacy, credentials, and production
  deployment boundaries.

## Repository Layout

| Path | Purpose |
| --- | --- |
| frontend | Static web client, internationalization, and Playwright usability checks |
| backend | FastAPI APIs, Agent services, persistence, and backend tests |
| docs | Architecture, operating guides, review material, and demo assets |
| monitoring | Prometheus scrape configuration and alert rules |
| .github | Continuous-integration workflow |

## Verification

See [the testing strategy](docs/testing-strategy.md) for local commands. The
CI workflow validates backend unit, integration, and workflow tests plus
frontend static and browser usability checks.
