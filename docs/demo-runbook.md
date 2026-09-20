# Demo Runbook

## Purpose

This script demonstrates that LifeSnap AI is a working financial workflow with
controlled AI actions, not only a conversational prototype. It is suitable for
a five-to-eight-minute product review.

## Before the Demo

1. Start the backend on port 8023 and open the application in a clean browser
   profile.
2. Prepare one non-sensitive receipt image or use manual entry if external
   image recognition is not configured.
3. In Settings, confirm the intended provider configuration. Do not reveal
   API keys in the demo.
4. For an RAG administration demo, set LIFESNAP_ADMIN_KEY locally and use the
   administrator page to create a short-lived session.
5. Keep the concept visual at docs/assets/lifesnap-ai-demo-hero.png available
   as the opening slide image; it is explicitly a concept visual, not a product
   screenshot.

## Demo Flow

### 1. Establish the Value

Open the dashboard and explain the loop: capture a bill, understand spending,
ask the assistant, review every write action, and use feedback to improve
quality. Point out the current-month summary and recent activity.

### 2. Capture a Bill

Use the manual entry form with an amount and bill type only; explain that the
remaining fields are optional. Then upload a non-sensitive receipt image. The
system should present extracted fields for confirmation. If recognition is
unavailable, demonstrate the fallback prompt and complete the record manually.

Success signal: the record appears in the bill list and dashboard after an
explicit save.

### 3. Ask for Analysis

In the assistant, ask a question such as "How is my spending this month?" or
"Am I on track with my budget?".

Success signal: the response returns a written assessment and chart-ready
spending analysis without creating or changing a bill.

### 4. Demonstrate Function Calling Safely

Ask the assistant to record a small expense in natural language, for example:
"I spent 28 yuan on lunch today." Review the candidate, adjust a value, and
select the explicit save action.

Success signal: the UI displays Agent execution steps, the candidate can be
edited, and only the confirmation creates the bill.

### 5. Demonstrate RAG Administration

Open the administrator page and inspect the existing knowledge list. Add or
revise a category policy, run the knowledge test, then show its version
history. Roll back instead of deleting if the content should be reverted.

Success signal: knowledge administration is separate from ordinary financial
operations and uses a short-lived administrator session.

### 6. Demonstrate Quality and Operations

Submit feedback on an assistant answer. In the administrator area, run an AI
quality evaluation. Then open the diagnostics or observability view and explain
the health signal, trace privacy controls, and Prometheus metrics endpoint.

Success signal: product quality has a feedback loop and operational signals,
not only a one-time model response.

## Closing Message

LifeSnap AI combines structured personal finance data with an AI assistant that
has constrained tools, managed knowledge, explicit confirmation for mutations,
and measurable quality. The roadmap is to scale the same boundaries rather
than replace the workflow after a pilot.

## Presenter Notes

- Never expose API keys, raw receipt content, or personal records.
- Do not promise perfect OCR or categorization. Show the review and correction
  workflow as the deliberate product control.
- If an external provider is unavailable, use local fallback behavior and
  explain that provider health is independently observable.
