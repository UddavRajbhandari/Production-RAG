# AGENTS.md — Production RAG Pipeline

## Behavioral guidelines

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.


## Engineering Protocol — Mandatory Development Workflow

This section defines **non-negotiable development rules**. Any generated code that violates these rules is considered invalid.


### 1. Test-Driven Development (TDD) — REQUIRED

For every feature, module, or function:

**Step 1 — Write Tests First**
- Create tests in `tests/unit/` before implementation
- Add integration tests in `tests/integration/` when cross-module behavior exists
- Cover:
  - Expected behavior
  - Edge cases
  - Failure cases

**Step 2 — Ensure Tests Fail (Red Phase)**

**Step 3 — Implement Minimal Code (Green Phase)**

**Step 4 — Refactor (Without Breaking Tests)**

🚨 **Critical Rule:**
- Tests MUST be generated before implementation in the same response
- No code is valid without tests


### 2. Code Quality Compliance — MUST PASS

#### Ruff (Lint + Format)
- `ruff check .`
- `ruff format --check .`

#### Mypy (Strict Typing)
- All functions must include full type hints
- No untyped functions allowed
- Avoid `Any` unless absolutely necessary


### 3. Pre-Commit Compliance

All code must pass pre-commit hooks:

- No trailing whitespace
- No debug statements (`print`, `pdb`, `breakpoint`)
- No large files (>1MB)
- No secrets
- Valid YAML/TOML
- Ground truth validation must pass


### 4. CI/CD Alignment — NON-NEGOTIABLE

Generated code must pass the full pipeline:

#### Quality
- Ruff lint
- Ruff format check
- Mypy

#### Tests
- Unit tests
- Integration tests
- Ground truth schema validation

#### Evaluation (Phase 6+ ONLY)
- RAGAS evaluation is NOT required before Phase 6
- During Phase 6+, RAGAS thresholds must not regress

#### Build (Phase 8 ONLY)
- Docker build is NOT required before Phase 8
- During Phase 8+, Docker build must succeed

🚨 Any code that would fail CI is invalid.



### 5. Testing Standards

- Naming:
  - `test_<function_name>`
- Structure:
  - Arrange → Act → Assert
- Coverage:
  - Happy path
  - Edge cases
  - Failure cases

Markers:
- `@pytest.mark.unit`
- `@pytest.mark.integration`


### 6. Implementation Constraints

- Follow project structure strictly (`src/ingestion`, `retrieval`, etc.)
- Do NOT introduce:
  - New frameworks
  - Paid APIs
  - Unapproved dependencies


### 7. Definition of Done (DoD)

A feature is complete ONLY if:

- [ ] Tests exist (unit + integration if needed)
- [ ] Tests pass
- [ ] Ruff passes
- [ ] Mypy passes
- [ ] Pre-commit passes
- [ ] CI pipeline would pass
- [ ] No regression in evaluation metrics





## How to Work With Me

- Ask which phase I'm on before giving implementation advice
- Prefer specific, actionable guidance over general explanations
- If something here conflicts with what I say in conversation, ask me to clarify — don't assume silently
- Be skeptical and validate — I may be wrong about implementation details
- When I share code or output, check it against the architecture described here


## Required Setup

1. **Environment file**: Copy `.env.example` to `.env` and fill in values
2. **Services**: Qdrant Cloud (already configured via `QDRANT_URL` + `QDRANT_API_KEY`). No local Docker needed.
3. **Pre-commit**: `pre-commit install`



## Architecture

Five primary subsystems, plus an operational guardrails layer:

