# Business Flow Review

Reviewed: 2026-09-07

## Scope

The execution plan defines the MVP as image/OCR or text input, candidate extraction,
user editing and confirmation, saved records, lists and statistics. Tasks, diaries,
privacy controls, recovery and export are supporting workflows.

## Changes

- Chat fallback prioritizes explicit reminder requests while keeping monetary
  descriptions such as ordering coffee in the bill flow.
- Rule parsing recognizes income, refunds, transfers and top-ups instead of
  recording every transaction as an expense. This is heuristic fallback;
  candidates still require review before saving.
- Bill category inference now uses a shared classifier across rule parsing,
  contextual chat updates and external-model post-processing. Explicit user
  categories win first; otherwise common merchant, item and scenario keywords
  infer categories such as 餐饮, 交通, 购物, 日用, 医疗, 娱乐, 学习 and 住房.
  Near-synonyms such as 居住 are normalized to the configured category 住房.
- Agent responses now expose runtime trace fields for RAG knowledge hits,
  internal function calls and model strategy. Each chat turn uses a function-call
  session for privacy checks, knowledge search, routing, candidate parsing and
  context actions; compatible LLM calls can also execute safe read-only tool
  calls before returning strict JSON. The runtime profile is available through
  `/agent/runtime`, the local knowledge base through `/agent/knowledge/search`,
  and supervised fine-tuning examples through `/agent/fine-tuning/examples`.
- DeepSeek can now be selected as the built-in LLM provider with
  `DEEPSEEK_API_KEY`. The backend defaults to `https://api.deepseek.com` and
  `deepseek-v4-flash`, then keeps the same RAG, function-calling and
  confirmation-before-save workflow.
- Agent runtime readiness is now explicit. `/agent/runtime` and chat
  `model_trace` distinguish external model configured, external model ready,
  local fallback active, privacy blockers, credential blockers, function-calling
  mode and the next setup action, so the UI does not present a blocked DeepSeek
  config as an active model.
- Bill analysis queries such as "这个月餐饮花了多少" now route to a read-only
  `analyze_bills` function call. The Agent retrieves local statistics and
  computes category totals, monthly totals, previous-month deltas, budget usage,
  top spending day and merchant highlights
  deterministically instead of asking the model to invent numbers.
- Bills and bill candidates now require only amount and transaction type to save.
  Merchant, category, payment method, time and note can be left blank in the UI;
  blank merchant values are stored as null and displayed as 未填写.
- Bill candidates reject nonpositive amounts. A zero amount in rule parsing
  produces an incomplete candidate for correction.
- Record and candidate PATCH requests distinguish omitted fields from null.
  Required fields reject null with the standard 422 response. Optional bill
  notes/payment methods and diary weather can now actually be cleared.
- Saved bill timestamps cannot be cleared because list and statistics operations
  require them. Creation without a timestamp still uses the creation time.
- Chat send/confirm/discard ignore repeated submissions while processing.
  Confirm/discard reuse a stable candidate-specific idempotency key on retry.
- Chat messages can now carry the active candidate context. The Agent can update
  an existing bill, task or diary candidate from follow-up text before saving.
- Context messages support typed confirmation and discard, so users can say
  "确认保存" or "不保存" while a pending candidate is active.
- Image chat no longer drops accompanying text after creating a bill candidate;
  the text is forwarded as a contextual follow-up that can correct the image
  candidate.
- The chat UI now renders the Agent's execution steps and keeps the original
  candidate card in sync when follow-up text updates it.

## Verification

The isolated smoke suite checks CRUD, statistics, candidate editing, confirmation,
idempotency, privacy, attachments/OCR fallback, recovery, imports and exports.
New regressions exercise null updates without record mutation, optional-field
clearing, intent routing, transaction types, zero amounts, confirmation replay,
bill category inference, deterministic bill analysis, minimal bill confirmation
without merchant, contextual candidate updates, typed confirmation, typed
discard, RAG search, required function-call coverage for
parse/update/confirm/discard/analyze paths and fine-tuning dataset export.
Frontend JavaScript syntax is checked separately.

Browser automation could not initialize because the Windows sandbox failed to
apply its filesystem ACLs. Visual layout and interactive browser checks are not
claimed as verified. External model quality is not tested without model credentials.

## Remaining Product Work

1. Candidate context is request-scoped and client supplied. It now supports the
   main single-device chat flow, but does not yet include server-side sessions,
   candidate revisions or conflict detection across tabs/devices.
2. The notification center displays tasks; it is not background notification
   delivery. Define the intended target (web, desktop or Android), timezone and
   delivery behavior before implementing scheduling and notification permissions.
3. Local JSON stores are suitable for the existing local prototype, but are not a
   transactional multi-worker database. Candidate confirmation and persisted
   idempotency records need an atomic transaction before multi-user deployment.
4. Date boundaries differ between UTC task summaries and stored bill timestamps.
   Choose a configurable business timezone and test midnight/month-end boundaries.
5. Bill statistics questions are now supported for local monthly totals,
   category spend and merchant highlights. Broader cross-record analysis across
   diaries, tasks, subscriptions and warranties still needs scoped retrieval,
   deterministic calculations and a separate explanation layer.
