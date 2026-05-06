# Production RAG Pipeline — Project Structure
**Project 02 | Version 1.1**
*Revised May 2026 — Aligned with v1.1 Technical Review*

---

## Revision Notes

This structure supersedes the original `Project_Structure.md`. Changes were made
to align with the architectural decisions resolved in v1.1 and the findings of
the pre-Phase 1 corpus audit. Key additions: `src/storage/`, `src/validation/`,
`data/ground_truth/`, `data/processed/filtered/`, `data/processed/chunks/`,
and `tests/red_team/`.

---

## /src

### ingestion/
Document parsing, structure analysis, chunking, and metadata extraction.
Corresponds to Phase 1 of the implementation plan.

```
ingestion/
  parser.py           # Type-specific handlers: PDF (PyMuPDF), DOCX (python-docx),
                      # XLSX (openpyxl), Images (unstructured + OCR).
                      # Do NOT use a single generic parser.
  structure_analyzer.py  # Classifies every block: heading, paragraph, table,
                         # code_block, list_item. Outputs a tagged document tree.
  chunker.py          # Structure-aware chunking: 256–512 tokens, 50-token overlap.
                      # Hard rules: never split table rows or code blocks.
                      # Includes minimum character threshold filter (< 100 chars)
                      # per corpus audit finding (zero-text / low-density pages).
  metadata_pipeline.py   # Per-chunk metadata: source_file, section_heading,
                         # chunk_index, date, department, version, summary,
                         # keywords, hypothetical_questions (HyDE via LLM).
                         # Temporal metadata: regex-based year extraction from
                         # filename takes priority over internal PDF metadata
                         # per corpus audit finding.
```

> **Audit note:** The corpus contains documents ranging from 7 to 408 pages with
> high table density in financial files (up to 3 tables/page). Use `unstructured`
> for table-to-Markdown conversion and batch processing for large files to
> prevent memory spikes during embedding generation.

---

### storage/
Infrastructure initialization for all three storage backends.
Corresponds to Phase 2 of the implementation plan.

```
storage/
  qdrant_client.py    # Qdrant (local Docker) setup for dense vector storage.
                      # Stores chunk text + full metadata payload.
  bm25_index.py       # rank_bm25 in-memory index (Decision 1: confirmed).
                      # Feasible for corpus under ~80K chunks on 16 GB RAM.
                      # Migration trigger: >80K chunks OR Context Recall < 0.70
                      # → revisit Qdrant sparse vectors (SPLADE).
  neon_db.py          # Neon/Postgres + pgvector schema.
                      # Required fields: version, department, date.
                      # Supports Neon branching for isolated testing of new
                      # embedding models or chunking strategies.
```

---

### retrieval/
Hybrid retrieval pipeline and cross-encoder reranking.
Corresponds to Phase 3 of the implementation plan.

```
retrieval/
  hybrid_search.py    # Qdrant dense retrieval (top 20) + BM25 sparse (top 20).
  rrf_fusion.py       # Reciprocal Rank Fusion (k=60). Preferred over weighted
                      # averaging — requires no tuning.
  reranker.py         # cross-encoder/ms-marco-MiniLM-L-6-v2 via sentence-
                      # transformers (replaces Cohere Rerank — zero cost).
                      # Alternative: cross-encoder/ms-marco-electra-base for
                      # higher accuracy at additional latency cost.
                      # Target: ≤ 120ms for full retrieval + reranking.
```

> **Hardware note:** Local cross-encoder inference is slower than a paid API call.
> Profile on target hardware early. Reduce top-N candidate count if the 120ms
> budget is exceeded before adjusting anything else.

---

### reasoning/
LangGraph stateful graph: planner, conditional router, and agent nodes.
Corresponds to Phase 4 of the implementation plan.

```
reasoning/
  state.py            # RAGState TypedDict: query, sub_tasks, retrieved_chunks,
                      # agent_outputs, final_answer, validation_passed.
  planner.py          # Decomposes multi-step queries into executable sub-tasks.
  router.py           # Classifies sub-task type and routes to correct agent.
  agents/
    retrieval_agent.py      # Retrieval Agent node.
    summarization_agent.py  # Summarization Agent node.
    calculation_agent.py    # Calculation Agent node.
  graph.py            # Full LangGraph StateGraph wiring: entry point, sequential
                      # edges, conditional edges (Decision 2: sequential execution
                      # confirmed). Parallelism reserved for Phase 4 optimization
                      # only if profiling reveals measurable bottlenecks.
```

---

### validation/
LLM-as-Judge validation nodes. Corresponds to Phase 5 of the implementation plan.

```
validation/
  gatekeeper.py       # Verifies response addresses original query. PASS/FAIL + reason.
  auditor.py          # Grounding check: every claim must be traceable to a retrieved
                      # chunk. Uses hardened prompt (Decision 3: same model confirmed).
                      # Prompt must include: "For each claim, identify the exact chunk
                      # that supports it. If a claim cannot be traced to a specific
                      # chunk, mark it UNGROUNDED."
  strategist.py       # Contextual coherence evaluation. PASS/FAIL + reason.
  schemas.py          # Shared output schema: { verdict: PASS/FAIL, reason: string }.
                      # All nodes must return this structure. Decisions are logged
                      # and auditable.
```

> **Validation LLM:** Same model as reasoning engine (Decision 3). Optional upgrade:
> load a second quantized model (e.g., Mistral-7B-Instruct Q4_K_M via llama.cpp)
> for the Auditor role only if 16 GB RAM permits. Two 4-bit quantized 7B models
> can co-exist within 16 GB.

