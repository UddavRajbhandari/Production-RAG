# Phase 8.4 & 8.5: Production Readiness & Validation

**Project**: Production-Grade RAG Pipeline
**Version**: 1.0
**Date**: May 2026
**Status**: Planned

---

## Table of Contents

1. [Overview](#1-overview)
2. [Current State Assessment](#2-current-state-assessment)
3. [Implementation Steps](#3-implementation-steps)
4. [Files to Modify](#4-files-to-modify)
5. [Verification Strategy](#5-verification-strategy)
6. [Risk Assessment](#6-risk-assessment)

---

## 1. Overview

### Objectives

**Phase 8.4 — Production Readiness**:
1. Enable error tracking via Sentry (SDK already installed, never initialized)
2. Expose Prometheus metrics for latency, error rates, and RAGAS scores
3. Add concurrent load testing capability
4. Document operational runbooks for common scenarios

**Phase 8.5 — Validation**:
1. Wire RAGAS regression guard into CI pipeline
2. Verify end-to-end latency against budget thresholds (p95 ≤ 180s)
3. Validate streaming UX works correctly in the browser
4. Confirm no regression in RAGAS metrics from Phase 6 baselines

### Target Outcomes

| Metric | Target | Current Baseline | Verification |
|--------|--------|------------------|--------------|
| API Latency (p95) | ≤ 180s | TBD | `scripts/profile_full_pipeline.py` |
| Error Tracking | Captured | None | Sentry dashboard |
| Metrics Export | Available | None | `GET /metrics` |
| RAGAS Regression | Blocked in CI | Not gated | CI pipeline |
| Streaming UX | Verified | Not tested | Playwright test |
| Load Test | N=5 concurrent | Not tested | `scripts/load_test.py` |

---

## 2. Current State Assessment

### What Already Exists

| Capability | Status | How |
|-----------|--------|-----|
| Health checks | ✅ Full | `/health`, `/ready`, `/live` with component-level checks |
| Structured logging | ✅ JSON | `LoggingMiddleware` with correlation IDs, per-query fields |
| Rate limiting | ✅ Active | `slowapi`, 60 req/min per API key |
| CI/CD pipeline | ✅ CI + Deploy + Frontend Deploy | lint, typecheck, test, build |
| RAGAS evaluator | ✅ Module exists | `src/evaluation/ragas_evaluator.py` with 68-pair benchmark |
| Docker build | ✅ Enabled | CI `docker-build` job active |
| Storage mode detection | ✅ Cloud/Local | Auto-detection via env vars |
| Sentry SDK | ⚠️ Installed, not initialized | `sentry-sdk[fastapi]` in requirements, no `sentry_sdk.init()` |

### What's Missing

| Capability | Missing Since | Blocking |
|-----------|---------------|----------|
| Sentry initialization | Phase 8.4 | Crashes invisible in production |
| Prometheus metrics | Phase 8.4 | No latency/error visibility |
| RAGAS CI gate | Phase 8.5 | Deployments can silently regress |
| Latency profiling | Phase 8.5 | Budgets defined but untested |
| Load testing | Phase 8.4 | No concurrency validation |
| Runbooks | Phase 8.4 | Operational procedures undocumented |
| Streaming UX test | Phase 8.5 | SSE UI unverified end-to-end |

---

## 3. Implementation Steps

### Step 1: Sentry Initialization

**Why**: Without error tracking, production crashes are invisible. The SDK is installed but never wired up.

**Files**:
- `src/api/main.py` — add `sentry_sdk.init()` before FastAPI app creation
- `.env.example` — ensure `SENTRY_DSN` is documented

**Implementation**:
```python
# In src/api/main.py, before app creation
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    sentry_sdk.init(
        dsn=sentry_dsn,
        integrations=[
            FastApiIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        traces_sample_rate=0.1,
        send_default_pii=False,
    )
```

**Verification**:
- App starts without error when `SENTRY_DSN` is unset (graceful no-op)
- App initializes Sentry when `SENTRY_DSN` is set
- `ruff check` passes

---

### Step 2: Prometheus Metrics

**Why**: Without metrics, p95 latency (8.5 requirement), error rates, and throughput are invisible. Required for any alerting.

**Files**:
- `requirements.txt` — add `prometheus-client`
- `src/api/middleware/metrics.py` — NEW. FastAPI middleware recording:
  - `rag_requests_total` (counter, labels: `endpoint`, `status`)
  - `rag_latency_seconds` (histogram, labels: `endpoint`, buckets: 0.1, 0.5, 1, 5, 30, 60, 120, 180)
  - `rag_ragas_score` (gauge, labels: `metric_name`) — updated per query by evaluator
- `src/api/main.py` — register metrics middleware in app startup
- `src/api/routes/health.py` — expose `GET /metrics` returning Prometheus output
- `config/settings.yaml` — add `metrics:` section under `monitoring:`

**Metrics Middleware Design**:
```python
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

requests_total = Counter(
    "rag_requests_total", "Total requests",
    ["endpoint", "status"],
)
latency_histogram = Histogram(
    "rag_latency_seconds", "Request latency",
    ["endpoint"],
    buckets=(0.1, 0.5, 1, 5, 30, 60, 120, 180),
)
ragas_gauge = Gauge(
    "rag_ragas_score", "RAGAS score by metric",
    ["metric_name"],
)
```

**Verification**:
- `curl http://localhost:8000/metrics` returns valid Prometheus text format
- Metrics appear after query requests
- `ruff check` and `mypy` pass

---

### Step 3: RAGAS CI Gate

**Why**: The CI has a commented-out RAGAS regression job. Without it, deployment can silently degrade answer quality. This is the core validation gate for Phase 8.5.

**Files**:
- `.github/workflows/ci.yml` — uncomment and enable the RAGAS regression job
- `data/ground_truth/golden_set_ci.json` — NEW. Lightweight 5-10 query subset of the 68-pair benchmark for fast CI runs
- `scripts/validate_ragas_regression.py` — NEW. Script that:
  1. Loads golden set
  2. Runs each query through the pipeline
  3. Computes RAGAS scores
  4. Fails if any metric drops below threshold

**CI Job Design**:
```yaml
ragas-regression:
  needs: tests
  runs-on: ubuntu-latest
  # Only run on PRs to main or pushes to main
  if: github.event_name == 'pull_request' || github.ref == 'refs/heads/main'
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
      with:
        python-version: '3.10'
        cache: 'pip'
    - run: pip install -r requirements.txt
    - name: Validate RAGAS regression
      env:
        OPENROUTER_API_KEY: ${{ secrets.OPENROUTER_API_KEY }}
      run: python scripts/validate_ragas_regression.py
```

**RAGAS Thresholds** (from Phase 6 baselines):
| Metric | Phase 6 Score | CI Fail Threshold |
|--------|---------------|-------------------|
| Faithfulness | 0.87 | < 0.80 |
| Answer Relevancy | 0.78 | < 0.70 |
| Context Precision | 0.80 | < 0.75 |
| Context Recall | 0.55 | < 0.45 |
| Answer Completeness | 0.62 | < 0.55 |

**Verification**:
- CI pipeline includes RAGAS regression step
- Step passes against current metrics
- Step fails if thresholds are breached

---

### Step 4: Latency Budget Verification

**Why**: Budgets in `settings.yaml` are defined but untested. Need a script to validate end-to-end latency against thresholds.

**Files**:
- `scripts/profile_full_pipeline.py` — NEW. Runs N queries through the full RAG pipeline, measures and reports:
  - Per-query total latency
  - Per-node latency breakdown
  - p50, p95, p99, max across all queries
  - Pass/fail against budgets

**Budget Thresholds** (from `config/settings.yaml`):
| Component | Budget |
|-----------|--------|
| Retrieval | ≤ 500ms |
| Rerank | ≤ 1000ms |
| Generation (LLM) | ≤ 30000ms |
| Total (p95) | ≤ 180000ms |

**Verification**:
- `python scripts/profile_full_pipeline.py` runs with 3+ test queries
- Outputs latency breakdown table
- Reports pass/fail per budget

---

### Step 5: Load Testing Script

**Why**: Validates system behavior under concurrent load. No external tooling (locust/k6) — uses Python `concurrent.futures`.

**Files**:
- `scripts/load_test.py` — NEW. Sends N concurrent queries, measures:
  - Success rate under load
  - p50/p95 latency under concurrency
  - Error rate
  - Any rate-limiting (429) responses

**Design**:
```python
def run_load_test(
    query: str = "What is the project about?",
    concurrency: int = 5,
    requests_per_worker: int = 2,
) -> dict:
    """Run concurrent queries and report performance."""
```

**Verification**:
- `python scripts/load_test.py` runs without error
- Reports pass/fail for: success rate > 95%, no 429s at low concurrency
- Completes within reasonable time

---

### Step 6: Operational Runbook

**Why**: Production readiness requires documented procedures for common scenarios.

**Files**:
- `docs/ops/RUNBOOK.md` — NEW. Covers:

| Scenario | Procedure |
|----------|-----------|
| Startup | Start Qdrant, run API, verify health |
| Shutdown | Graceful stop sequence |
| Health check interpretation | What each component status means |
| Qdrant recovery | Restart container, verify collection exists |
| BM25 recovery | Load pickle file, check index size |
| LLM fallback | Check Ollama status, verify API key |
| Rollback | Git revert + redeploy |
| Data re-ingestion | Repopulate all 3 storage backends |

**Verification**:
- Document exists with actionable, step-by-step procedures
- Covers all 8 scenarios listed above

---

### Step 7: Streaming UX Playwright Test

**Why**: Validates SSE streaming works correctly in the browser (8.5 streaming UX requirement).

**Files**:
- `frontend/tests/streaming.spec.ts` — NEW. Playwright test that:
  1. Loads the query page
  2. Submits a query
  3. Verifies text chunks appear progressively
  4. Verifies sources panel appears after completion
  5. Verifies no console errors

**Verification**:
- `npx playwright test frontend/tests/streaming.spec.ts` passes
- Test captures any console errors or rendering issues

---

## 4. Files to Modify

| File | Action | Step | Priority |
|------|--------|------|----------|
| `src/api/main.py` | Edit — add Sentry init | 1 | High |
| `.env.example` | Edit — document SENTRY_DSN | 1 | Medium |
| `requirements.txt` | Edit — add `prometheus-client` | 2 | High |
| `src/api/middleware/metrics.py` | **NEW** | 2 | High |
| `src/api/routes/health.py` | Edit — add `/metrics` | 2 | High |
| `config/settings.yaml` | Edit — add monitoring section | 2 | Medium |
| `.github/workflows/ci.yml` | Edit — enable RAGAS regression job | 3 | High |
| `data/ground_truth/golden_set_ci.json` | **NEW** | 3 | High |
| `scripts/validate_ragas_regression.py` | **NEW** | 3 | High |
| `scripts/profile_full_pipeline.py` | **NEW** | 4 | High |
| `scripts/load_test.py` | **NEW** | 5 | Medium |
| `docs/ops/RUNBOOK.md` | **NEW** | 6 | Medium |
| `frontend/tests/streaming.spec.ts` | **NEW** | 7 | Medium |

**Totals**: 5 existing files modified, 8 new files created

---

## 5. Verification Strategy

### Per-Step Verification

| Step | Verify Command | Expected Result |
|------|---------------|----------------|
| 1 | `python -c "import src.api.main"` | App imports without error |
| 2 | `curl localhost:8000/metrics` | Prometheus text output with `rag_requests_total`, `rag_latency_seconds`, `rag_ragas_score` |
| 3 | `python scripts/validate_ragas_regression.py` | Passes (no regression) |
| 4 | `python scripts/profile_full_pipeline.py` | Reports latency breakdown + pass/fail |
| 5 | `python scripts/load_test.py` | Reports success rate, latency under concurrency |
| 6 | Read `docs/ops/RUNBOOK.md` | All 8 scenarios documented |
| 7 | `npx playwright test frontend/tests/streaming.spec.ts` | Passes |

### Full CI Pipeline Verification

```bash
# Verify CI passes end-to-end
ruff check .
ruff format --check .
mypy src/
pytest tests/unit/ -q
pytest tests/integration/ -q
python scripts/validate_ragas_regression.py
```

### Final Acceptance Criteria

- [ ] Sentry initializes (graceful no-op if DSN absent)
- [ ] `/metrics` endpoint exposes Prometheus-formatted metrics
- [ ] CI blocks deployment on RAGAS regression
- [ ] Full pipeline latency p95 ≤ 180s
- [ ] Load test with N=5 concurrent passes (success rate > 95%)
- [ ] Runbook documents all 8 operational scenarios
- [ ] Streaming UX Playwright test passes
- [ ] No regression in existing functionality
- [ ] `ruff check .` passes
- [ ] `mypy src/` passes

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Sentry DSN missing in production | Medium | Low | Graceful no-op, log warning |
| Metrics endpoint overload | Low | Low | Prometheus client is lightweight, single-threaded |
| RAGAS CI gate too slow | Medium | Medium | Use 5-query golden set, 3-minute limit |
| Latency exceeds 180s budget | Medium | High | Document as known constraint (CPU inference) |
| Load test fails due to Ollama latency | Low | Medium | Test with API key mode, not Ollama |
| Playwright test flaky | Low | Low | Add retries, 30s timeouts |

### Rollback Plan

If any step causes regression:
1. **Sentry**: Remove `sentry_sdk` import — fully additive, no runtime impact
2. **Metrics**: Remove middleware registration — fully additive
3. **RAGAS CI gate**: Comment out the job in CI — no code change needed
4. **Scripts**: New files only, no impact on existing code
5. **Runbook**: Documentation only, no code impact
