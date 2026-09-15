# LifeSnap AI Enterprise Upgrade Reference

Reviewed: 2026-09-15

## Purpose

This document turns the current LifeSnap AI prototype into a reference plan for
an enterprise-grade AI product. The goal is not only to add more features, but
to make the project recognizable to senior engineering reviewers: clear business
workflow, maintainable architecture, reliable AI Agent behavior, measurable
quality, security controls, observability and deployment readiness.

Recommended positioning:

> LifeSnap AI Enterprise Finance Agent: a privacy-aware AI finance assistant
> with multimodal bill capture, RAG knowledge management, function calling,
> deterministic budget analysis and auditable Agent execution traces.

## Enterprise Review Criteria

The project should be evaluated against five dimensions.

1. Product completeness: the user can finish a full workflow from bill input to
   confirmation, analysis and correction without leaving the app.
2. Engineering maturity: the system has clear module boundaries, stable APIs,
   automated tests, repeatable setup and safe configuration handling.
3. AI credibility: Agent behavior is traceable, tool-augmented, grounded by RAG
   knowledge and guarded by deterministic validation.
4. Security and privacy: sensitive finance data, images and model credentials
   have explicit controls, audit logs and access boundaries.
5. Operability: failures are observable, diagnosable and recoverable in local,
   staging and production-like environments.

## Reference Standards