```
DATA SOURCES
    └── DATA PROCESSING
            ├── Re-Structuring (Document Parser + Structure Analyzer)
            ├── Structure-Aware Chunking (Table Preserver, Heading Detector, Boundary Detector)
            └── Metadata Creation (Summary Generator, Keyword Extractor, Question Generator)
                    └── DATABASE LAYER
                            ├── Vector Store (Qdrant — dense)
                            ├── Sparse Index (BM25 — rank_bm25)
                            └── Relational DB (Neon/Postgres + pgvector)

GUARDRAILS LAYER (applied at API + Pipeline entry)
    ├── PII Masking (emails, SSNs, CCs, phones, IPs — input + output)
    ├── Semantic Caching (embedding similarity ≥ 0.92, LRU 256, TTL 1h)
    ├── Token Budgeting (tiktoken cl100k_base, max 2000 query / 30000 total)
    └── Prompt Injection Hardening (SECURITY INSTRUCTION in all LLM prompts)

USER QUERY
    └── REASONING ENGINE (LangGraph)
            ├── Planner
            ├── Tool Execution
            └── Conditional Router
                    └── MULTI-AGENT SYSTEM (Sequential)
                            ├── Agent 1: Retrieval Agent
                            ├── Agent 2: Summarization Agent
                            └── Agent 3: Calculation Agent
                                    └── HUMAN VALIDATION
                                            ├── Gatekeeper (query-response alignment)
                                            ├── Auditor (grounding check — hardened prompt)
                                            └── Strategist (contextual coherence + citation enforcement)
                                                    └── EVALUATION LAYER
                                                            ├── RAGAS (Precision & Recall)
                                                            └── Latency & Cost tracking

STRESS TESTING (adversarial — runs against Reasoning Engine)
    ├── Prompt Injection
    ├── Information Evasion
    └── Bias Probing
```

---

## RAGAS Targets

| Metric | Target | Phase 6 Results (Structure-Aware) |
|---|---|---|
| Faithfulness | > 0.80 | **0.87** ✅ |
| Answer Relevancy | > 0.55 | 0.41 ⚠️ |
| Context Precision | > 0.61 | **0.80** ✅ |
| Context Recall | > 0.75 | 0.55 ⚠️ |
| Answer Completeness | > 0.80 | 0.62 ⚠️ |
| End-to-end latency (p95) | ≤ 180s (3m) | TBD |

> ⚠️ **Hardware Constraint**: The original 280ms target assumed cloud GPU inference. Local CPU inference with Llama-3 8B requires a 3-minute budget for the full 8-node reasoning chain.

> **Phase 6 Key Finding**: Structure-Aware outperforms Naive (3/5 metrics passed vs 0/5). Focus areas for Phase 7: Context Recall and Answer Completeness.

---




## Implementation Phases

| Phase | Description | Key Milestone | Status |
|---|---|---|---|
| 1 | Data Ingestion & Processing | 2,717 token-accurate chunks ingested | ✅ Verified |
| 2 | Storage Layer | Triple-backend synchronization verified | ✅ Verified |
| 3 | Hybrid Retrieval & Reranking | Retrieval ≤ 500ms, Rerank (ONNX) ≤ 600ms | ✅ Verified |
| 4 | Reasoning Engine (LangGraph) | 8-node topology with conditional routing | ✅ Verified |
| 5 | Human Validation Nodes | Gatekeeper/Auditor/Strategist testing | ✅ Verified |
| 6 | RAGAS Evaluation | 68-pair benchmark (Naive vs Structure-Aware) | ✅ Complete |
| 7 | Red Teaming & Stress Testing | Prompt Injection / Information Evasion / Bias Probing (30 tests) | ✅ Verified |
| 8 | Deployment & Monitoring | Streaming UX + Live monitoring | ✅ Complete |

---


## Project Resources

| File | Purpose |
|---|---|
| `docs/Project_02_RAG_Pipeline_v1.1.docx` | Full project plan with all phase details |
| `AGENTS.md` | This file — operational context for the AI agent |
| `CLAUDE.md` | Legacy operational context (older version of AGENTS.md) |
| `docs/img/Project 02 system diagram.png` | 5-subsystem architecture layout |
| `docs/ground_truth_source_analysis.md` | Mapping of QA pairs to source documents |
| `docs/phase1to3/Phase_1_to_3_Technical_Report_v1.1.md` | Post-remediation status report |
| `docs/phase4 and 5/Phase_4-5_Reasoning_Engine_Report.md` | LangGraph architecture and performance |
| `docs/phase 6/Phase_6_Comparison_Report.md` | Naive vs Structure-Aware RAG evaluation |
| `docs/phase 7/Phase_7_Stress_Testing_Report.md` | Red Teaming & Stress Testing documentation |
| `docs/phase 8/Phase_8.4_and_8.5_Implementation_Plan.md` | Phase 8.4+8.5 production readiness & validation plan |
| `docs/phase 8/Phase_8.6_Operational_Guardrails.md` | PII Masking, Semantic Cache, Token Budget, Prompt Hardening |
| `docs/ops/RUNBOOK.md` | Operational runbook (startup, recovery, rollback, monitoring) |
| `docs/LATENCY_LOG.md` | Verified wall-clock timings for all components |
| `data/ground_truth/ground_truth.json` | 68-pair "Gold Set" evaluation data |
| `data/processed/chunks/ingested_nodes_*.pkl` | Chunked nodes (naive & structure-aware)


