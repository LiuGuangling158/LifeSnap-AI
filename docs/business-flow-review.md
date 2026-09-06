# Business Flow Review

Reviewed: 2026-09-06

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
- Bill candidates reject nonpositive amounts and empty merchant values.
  A zero amount in rule parsing produces an incomplete candidate for correction.
- Record and candidate PATCH requests distinguish omitted fields from null.
  Required fields reject null with the standard 422 response. Optional bill
  notes/payment methods and diary weather can now actually be cleared.
- Saved bill timestamps cannot be cleared because list and statistics operations
  require them. Creation without a timestamp still uses the creation time.
- Chat send/confirm/discard ignore repeated submissions while processing.
  Confirm/discard reuse a stable candidate-specific idempotency key on retry.

## Verification

The isolated smoke suite checks CRUD, statistics, candidate editing, confirmation,
idempotency, privacy, attachments/OCR fallback, recovery, imports and exports.
New regressions exercise null updates without record mutation, optional-field
clearing, intent routing, transaction types, zero amounts and confirmation replay.
Frontend JavaScript syntax is checked separately.

Browser automation could not initialize because the Windows sandbox failed to
apply its filesystem ACLs. Visual layout and interactive browser checks are not
claimed as verified. External model quality is not tested without model credentials.

## Remaining Product Work

1. Chat requests currently contain one message, without a conversation or pending
   candidate reference. Follow-up answers cannot reliably complete the preceding
   candidate. Add explicit conversation context and candidate revision handling.
2. The notification center displays tasks; it is not background notification
   delivery. Define the intended target (web, desktop or Android), timezone and
   delivery behavior before implementing scheduling and notification permissions.
3. Image chat processing can skip accompanying text once an image candidate exists.
   Combine image extraction and user instructions in a single candidate workflow.
4. Local JSON stores are suitable for the existing local prototype, but are not a
   transactional multi-worker database. Candidate confirmation and persisted
   idempotency records need an atomic transaction before multi-user deployment.
5. Date boundaries differ between UTC task summaries and stored bill timestamps.
   Choose a configurable business timezone and test midnight/month-end boundaries.
6. Cross-record natural-language analysis is excluded by the execution plan and
   is not provided by the current intent router. A future analysis tool should
   retrieve scoped records, calculate totals deterministically, then ask the
   model to explain those verified results.
