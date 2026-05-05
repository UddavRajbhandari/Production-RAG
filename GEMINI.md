# GEMINI.md — Project 02: Production-Grade RAG Pipeline v1.1
> Read this file entirely before responding to any query in this project.

---

## Who I Am

I am a developer working on a production-grade RAG pipeline as part of my personal project curriculum. I have intermediate Python knowledge and am familiar with basic RAG concepts. I am **not** a beginner — skip foundational explanations unless I ask.

---

## Current Status

**Planning and Pre-Phase 1 complete. Phase 1 implementation is now active.**

All pre-Phase 1 actions, including the corpus audit and initial ground truth generation (25 pairs), are finished. We are moving into the Data Ingestion & Processing phase.

---

## What This Project Is

**Project 02** transitions a RAG system from a notebook prototype into a production-grade, verifiable engineering artifact. The core problems being solved:

- Poor document ingestion — tables collapsing, mid-sentence chunking
- No temporal disambiguation — 2019 and 2024 docs treated identically
- No quantitative evaluation — only subjective feedback

This project solves all three through structure-aware ingestion, hybrid retrieval, stateful multi-agent reasoning, and RAGAS-based evaluation.

---

## Architecture

Five primary subsystems:

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
                                            └── Strategist (contextual coherence)
                                                    └── EVALUATION LAYER
                                                            ├── RAGAS (Precision & Recall)
                                                            └── Latency & Cost tracking

STRESS TESTING (adversarial — runs against Reasoning Engine)
    ├── Prompt Injection
    ├── Information Evasion
    └── Bias Probing
```

---

## Technology Stack

All tooling is open-source and zero-cost. No paid APIs.

| Component | Technology | Status |
|---|---|---|
| Document Parsing | PyMuPDF, python-docx, openpyxl, unstructured | Confirmed |
| Orchestration / Ingestion | LlamaIndex | Confirmed |
| Semantic Chunking | LlamaIndex SentenceWindowNodeParser (256–512 tokens, 50-token overlap) | Confirmed |
| Embedding Generation | all-MiniLM-L6-v2 or nomic-embed-text (Hugging Face) | Planned — cloud GPU only |
| Dense Vector Store | Qdrant (local Docker) | Confirmed |
| Sparse / Keyword Search | rank_bm25 | Confirmed — Decision 1 |
| Relational Storage | Neon/Postgres + pgvector | Confirmed |
| Result Fusion | Reciprocal Rank Fusion (RRF, k=60) | Confirmed |
| Cross-Encoder Reranking | cross-encoder/ms-marco-MiniLM-L-6-v2 (sentence-transformers) | Replaces Cohere Rerank |
| Agent / Graph Framework | LangGraph StateGraph | Confirmed |
| Local LLM Inference | llama.cpp or Ollama (quantized) | Confirmed |
| Evaluation Framework | RAGAS | Confirmed |
| Containerization | Docker / Kubernetes | Phase 8 |
| Cloud GPU (ingestion only) | Kaggle (preferred) or Google Colab | Free tier |

---

## Hardware

| Environment | Spec | Role |
|---|---|---|
| Local machine | 16 GB RAM, no GPU | Qdrant, BM25, cross-encoder inference, quantized LLM |
| Kaggle / Colab (free) | T4 or P100 GPU | Embedding generation only — one-time ingestion job |

**Before Phase 2:** run `free -h` on a clean boot. Qdrant + cross-encoder + Python runtime can consume 6–8 GB combined.

---

## Embedding Workflow (Planned — Not Yet Implemented)

This workflow will be executed at the start of Phase 1–2. Documented here for planning purposes only.

```
Step 1 — Upload corpus to Kaggle dataset or Google Drive
Step 2 — Run embedding pipeline on cloud GPU (Kaggle preferred)
           python embed_corpus.py --model all-MiniLM-L6-v2 --output vectors.npy
Step 3 — Persist vectors before session ends
           cp vectors.npy /kaggle/working/vectors.npy