- [The Twelve-Factor App](https://www.12factor.net/): configuration,
  dependency isolation, build-release-run separation, stateless processes and
  logs as event streams.
- [OWASP ASVS](https://owasp.org/www-project-application-security-verification-standard/):
  application security requirements for authentication, authorization, input
  validation, file handling, logging and secrets.
- [NIST SSDF SP 800-218](https://www.nist.gov/publications/secure-software-development-framework-ssdf-version-11-recommendations-mitigating-risk):
  secure software development practices across planning, implementation,
  verification and vulnerability response.
- [OpenTelemetry](https://opentelemetry.io/docs/what-is-opentelemetry/):
  traces, metrics and logs for understanding system behavior and diagnosing
  unknown failures.

## Target Architecture

Keep the system as a modular monolith first. For this project, a clean modular
monolith is more valuable than premature microservices.

Recommended backend layers:

- API layer: FastAPI routes, request validation, response schemas and HTTP error
  mapping.
- Service layer: business workflows such as bill confirmation, Agent chat,
  budget analysis, RAG updates and privacy decisions.
- Repository layer: database access, transactions and persistence boundaries.
- Domain layer: bill, task, diary, attachment, candidate, knowledge document and
  audit concepts.
- Provider layer: DeepSeek, Kimi, SiliconFlow, mock AI, OCR and future model
  providers behind stable interfaces.

Recommended frontend boundaries:

- Route-level views: dashboard, bills, assistant, settings, admin and diagnostics.
- Shared UI primitives: buttons, forms, charts, empty states, dialogs and toasts.
- API client: one place for request handling, errors and auth headers.
- State modules: bills, candidates, Agent runtime, knowledge base, settings and
  language preferences.

## Product Upgrade Plan

### 1. Full Business Workflow

Goal: make the product feel complete without relying on developer explanation.

Recommended work:

- Dashboard: show monthly income, expense, balance, budget progress, abnormal
  spending and latest Agent suggestions.
- Bills: support search, filters, pagination, edit, delete, export, import,
  duplicate detection and category correction.
- Assistant: support text bills, image bills, budget questions, spending trend
  analysis and candidate correction before save.
- Admin: manage RAG knowledge, search test, version history, rollback and audit
  events.
- Settings: manage language, currency, timezone, privacy mode, model provider,
  image retention and export behavior.

Acceptance criteria:

- Upload a bill image, recognize it, create a candidate, edit optional fields and
  confirm it as a bill.
- Ask the Agent about monthly spending and budget. The answer must include chart
  data, deterministic totals and an AI assessment.
- Update RAG knowledge from the Admin page, test retrieval, then verify the next
  Agent answer uses the new knowledge.

### 2. Data Persistence Upgrade

Goal: replace prototype persistence with transactional storage.

Recommended work:

- Use SQLite for local development and PostgreSQL for production-like profiles.
- Add migrations with Alembic.
- Create tables for users, bills, tasks, diaries, attachments, candidates,
  knowledge documents, knowledge versions, audit logs and idempotency records.
- Wrap candidate confirmation, bill creation and idempotency writes in one
  transaction.
- Keep JSON export and import as backup features, not as the primary database.

Acceptance criteria:

- Concurrent confirmation requests cannot create duplicate bills.
- Data survives restart and schema changes through migrations.
- Smoke tests can run against an isolated test database.

### 3. Authentication And Authorization

Goal: move from local prototype to user-aware system.

Recommended work:

- Add login with secure session or JWT strategy.
- Add roles: user and admin.
- Restrict admin routes for RAG management, provider diagnostics and key reveal.
- Scope bills, tasks, diaries and attachments by user.
- Add audit events for login, export, delete, admin key access and RAG update.

Acceptance criteria:

- A normal user cannot call admin knowledge update endpoints.
- User A cannot read or modify User B's records.
- Admin actions appear in the audit log with actor, action, time and target.

## AI Agent Upgrade Plan

### 1. Standard Agent Execution Chain

Target chain:

1. Receive user text, voice transcript or attachment context.
2. Run privacy guard and local-only policy checks.
3. Classify intent: bill creation, bill analysis, candidate update, task, diary,
   knowledge question or general chat.
4. Retrieve relevant RAG knowledge.
5. Select function calls for deterministic work.
6. Execute tools locally.
7. Ask the external model only for language understanding or final explanation
   when privacy settings allow it.
8. Validate structured output.
9. Create a candidate or return analysis.
10. Require user confirmation before saving persistent business records.

Recommended tools:

- `privacy_guard`: decide whether external AI can receive text or images.
- `knowledge_search`: retrieve local RAG knowledge.
- `route_chat_intent`: identify the user's intent.
- `classify_bill_category`: infer category from merchant, item and context.
- `parse_bill_candidate`: create a bill candidate.
- `analyze_bills`: compute deterministic statistics and chart data.
- `update_candidate`: apply follow-up corrections.
- `confirm_candidate`: persist after user confirmation.
- `discard_candidate`: cancel a candidate.

Acceptance criteria:

- Every Agent reply can show knowledge hits, called tools, model provider,
  fallback mode and validation result.
- Budget and spending questions never rely on model-invented numbers.
- External model failure falls back to local parsing or asks a clarification
  question instead of silently failing.

### 2. RAG Knowledge Base

Goal: make RAG visible and manageable, not hidden inside prompts.

Recommended work:

- Keep built-in product rules in code.
- Store admin-managed knowledge in the database.
- Add knowledge versions with diff, author, timestamp and rollback.
- Add search test on Admin page.
- Add JSON import/export for knowledge documents.
- Track which knowledge documents are used by each Agent turn.

Acceptance criteria:

- Admin can view the full active knowledge base.
- Admin can add or override knowledge by `source_id`.
- Disabled knowledge no longer appears in search or Agent grounding.
- Agent trace shows the exact documents used in a response.

### 3. Fine-Tuning Readiness

Goal: show serious model lifecycle thinking without claiming unsupported results.

Recommended work:

- Export supervised training examples from confirmed user corrections.
- Add sample quality checks: missing labels, contradictory labels, low-confidence
  OCR and duplicated samples.
- Add fine-tuned model configuration fields but keep base model fallback.
- Add evaluation sets for intent routing, category classification, image bill
  extraction and budget answers.

Acceptance criteria:

- The project can export a clean training dataset.
- Evaluation reports show accuracy, failure examples and regression changes.
- UI distinguishes base model, fine-tuned model, external parser and local
  fallback.

## Security And Privacy Plan

### Secrets And Provider Credentials

Recommended work:

- Keep model API keys only in backend environment variables.
- Never persist or log full API keys.
- Redact keys in diagnostics, errors and audit metadata.
- Keep local admin key reveal disabled by default and restricted to localhost.
- Add provider health checks that do not leak secrets.

Acceptance criteria:

- Frontend never stores real provider keys.
- Logs do not contain full keys, image base64 or sensitive bill text.
- Admin key reveal cannot be called from non-localhost clients.

### Privacy Controls

Recommended work:

- Add explicit switches for local-only mode, AI text processing, AI image
  processing and original image retention.
- Show what data will be sent to external AI before enabling it.
- Redact financial totals from external tool payloads when deterministic local
  calculations are available.
- Make image retention configurable per user.

Acceptance criteria:

- When local-only mode is on, no external model request is sent.
- User can disable saving original uploaded images.
- Audit events record privacy setting changes.

### File Upload Safety

Recommended work:

- Restrict allowed content types and file sizes.
- Store uploaded files outside executable paths.
- Generate safe internal attachment IDs instead of trusting filenames.
- Add content serving authorization.
- Clean orphaned uploads after candidate discard when retention is disabled.

Acceptance criteria:

- Invalid files are rejected with clear errors.
- Attachment URLs cannot access files outside the attachment directory.
- User A cannot fetch User B's attachment content.

## Engineering Quality Plan

### Automated Tests

Recommended test layers:

- Unit tests for category inference, intent routing, privacy guards and RAG
  search scoring.
- API tests for CRUD, candidate confirmation, admin knowledge update and export.
- Agent workflow tests for parse, update, confirm, discard and bill analysis.
- OCR/provider tests with mock providers.
- Frontend syntax, component behavior and end-to-end smoke tests.

Acceptance criteria:

- CI runs backend tests, frontend checks and smoke tests.
- Critical business workflows have regression tests.
- Provider failures are tested through mocks.

### CI/CD And Developer Experience

Recommended work:

- Add one-command setup and run scripts.
- Add Docker Compose for backend, frontend, database, mock AI and optional
  observability stack.
- Add lint, format, type check and security scan jobs.
- Add pull request template with test evidence checklist.
- Add OpenAPI documentation and API examples.

Acceptance criteria:

- A new developer can run the project from README instructions in less than 15
  minutes.
- CI fails on syntax errors, broken tests, dependency issues and unsafe diffs.
- API docs match the running backend.

## Observability And Operations Plan

Recommended signals:

- Logs: structured JSON logs with request ID, user ID, agent trace ID, tool name
  and provider name.
- Metrics: request latency, error rate, OCR success rate, model call success
  rate, candidate confirmation rate and bill analysis latency.
- Traces: one trace per Agent turn, with spans for privacy check, RAG search,
  model call, tool call, validation and persistence.
- Health checks: database, storage, RAG index, OCR provider, LLM provider and
  privacy configuration.

Acceptance criteria:

- A failed image recognition can be diagnosed as upload, OCR provider, JSON
  parsing, privacy blocking or candidate validation failure.
- Agent latency can be broken down by RAG, model and local tool execution.
- Runtime diagnostics page shows configured provider, readiness and blockers.

## Documentation Plan

Recommended documents:

- `README.md`: product overview, screenshots, quick start, tests and demo flow.
- `docs/architecture.md`: module boundaries, data flow and deployment view.
- `docs/ai-agent.md`: Agent chain, RAG, function calling, model providers and
  fine-tuning readiness.
- `docs/security.md`: authentication, secrets, privacy, uploads and audit logs.
- `docs/operations.md`: configuration, health checks, logs, metrics and traces.
- `docs/demo-script.md`: 3-minute demo, 10-minute demo and technical interview
  demo.
- `docs/api.md`: common API examples or generated OpenAPI export notes.

Acceptance criteria:

- A reviewer can understand the product value without running the app.
- A developer can run, test and extend the app from documentation alone.
- A technical interviewer can see the AI and engineering depth within 10 minutes.

## Priority Roadmap

### P0: Enterprise Foundation

These items should be done first because they change project credibility the
most.

1. Replace JSON persistence with SQLite/PostgreSQL plus migrations.
2. Add authentication, user scoping and admin authorization.
3. Add Agent trace panel with RAG hits, function calls and model strategy.
4. Add RAG version history and rollback.
5. Add Docker Compose one-command startup.
6. Add end-to-end demo flow test: image bill to saved bill to budget analysis.

### P1: Engineering Maturity

1. Add CI pipeline for backend tests, frontend checks and smoke tests.
2. Add OpenAPI docs and API examples.
3. Add structured audit logs for admin and data-sensitive actions.
4. Add provider diagnostics and model readiness page.
5. Add observability instrumentation for traces, metrics and logs.
6. Expand regression coverage around Agent workflows.

### P2: Product Differentiation

1. Add multi-tenant organization support.
2. Add report center for monthly, quarterly and category analysis.
3. Add budget rule engine and abnormal spending alerts.
4. Add bill import templates for common payment platforms.
5. Add model evaluation dashboard.
6. Add PWA/mobile experience optimization.

## Interview And Portfolio Narrative

Suggested short pitch:

> LifeSnap AI started as a personal finance assistant and was upgraded into an
> enterprise-style AI finance Agent. It combines deterministic finance logic with
> LLM-based understanding, RAG knowledge grounding, function calling, OCR bill
> recognition, privacy controls and auditable execution traces. The architecture
> keeps AI output behind validation and user confirmation, so the model assists
> the workflow without owning the source of truth.

Technical highlights to emphasize:

- AI Agent chain is explicit and auditable.
- Finance totals and charts are computed locally, not hallucinated by the model.
- RAG knowledge can be inspected, searched, updated and versioned.
- External AI is controlled by privacy settings and provider readiness checks.
- The system is designed for migration from local prototype to database-backed,
  authenticated, observable deployment.

## Definition Of Done For Enterprise Upgrade

The project can be considered enterprise-ready for portfolio review when these
conditions are met.

- Core user workflow works end to end with repeatable tests.
- Data persistence is transactional and migration-managed.
- Authentication, authorization and user scoping are implemented.
- Admin operations are protected and audited.
- Agent responses expose RAG, function calling and model trace details.
- External AI usage is governed by privacy settings.
- CI runs automatically and catches regressions.
- Docker Compose can start a complete local environment.
- Documentation explains architecture, AI design, security and operations.
- A demo script can show the system value in under 10 minutes.
