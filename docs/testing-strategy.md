# Testing Strategy

LifeSnap uses layered tests so that a fast failure points to the smallest
relevant boundary before the end-to-end workflow is exercised.

## Layers

| Layer | Location | Scope | Expected cadence |
| --- | --- | --- | --- |
| Unit | backend/tests/unit | Deterministic service logic, signatures, normalization, calculations | Every local change and pull request |
| Integration | backend/tests/integration | Public HTTP contracts with an isolated SQLite data directory | Every pull request |
| Workflow | backend/scripts/smoke_test.py | Real Uvicorn process, API business flows, agent tools, RAG, quality, and metrics | Every pull request |
| Browser usability | frontend/scripts/usability_smoke.cjs | Desktop and mobile workflows in Playwright | Every pull request |

Unit and integration tests must not use the developer's local database. The
test runner provides a fresh LIFESNAP_DATA_DIR for each invocation.

## Commands

Run these commands from the repository root:

    .\\backend\\.venv\\Scripts\\python.exe -m pip install -r .\\backend\\requirements-dev.txt
    .\\backend\\.venv\\Scripts\\python.exe .\\backend\\scripts\\test_runner.py unit
    .\\backend\\.venv\\Scripts\\python.exe .\\backend\\scripts\\test_runner.py integration
    .\\backend\\.venv\\Scripts\\python.exe .\\backend\\scripts\\test_runner.py workflow
    npm --prefix frontend ci
    npm --prefix frontend run check
    npm --prefix frontend run test

The GitHub Actions workflow runs the backend layers in order and runs the
frontend syntax and Playwright checks in a separate job. A failed lower layer
should be fixed before diagnosing a higher layer failure.

## Test Design Rules

- Add pure classification, parsing, and policy behavior to the unit layer.
- Add route status codes and response-shape guarantees to the integration layer.
- Cover candidate-session revision changes, stale-write conflicts and final
  confirmation or discard transitions in integration tests.
- Add cross-service, persistence, agent tool, and observability scenarios to the workflow layer.
- Add primary user-visible flows and responsive layout regressions to the browser layer.
- Use synthetic data only. Do not put API keys, uploaded bill images, or real personal finance data in fixtures, logs, or assertions.