Step 4 — Download to local machine
Step 5 — Ingest into local Qdrant
           python ingest_qdrant.py --vectors vectors.npy --collection rag_pipeline
```

> ⚠️ Kaggle and Colab sessions are ephemeral. Always persist embeddings before the session closes. Lost vectors require a full re-run.

---

## Architectural Decisions (All Resolved)

| Decision | Resolution | Revisit Trigger |
|---|---|---|
| BM25 path | `rank_bm25` selected | Corpus > 80K chunks or Context Recall < 0.70 |
| Agent execution | Sequential with conditional routing | Only parallelize after profiling shows independent bottlenecks |
| Validation LLM | Same model; Auditor uses chunk-restricted prompt | If Faithfulness stagnates below 0.75 after prompt hardening |
| Ground truth dataset | Build during Phase 1 — not Phase 6 | N/A |

---

## RAGAS Targets

| Metric | Target |
|---|---|
| Faithfulness | > 0.80 |
| Answer Relevancy | > 0.75 |
| Context Precision | 0.61 → 0.84 |
| Context Recall | > 0.75 |
| End-to-end latency (p95) | ≤ 280ms |

> ⚠️ The 38% Context Precision improvement is a target from source material — not a verified result. Establish your own baseline in Phase 6 Iteration 1 before setting any stakeholder expectations.

---

## RAGAS Evaluation Protocol

Run in iteration order. Do not skip ahead.

| Iteration | Pipeline Configuration | Action |
|---|---|---|
| 1 | Naive chunking | Record all 4 baseline scores |
| 2 | Structure-aware chunking | Document delta vs. Iteration 1 |
| 3 | + Hybrid retrieval (RRF) | Document delta |
| 4 | + Cross-encoder reranking | Document delta |

---

## Implementation Phases

| Phase | Description | Key Milestone |
|---|---|---|
| 1 | Data Ingestion & Processing | 100-doc corpus ingested, metadata complete |
| 2 | Storage Layer | Round-trip storage test passing |
| 3 | Hybrid Retrieval & Reranking | Latency ≤ 120ms profiled |
| 4 | Reasoning Engine (LangGraph) | Multi-step queries routing correctly |
| 5 | Human Validation Nodes | All 3 nodes passing/failing correctly |
| 6 | RAGAS Evaluation | 4-iteration benchmark documented |
| 7 | Red Teaming & Stress Testing | All attack categories logged as FAIL |
| 8 | Deployment & Monitoring | Live, p95 ≤ 280ms, monitoring active |

---

## Phase 1 Active Tasks

| # | Task | Priority |
|---|---|---|
| 1 | Create `config/settings.yaml` for pipeline parameters | CRITICAL |
| 2 | Implement `src/ingestion/parser.py` (Structure-Aware) | CRITICAL |
| 3 | Populate remaining 35 QA pairs (Track A) | HIGH |

---

## Known Caveats


- Google Research hallucination citation from source material has not been independently verified — do not cite externally
- The "80% of databases provisioned by AI agents" Neon claim has not been sourced — omit from client-facing materials

---

## Project Resources

| File | Purpose |
|---|---|
| `docs/Project_02_RAG_Pipeline_v1.1.docx` | Full project plan with all phase details |
| `gemini.md` | This file — operational context for Gemini CLI |
| `docs/img/ByteMonk Project 02 system diagram.png` | 5-subsystem architecture layout |
| `docs/ground_truth_source_analysis.md` | Mapping of QA pairs to source documents |

---

## How to Work With Me

- Ask which phase I'm on before giving implementation advice
- Prefer specific, actionable guidance over general explanations
- If something here conflicts with what I say in conversation, ask me to clarify — don't assume silently
- Be skeptical and validate — I may be wrong about implementation details
- When I share code or output, check it against the architecture described here

---

*Last updated: May 2026 — ByteMonk Project 02 | Pre-Phase 1 complete — Phase 1 implementation active*