## Key Developer Commands

```bash
# Test a single query end-to-end
python scripts/test_single_query.py

# Profile retrieval latency
python scripts/profile_retrieval.py

# Full pipeline latency profiling
python scripts/profile_full_pipeline.py

# Concurrent load test
python scripts/load_test.py --concurrency 2 --requests 3

# Capture LangGraph trace
python scripts/capture_trace.py

# Run adversarial stress tests (simulation mode)
python src/stress_testing/runner.py --verbose

# Run live stress tests (requires LLM service)
python src/stress_testing/runner.py --live --verbose

# Run specific category stress tests
python src/stress_testing/runner.py --category prompt_injection --verbose

# Run guardrail unit tests
python -m pytest tests/unit/guardrails/ -v
```

## Important Conventions

- **Chunk IDs**: SHA256 hashes with prefix (`naive_` for NaiveChunker, `sa_` for StructureAwareChunker)
- **Ground truth**: `data/ground_truth/ground_truth.json` — validated on pre-commit
- **LLM fallback**: If API providers (OpenRouter/Groq) fail, scripts fall back to Ollama (see `src/reasoning/utils/`) or raise

## Remaining Work (Post-Phase 8)

| Task | Status | Notes |
|------|--------|-------|
| **Deploy backend to Render** | ❌ Not started | `.github/workflows/deploy.yml` exists but no Render account/service configured yet. Needs env secrets set in GitHub Actions. |
| **Deploy frontend to Cloudflare Pages** | ❌ Not started | `.github/workflows/frontend-deploy.yml` exists. Cloudflare account needed — discuss whether to proceed with this or serve frontend from Render instead. |
| **GitHub Actions secrets** | ❌ Not set | Need: `OPENROUTER_API_KEY`, `RENDER_STAGING_DEPLOY_HOOK`, `RENDER_PRODUCTION_DEPLOY_HOOK`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` |
| **Production `.env`** | ❌ Not created | Must be provisioned with live keys for Qdrant Cloud, OpenRouter, Neon/Postgres, Sentry DSN |
| **Qdrant payload indexes** | ✅ Done | `date`, `department`, `source_file` keyword indexes created on Qdrant Cloud |
| **RAGAS CI regression** | ⏳ Blocked | Needs `OPENROUTER_API_KEY` secret set in GitHub repo before CI can run this job |
| **Guardrails (PII, Cache, Budget, Hardening)** | ✅ Done | `src/api/guardrails/` — PII Mask, Semantic Cache, Token Budget, Prompt Injection Hardening |
| **Citation enforcement** | ✅ Done | Strategist now fails on missing citations, API returns `source_files` list |

## External References

- Full architecture: see `AGENTS.md`
- Phase reports: `docs/phase*/*.md`

## graphify

This project has a knowledge graph at graphify-out/ with god nodes, community structure, and cross-file relationships.

When the user types `/graphify`, invoke the `skill` tool with `skill: "graphify"` before doing anything else.

Rules:
- For codebase questions, first run `graphify query "<question>"` when graphify-out/graph.json exists. Use `graphify path "<A>" "<B>"` for relationships and `graphify explain "<concept>"` for focused concepts. These return a scoped subgraph, usually much smaller than GRAPH_REPORT.md or raw grep output.
- Dirty graphify-out/ files are expected after hooks or incremental updates; dirty graph files are not a reason to skip graphify. Only skip graphify if the task is about stale or incorrect graph output, or the user explicitly says not to use it.
- If graphify-out/wiki/index.md exists, use it for broad navigation instead of raw source browsing.
- Read graphify-out/GRAPH_REPORT.md only for broad architecture review or when query/path/explain do not surface enough context.
- After modifying code, run `graphify update .` to keep the graph current (AST-only, no API cost).