---

### evaluation/
RAGAS integration, latency and cost tracking, and ground truth validation.
Corresponds to Phase 6 of the implementation plan.

```
evaluation/
  ragas_runner.py          # Runs RAGAS across all 4 iterations. Records
                           # Faithfulness, Answer Relevancy, Context Precision,
                           # Context Recall. Outputs delta scores per iteration.
  latency_tracker.py       # Per-query logging: retrieval_latency_ms,
                           # rerank_latency_ms, generation_latency_ms,
                           # total_latency_ms, validation_passed, cost_usd.
                           # Alert threshold: total_latency_ms > 280ms.
  validate_ground_truth.py # Ground truth schema validation script.
                           # See ground_truth_plan.md for full specification.
```

---

### utils/
Shared infrastructure. No business logic.

```
utils/
  logging.py          # Structured logging across all subsystems.
  env.py              # Environment variable management.
  helpers.py          # Shared helper functions.
```

---

## /data

```
data/
  raw/                # Original corpus: 27 PDF files + 6 DOCX files.
                      # Read-only. Never modify files in this directory.

  processed/
    filtered/         # Post junk-node removal. Pages below 100-character
                      # threshold are excluded here per corpus audit finding.
    chunks/           # Validated structure-aware chunks from Phase 1.
                      # These are the chunks used for chunk ID assignment
                      # in the ground truth dataset (Track B).

  ground_truth/       # Ground truth QA dataset. Construction begins in Phase 1
                      # (Track A) and completes after chunking is validated
                      # (Track B). See ground_truth_plan.md.
    ground_truth.json # Primary dataset. Schema: question_id, question,
                      # ground_truth_answer, ground_truth_chunk_ids,
                      # source_document, domain_tag.
    ground_truth.csv  # Optional CSV mirror for spreadsheet-based annotation.

  metadata/           # Temporal metadata outputs and other extraction artifacts.
```

---

## /config

```
config/
  settings.yaml       # Model names, chunk size (256–512 tokens), overlap (50 tokens),
                      # RRF k-value (60), latency thresholds (p95: 280ms,
                      # retrieval: 120ms), RAGAS alert threshold (CP < 0.75),
                      # top-N retrieval counts, API endpoint configurations.
```

---

## /tests

```
tests/
  unit/               # Per-module unit tests for each subsystem.
  integration/        # Round-trip and cross-subsystem tests.
                      # Includes: single-document ingest → Qdrant + Postgres
                      # round-trip (Phase 2 milestone), 50-query retrieval
                      # validation (Phase 3 milestone).
  red_team/           # Adversarial test suites (Phase 7).
    prompt_injection/   # Attempts to override system prompt and core instructions.
    info_evasion/       # Attempts to leak data across access levels.
    bias_probing/       # Demographic, political, religious query framing.
                        # Every test case must be logged — undocumented tests
                        # do not count toward the Phase 7 milestone.
```

---

## /docs

```
docs/
  audit_pre_phase.md  # Pre-Phase 1 corpus audit (complete). Covers 25/33 documents.
                      # Key findings: zero-text pages, high table density in
                      # financial files, document scale 7–408 pages, filename-
                      # based temporal metadata.
  ground_truth_plan.md  # Ground truth construction workflow (Track A + Track B).
  PROJECT_STATUS.md   # Project status, decisions log, and active blockers.
                      # Replaces GEMINI.md — audit GEMINI.md for Google-specific
                      # tooling assumptions before renaming.
```

---

## Root Files

```
main.py               # CLI or API entry point to run the pipeline.
.env                  # Environment variables (keys, paths). Never commit.
requirements.txt      # Python dependency manifest.
pyproject.toml        # Build system configuration (alternative to requirements.txt).
GEMINI.md             # Gemini CLI configuration. Do not rename or modify structure.
```

---

## Hardware Reference

| Environment | Specification | Role |
|---|---|---|
| Local machine | No GPU, 16 GB RAM | Qdrant, BM25, cross-encoder inference, quantized LLM |
| Cloud GPU (free) | Kaggle T4/P100 or Colab T4 | Embedding generation only — one-time ingestion job |
| Workflow | Embed on cloud → serialize → load into local Qdrant | Eliminates GPU dependency at query time |

> **Before Phase 2:** Run `htop` or `free -h` on a clean boot to establish actual
> RAM headroom. Qdrant + cross-encoder + Python runtime can approach 6–8 GB combined.

---

## Pre-Phase 1 Gate Checklist

All items below must be complete before Phase 1 implementation code begins.

| # | Item | Status |
|---|---|---|
| 1 | YouTube reference video watched and plan updated | ✅ Complete |
| 2 | GEMINI.md audited and renamed to PROJECT_STATUS.md | ✅ Complete |
| 3 | BM25 path decided (rank_bm25 — Decision 1) | ✅ Closed |
| 4 | Agent execution model decided (Sequential — Decision 2) | ✅ Closed |
| 5 | Validation LLM decided (Same model + hardened prompts — Decision 3) | ✅ Closed |
| 6 | Project structure revised and aligned with v1.1 | ✅ Complete |
| 7 | Ground truth schema defined, file initialized (Track A, Step 1) | ☐ |
| 8 | Ground truth questions and answers written (Track A, Step 2) | ☐ |
| 9 | Validation script written and passing on empty dataset (Track A, Step 3) | ☐ |

Items 7–9 are the final gate. Phase 1 implementation begins once they are checked.

---

*Document prepared May 2026 | Version 1.1 | Project 02*
*Confidential — Internal Use Only*
*
