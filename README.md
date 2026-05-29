---
title: Production RAG Pipeline
emoji: 🧠
colorFrom: indigo
colorTo: purple
sdk: docker
pinned: false
---

# Production RAG Pipeline with Evaluation Layer

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-3776AB?logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/framework-FastAPI-009688?logo=fastapi" alt="FastAPI">
  <img src="https://img.shields.io/badge/orchestrator-LangGraph-7C3AED?logo=langchain" alt="LangGraph">
  <img src="https://img.shields.io/badge/vectors-Qdrant-7600D1?logo=qdrant" alt="Qdrant">
  <img src="https://img.shields.io/badge/embeddings-sentence--transformers-FF6F00?logo=huggingface" alt="Sentence Transformers">
  <img src="https://img.shields.io/badge/reranker-ONNX-005CED?logo=onnx" alt="ONNX">
  <img src="https://img.shields.io/badge/database-Neon%2FPostgres-316192?logo=postgresql" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/frontend-Next.js%2014-000000?logo=next.js" alt="Next.js">
  <img src="https://img.shields.io/badge/ui-React%2018-61DAFB?logo=react" alt="React">
  <img src="https://img.shields.io/badge/styling-Tailwind%20CSS%203-06B6D4?logo=tailwindcss" alt="Tailwind CSS">
  <img src="https://img.shields.io/badge/deploy-Docker-2496ED?logo=docker" alt="Docker">
  <img src="https://img.shields.io/badge/monitoring-Prometheus-E6522C?logo=prometheus" alt="Prometheus">
  <img src="https://img.shields.io/badge/CI-CD-208A00?logo=githubactions" alt="CI/CD">
  <img src="https://img.shields.io/badge/license-MIT-blue" alt="License">
</p>

A production-grade Retrieval-Augmented Generation pipeline featuring a LangGraph-based multi-agent reasoning engine, operational guardrails, hybrid retrieval, and a modern web UI. Deployed on Hugging Face Spaces via Docker.

---

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [System Design & Components](#system-design--components)
  - [Ingestion Pipeline](#1-ingestion-pipeline-srcingestion)
  - [Storage Layer](#2-storage-layer-srcstorage)
  - [Retrieval & Reranking](#3-retrieval--reranking-srcretrieval)
  - [Reasoning Engine](#4-reasoning-engine-srcreasoning)
  - [Evaluation](#5-evaluation-srcevaluation)
  - [API Server](#6-api-server-srcapi)
  - [Guardrails](#7-guardrails-srcapiguardrails)
  - [Stress Testing](#8-stress-testing-srcstress_testing)
- [Frontend](#frontend)
- [Project Structure](#project-structure)
- [Quick Start Guide](#quick-start-guide)
  - [Prerequisites](#prerequisites)
  - [Backend Setup](#backend-setup)
  - [Frontend Setup](#frontend-setup)
  - [Docker Deployment](#docker-deployment)
- [Usage Guide](#usage-guide)
  - [Making a Query](#making-a-query)
  - [Streaming Responses](#streaming-responses)
  - [Uploading Documents](#uploading-documents)
  - [Providing Your Own API Key](#providing-your-own-api-key)
  - [Monitoring System Health](#monitoring-system-health)
- [Configuration](#configuration)
- [Testing](#testing)
- [Deployment](#deployment)

---

## Architecture Overview

The system follows a five-subsystem architecture: **Data Processing**, **Storage Layer**, **Reasoning Engine**, **Human Validation**, and **Evaluation**, all wrapped by an operational **Guardrails Layer** applied at the API and pipeline entry points.

![System Architecture](docs/img/Project%2002%20system%20diagram%20.png)

**Data Flow**:

```
Raw Documents → Structure-Aware Chunking → Triple Storage (Qdrant + BM25 + Postgres)
                                                          ↓
                                             Hybrid Retrieval + ONNX Reranking
                                                          ↓
                                           LangGraph Multi-Agent Reasoning
                                                          ↓
                                              Human Validation (Gatekeeper → Auditor → Strategist)
                                                          ↓
                                                   RAGAS Evaluation
```

Each subsystem is independently testable, deployable, and observable via Prometheus metrics and structured JSON logging.

---

## System Design & Components

### 1. Ingestion Pipeline (`src/ingestion/`)

Converts raw documents into structured, searchable chunks with rich metadata.

| Component | File | Role |
|---|---|---|
| **Document Parser** | `parser.py` | Extracts text from PDF, DOCX, XLSX, and HTML sources using PyMuPDF, python-docx, openpyxl, and Unstructured |
| **Structure Analyzer** | `structure_analyzer.py` | Identifies headings, tables, document boundaries, and section hierarchies |
| **Chunker** | `chunker.py` | Token-accurate chunking using tiktoken (cl100k_base), configurable overlap and window size. Supports `naive` and `structure_aware` modes |
| **Metadata Pipeline** | `metadata_pipeline.py` | Generates summaries, extracts keywords, and produces hypothetical questions per chunk |
| **Batch Ingest** | `batch_ingest.py` | Bulk ingestion orchestration with progress tracking |
| **Pipeline** | `pipeline.py` | End-to-end ingestion coordinator connecting parser → analyzer → chunker → storage |

**Chunk IDs** are SHA256 hashes with prefix (`naive_` or `sa_`) to distinguish chunker modes.

### 2. Storage Layer (`src/storage/`)

Triple-backend storage for dense vectors, sparse keywords, and relational metadata. All three backends synchronize under a unified collection name.

| Backend | File | Mode | Purpose |
|---|---|---|---|
| **QdrantStorage** | `qdrant_storage.py` | Cloud (Qdrant Cloud) or local Docker | Dense vector store (384-dim, cosine similarity). Supports payload indexes on `date`, `department`, `source_file` |
| **BM25Storage / QdrantSparseStorage** | `bm25_storage.py`, `qdrant_sparse_storage.py` | Qdrant native sparse (cloud) or pickle file (local) | Keyword/BM25 sparse retrieval |
| **NeonStorage** | `neon_storage.py` | Neon PostgreSQL (cloud) or SQLite (local dev) | Relational chunk metadata (source file, department, year, section heading) |
| **Storage Factory** | `storage_factory.py` | — | Auto-selects storage backend based on environment variables |
| **Populate Storage** | `populate_storage.py` | — | One-time script to populate all backends from processed chunk pickles |

### 3. Retrieval & Reranking (`src/retrieval/`)

Hybrid search combining dense and sparse signals with ONNX-optimized cross-encoder reranking.

| Component | File | Role |
|---|---|---|
| **HybridRetriever** | `hybrid_search.py` | Performs parallel dense (Qdrant) and sparse (BM25) searches, fuses results via Reciprocal Rank Fusion (RRF). Supports optional `source_files` filtering. Returns top-K results with scores |
| **Reranker** | `reranker.py` | ONNX-optimized cross-encoder (`cross-encoder/ms-marco-MiniLM-L-6-v2`). Re-scores pool of N results down to top M. Downloads model (~90MB) on first use |

**Performance targets**: Retrieval ≤ 500ms, Rerank ≤ 600ms (verified on CPU).

### 4. Reasoning Engine (`src/reasoning/`)

An 8-node LangGraph `StateGraph` with conditional routing, per-node latency tracking, and LLM provider fallback chain.

**Graph Topology**:

```
planner → router → retrieval_agent → summarization_agent → gatekeeper → auditor → strategist → END
                     ↓ (conditional)        ↑
                calculation_agent ──────────┘
```

| Node | File | Type | Function |
|---|---|---|---|
| **Planner** | `nodes/planner.py` | LLM | Decomposes user query into 1-3 sub-tasks with tool assignments |
| **Router** | `nodes/router.py` | Deterministic | Routes to `retrieval_agent` or `calculation_agent` based on keyword matching |
| **Retrieval Agent** | `nodes/retrieval_agent.py` | Non-LLM | Executes hybrid search via `HybridRetriever`, attaches context to state |
| **Calculation Agent** | `nodes/calculation_agent.py` | Non-LLM | Rule-based number extraction, operation detection (sum, average, percentage, difference, count), and Python arithmetic |
| **Summarization Agent** | `nodes/summarization_agent.py` | LLM | Synthesizes retrieved context into a natural-language answer |
| **Gatekeeper** | `nodes/gatekeeper.py` | LLM | Validates that the answer addresses the original query (alignment check) |
| **Auditor** | `nodes/auditor.py` | LLM | Detects hallucinations by verifying answer claims against retrieved context (grounding check) |
| **Strategist** | `nodes/strategist.py` | Heuristic | Enforces minimum length, checks for missing citations, populates `source_files` list |

**LLM Provider Chain** (in `utils/llm_client.py`):

```
User-provided key (highest priority)
  → OpenRouter (env: OPENROUTER_API_KEY)
  → OpenAI (env: OPENAI_API_KEY)
  → Groq (env: GROQ_API_KEY)
  → Ollama (local fallback)
```

The `LLMClient` implements a circuit breaker pattern (5 failures → 60s cooldown) and automatic retry with exponential backoff.

**RAGState** (`state.py`) flows through all nodes and tracks:
- Query, sub-tasks, generated answer
- Retrieved context with RRF scores
- Per-node latency (`node_latency_ms`)
- Validation status, error messages, source files
- Optional user-provided `llm_api_key`

### 5. Evaluation (`src/evaluation/`)

| Component | File | Role |
|---|---|---|
| **RAGAS Evaluator** | `ragas_evaluator.py` | Computes Faithfulness, Answer Relevancy, Context Precision, Context Recall, and Answer Completeness per query using LLM-as-judge |
| **E2E Evaluate** | `evaluate_ragas.py` | Batch evaluation runner for ground truth datasets |
| **Ground Truth Validator** | `validate_ground_truth.py` | Schema validation and pre-commit checks for `data/ground_truth/ground_truth.json` (68 QA pairs) |

### 6. API Server (`src/api/`)

FastAPI application with full middleware stack, rate limiting, authentication, and observability.

| Layer | File | Role |
|---|---|---|
| **Main** | `main.py` | App bootstrap, lifespan management, middleware registration, embedding model pre-loading |
| **Routes** | `routes/` | `health.py` (liveness + component health), `query.py` (standard + SSE streaming + retrieve-only), `ingest.py`, `metadata.py` |
| **Middleware** | `middleware/` | `auth.py` (API key verification), `rate_limit.py` (per-key rate limiting via SlowAPI), `logging.py` (structured JSON request logging), `metrics.py` (Prometheus metrics) |
| **Models** | `models/models.py` | Pydantic schemas for all request/response types, Settings model with env var binding |
| **Query Tracker** | `query_tracker.py` | Thread-safe in-flight query tracking with stale detection (5min timeout) and force-clear debug endpoint |

**API Endpoints**:

| Endpoint | Method | Auth | Purpose |
|---|---|---|---|
| `/api/v1/health/live` | GET | No | Lightweight liveness probe |
| `/api/v1/health` | GET | No | Full component health (cached 30s) |
| `/api/v1/query` | POST | Yes | Standard query with sources |
| `/api/v1/query/stream` | POST | Yes | SSE streaming query (50-char chunks + metadata event) |
| `/api/v1/query/retrieve` | POST | Yes | Retrieve-only (no LLM call) |
| `/api/v1/ingest` | POST | Yes | Ingest a document |
| `/api/v1/metadata/documents` | GET | Yes | List ingested documents |
| `/api/v1/metadata/stats` | GET | Yes | Document statistics |
| `/api/v1/metadata/departments` | GET | Yes | List departments |

### 7. Guardrails (`src/api/guardrails/`)

Four operational guardrails applied at API and pipeline entry points:

| Guardrail | File | Behavior |
|---|---|---|
| **PII Masking** | `pii_mask.py` | Regex-based detection and redaction of emails, SSNs, credit card numbers, phone numbers, and IP addresses. Applied on both input (query) and output (answer) |
| **Semantic Cache** | `semantic_cache.py` | Embedding-similarity cache using sentence-transformers. Returns cached answer for queries with cosine similarity ≥ 0.92. LRU eviction (max 256 entries), TTL 1 hour |
| **Token Budget** | `token_budget.py` | Enforces per-query (2,000 tokens) and total (30,000 tokens) limits using tiktoken (cl100k_base). Rejects queries that would exceed budget before any LLM call |
| **Prompt Injection Hardening** | _(injected via system prompts)_ | Security instruction appended to all LLM system prompts. Prevents system prompt leakage, role-playing attacks, and instruction override attempts |

### 8. Stress Testing (`src/stress_testing/`)

Adversarial evaluation suite that probes the reasoning engine for security and robustness failures.

| Component | File | Role |
|---|---|---|
| **Runner** | `runner.py` | Orchestrates test campaigns with configurable concurrency, supports simulation mode (no API cost) and live mode (against real LLM) |
| **Prompt Injection** | `tests/prompt_injection.json` | 10+ attack patterns: system prompt override, role-playing, denial of service, instruction leakage, hypothetical scenarios |
| **Information Evasion** | `tests/information_evasion.json` | Tests that attempt to extract sensitive data, bypass citation requirements, or coerce the model into revealing its instructions |
| **Bias Probing** | `tests/bias_probing.json` | Evaluates the system for demographic, socioeconomic, and other bias patterns in responses |

Run with: `python src/stress_testing/runner.py --verbose` (simulation) or `python src/stress_testing/runner.py --live --verbose` (requires LLM service).

---

## Frontend

A standalone Next.js 14 (App Router) application with TypeScript and Tailwind CSS 3, communicating with the backend via REST and Server-Sent Events.

### Tech Stack

- **Framework**: Next.js 14.2.21 (App Router), React 18.3
- **Language**: TypeScript 5.5
- **Styling**: Tailwind CSS 3.4, CSS variables for dark/light mode
- **Icons**: Lucide React 0.408
- **Testing**: Playwright (E2E)

### Page Layout

| Route | File | Description |
|---|---|---|
| `/` | `app/page.tsx` | Main 3-panel layout: left sidebar (Upload + Past Queries), center (Chat Panel), sidebar toggle |
| `/settings` | `app/settings/page.tsx` | LLM API key management, provider chain display, system component health |
| `/api/query` | `app/api/query/route.ts` | Next.js Route Handler that proxies to backend with SSE support |

### Components

| Component | File | Role |
|---|---|---|
| **Navbar** | `components/Navbar.tsx` | Top navigation with Query/Settings links, theme toggle |
| **ChatPanel** | `components/ChatPanel.tsx` | Message list, streaming text display, source citations, RAGAS scores, agent evaluations. Supports "Ask" and "Retrieve" modes |
| **UploadPanel** | `components/UploadPanel.tsx` | Drag-and-drop file upload, document list with status indicators |
| **PastQueries** | `components/PastQueries.tsx` | Chat session history sidebar with create/delete |
| **EvaluationPanel** | `components/EvaluationPanel.tsx` | Sidebar showing agent node evaluation chain results |
| **StartupSkeleton** | `components/StartupSkeleton.tsx` | Full-page skeleton shimmer shown while polling backend health |
| **ThemeToggle** | `components/ThemeToggle.tsx` | Dark/light mode switch |

### API Key Management

API keys are stored exclusively in the browser's `localStorage` (key: `openrouter_api_key`). They are sent per-request in the `llm_api_key` field of the query body and are never persisted on the server. The Settings page allows setting, viewing, and clearing the key.

### Frontend Directory Structure

```
frontend/
├── app/
│   ├── layout.tsx          # Root layout with ThemeProvider
│   ├── page.tsx            # Home page (3-panel layout)
│   ├── globals.css         # Global styles + skeleton shimmer animation
│   ├── settings/page.tsx   # Settings page
│   └── api/query/route.ts  # API proxy route
├── components/
│   ├── ChatPanel.tsx
│   ├── EvaluationPanel.tsx
│   ├── Navbar.tsx
│   ├── PastQueries.tsx
│   ├── StartupSkeleton.tsx
│   ├── ThemeToggle.tsx
│   └── UploadPanel.tsx
├── lib/
│   ├── api.ts              # Client-side API functions
│   ├── api-server.ts       # Server-side API functions (for Route Handler)
│   └── storage.ts          # localStorage session + API key management
├── providers/
│   └── ThemeProvider.tsx   # Dark/light theme context
├── types/
│   └── index.ts            # All TypeScript interfaces
├── tests/
│   └── streaming.spec.ts   # Playwright E2E streaming test
├── tailwind.config.js
├── tsconfig.json
├── next.config.js
└── package.json
```

---

## Project Structure

```
├── README.md                        ← This file
├── Dockerfile                       ← HF Spaces Docker build (CPU torch)
├── docker-compose.yml               ← Local dev orchestration
├── pyproject.toml                   ← Python project metadata + tool config
├── requirements.txt                 ← Python dependencies
├── .env.example                     ← Environment variable template
├── .pre-commit-config.yaml          ← Pre-commit hooks
├── .secrets.baseline                ← detect-secrets baseline
│
├── config/
│   └── settings.yaml                ← Central application configuration
│
├── src/
│   ├── api/                         ← FastAPI backend
│   │   ├── main.py                  ← App entry point
│   │   ├── query_tracker.py         ← In-flight query monitoring
│   │   ├── guardrails/              ← PII, cache, token budget
│   │   ├── middleware/              ← Auth, logging, metrics, rate limit
│   │   ├── models/models.py         ← Pydantic schemas + Settings
│   │   └── routes/                  ← Health, query, ingest, metadata
│   ├── evaluation/                  ← RAGAS evaluation
│   ├── ingestion/                   ← Parsing, chunking, metadata
│   ├── reasoning/                   ← LangGraph pipeline + LLM client
│   │   ├── pipeline.py              ← StateGraph definition
│   │   ├── state.py                 ← RAGState TypedDict
│   │   ├── nodes/                   ← 8 graph nodes
│   │   └── utils/                   ← LLM client, config loader
│   ├── retrieval/                   ← Hybrid search + reranker
│   ├── storage/                     ← Qdrant, BM25, Neon/Postgres
│   └── stress_testing/              ← Adversarial testing suite
│
├── frontend/                        ← Next.js web application
│   ├── app/                         ← App Router pages + API route
│   ├── components/                  ← React components
│   ├── lib/                         ← API client + storage
│   ├── providers/                   ← Theme provider
│   └── types/                       ← TypeScript definitions
│
├── tests/
│   ├── unit/                        ← Unit tests (ingestion, retrieval,
│   │                                   storage, reasoning, guardrails)
│   └── integration/                 ← Integration tests (API, evaluation,
│                                       reasoning engine)
│
├── scripts/                         ← Utility and profiling scripts
│   ├── test_single_query.py         ← Test single query end-to-end
│   ├── profile_retrieval.py         ← Profile retrieval latency
│   ├── profile_full_pipeline.py     ← Profile full pipeline latency
│   ├── load_test.py                 ← Concurrent load testing
│   ├── capture_trace.py             ← Capture LangGraph trace
│   ├── validate_ragas_regression.py ← Validate RAGAS metric regression
│   └── research/                    ← Research scripts (profiling,
│                                       ground truth generation, auditing)
│
├── data/
│   └── ground_truth/                ← 68-pair gold evaluation set
│
├── docs/                            ← Phase reports, runbooks, plans
│   ├── ops/RUNBOOK.md               ← Operational runbook
│   ├── phase1to3/                   ← Post-remediation technical report
│   ├── phase4 and 5/                ← Reasoning engine report
│   ├── phase 6/                     ← RAGAS comparison report
│   ├── phase 7/                     ← Stress testing report
│   └── phase 8/                     ← Deployment + guardrails docs
│
└── .github/workflows/               ← CI/CD pipeline definitions
    ├── ci.yml                       ← Lint, typecheck, test
    ├── deploy.yml                   ← Backend deployment
    ├── frontend-deploy.yml          ← Frontend deployment
    └── sync-to-hf.yml               ← Hugging Face Spaces sync
```

**Quality assurance**: Pre-commit hooks (`.pre-commit-config.yaml`) enforce no trailing whitespace, no debug statements, valid YAML/TOML, secrets scanning (`.secrets.baseline` via detect-secrets), and ground truth JSON schema validation on every commit.

---

## Quick Start Guide

### Prerequisites

- **Python** 3.10 or later
- **Node.js** 18 or later
- **Qdrant Cloud** account (or local Docker Qdrant)
- **Neon/Postgres** database (or SQLite for local dev — zero config)
- **OpenRouter**, **Groq**, or **OpenAI** API key

### Backend Setup

```bash
# 1. Clone and enter the project
cd production-rag

# 2. Create environment file
cp .env.example .env

# 3. Edit .env with your credentials:
#    - OPENROUTER_API_KEY, GROQ_API_KEY, or OPENAI_API_KEY
#    - QDRANT_URL and QDRANT_API_KEY (cloud) or leave blank (local)
#    - DATABASE_URL (Neon) or leave blank (SQLite)
#
# nano .env

# 4. Install Python dependencies
pip install -r requirements.txt

# 5. Start the API server
uvicorn src.api.main:app --host 0.0.0.0 --port 7860
```

The server will pre-load the sentence-transformer embedding model on first startup (~25s). Once you see `Uvicorn running on http://0.0.0.0:7860`, the backend is ready.

**Verify**:
```bash
curl http://localhost:7860/api/v1/health/live
# → {"status":"alive","version":"1.0.0","components":{"api":"alive"}}
```

### Frontend Setup

```bash
# 1. Navigate to frontend
cd frontend

# 2. Create environment file
cp .env.local.example .env.local

# 3. Edit .env.local — the API URL should match your backend
#    NEXT_PUBLIC_API_URL=http://localhost:7860
#    NEXT_PUBLIC_API_KEY=my-secret-access-key

# 4. Install dependencies
npm install

# 5. Start development server
npm run dev
```

Open **http://localhost:3000** in your browser. The frontend will show a skeleton screen while it polls the backend health endpoint. Once the backend responds, the full application loads.

### Docker Deployment

```bash
docker-compose up -d
```

This builds the Docker image and starts the API service on port 7860.

---

## Usage Guide

### Making a Query

1. Open the application in your browser (default: `http://localhost:3000`)
2. Wait for the skeleton screen to disappear (backend health check)
3. Type your question in the chat input at the center of the screen
4. Press Enter or click the send button
5. The response streams in as it's generated, followed by source citations and agent evaluation results

**Example queries**:
- "What is the total budget for fiscal year 2024?"
- "Summarize the key findings from the annual report"
- "Compare the financial figures between 2023 and 2024"

### Streaming Responses

The default mode streams the answer token-by-token using Server-Sent Events (SSE). You'll see the text appear progressively rather than waiting for the full response. After the answer, a metadata block shows:
- **Sources**: Up to 5 retrieved documents with relevance scores
- **Agent Evaluations**: Pass/fail status from Gatekeeper, Auditor, and Strategist
- **RAGAS Scores**: Faithfulness, Answer Relevancy, Context Precision
- **Latency**: Total end-to-end processing time

### Uploading Documents

1. Locate the **Upload Panel** in the left sidebar
2. Drag and drop PDF, DOCX, XLSX, or TXT files, or click to browse
3. Each file shows an upload progress indicator
4. Once processed, the document appears in the documents list
5. Newly uploaded documents are immediately searchable by the retrieval system

### Providing Your Own API Key

If the system has no API key configured (or you want to use your own), navigate to:

1. Click the **Settings** icon in the top navigation bar
2. In the **LLM Configuration** section, paste your OpenRouter API key (starts with `sk-or-v1-`)
3. Click **Save Key**
4. The key is stored in your browser only — it is sent per-request and never saved on the server

The **LLM State** section shows the provider chain status, indicating whether the system is using the environment key or your personal key.

### Monitoring System Health

The **Settings** page displays real-time health status for all system components:
- **API Server**: Backend reachability
- **Vector DB (Qdrant)**: Vector store connection status
- **Metadata DB (Postgres)**: Relational database connectivity
- **BM25 Index**: Sparse index availability
- **LLM State**: Active provider and key configuration

Use the **Refresh** button to pull the latest status from the backend health endpoint.

---

## Configuration

Central configuration in `config/settings.yaml` controls all major subsystems:

| Section | Key Parameters |
|---|---|
| `ingestion` | `chunk_size`, `chunk_overlap`, `chunker_type` (naive or structure_aware), `table_extraction`, `window_size`, `department_mapping`, `min_char_threshold` |
| `retrieval` | `dense_top_k`, `sparse_top_k`, `rerank_pool_size`, `rerank_top_n`, `rrf_k` |
| `llm` | `provider` (auto or explicit), `profiles` (endpoint, model, env_key, timeout per provider) |
| `guardrails` | PII sensitivity, cache similarity threshold, token budget limits, prompt injection toggle |
| `storage` | Qdrant collection name, vector size, BM25 persist path, Postgres schema |
| `monitoring` | Prometheus metric buckets, Sentry sample rate |
| `evaluation` | RAGAS alert thresholds, production sample rate |
| `latency` | Per-component budget: `retrieval_budget_ms: 500`, `rerank_budget_ms: 1000`, `generation_budget_ms: 30000`, `total_p95_ms: 300000` |

**Environment variables** override settings for secrets:
- `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `OPENAI_API_KEY` — LLM provider keys
- `QDRANT_URL`, `QDRANT_API_KEY` — Qdrant Cloud connection
- `DATABASE_URL` — Neon/Postgres connection string
- `API_KEY` — API authentication key
- `RATE_LIMIT_PER_MINUTE` — Global rate limit (default: 3)
- `LLM_PROVIDER` — Explicit provider override

---

## Monitoring

### Prometheus Metrics

A `/metrics` endpoint (`src/api/middleware/metrics.py`) exposes Prometheus-formatted metrics for production observability. Accessible at `GET /api/v1/metrics`.

| Metric | Type | Labels | Description |
|---|---|---|---|
| `rag_query_total` | Counter | `status` | Total queries processed |
| `rag_query_duration_seconds` | Histogram | — | Request latency (buckets: 0.1s to 180s) |
| `rag_query_tokens_total` | Counter | — | Total LLM tokens consumed |
| `rag_active_queries` | Gauge | — | Currently in-flight queries |
| `rag_ragas_faithfulness` | Gauge | — | Latest RAGAS faithfulness score |
| `rag_ragas_answer_relevancy` | Gauge | — | Latest RAGAS answer relevancy score |
| `rag_ragas_context_precision` | Gauge | — | Latest RAGAS context precision score |

### Health Endpoints

| Endpoint | Cache | Purpose |
|---|---|---|
| `GET /api/v1/health/live` | None | Lightweight liveness probe — returns immediately |
| `GET /api/v1/health` | 30s | Full component health (Qdrant, BM25, Postgres, LLM, auth) |
| `GET /api/v1/health/ready` | None | Readiness check for Kubernetes-style deployments |

### Structured Logging

All API requests are logged as JSON via `LoggingMiddleware` with fields:
`event`, `request_id`, `method`, `url`, `status_code`, `duration_s`, `client_ip`

### In-Flight Query Tracking

`QueryTracker` (`src/api/query_tracker.py`) monitors all active queries with:
- Per-query start time and current graph node
- Stale detection (queries exceeding 5-minute threshold)
- Debug endpoints: `POST /api/v1/debug/active_queries` and `POST /api/v1/debug/clear_query`

### Rate Limiting

Rate limiting is implemented via **SlowAPI** middleware with two tiers:

| Scenario | Limit | Mechanism |
|---|---|---|
| Requests using the system's env API key | 3 concurrent queries max | Concurrent gate in `query.py` using `QueryTracker.active_count()` |
| Requests with a user-provided API key | 10 concurrent queries max (server safety cap) | Same gate, higher threshold when `llm_api_key` is present |
| Non-query endpoints (health, metadata) | 3 requests per minute per API key | SlowAPI global `Limiter` with per-key bucketing |

The rate limit key function (`src/api/middleware/rate_limit.py`) uses the `X-API-Key` header when available, falling back to the client IP address. Query routes are exempted from SlowAPI's global limit and rely on the concurrent gate instead, ensuring user-key requests aren't artificially restricted.

### Authentication

API authentication is handled via `X-API-Key` header verification (`src/api/middleware/auth.py`):

- **Header**: `X-API-Key: <key>` sent with every request
- **Scope**: Required for all endpoints except `/health/live`, `/health`, and `/`
- **Key format**: Supports multiple comma-separated values via the `API_KEY` environment variable
- **Verification**: Provided key is checked against configured valid keys; returns 401 on mismatch
- **Frontend integration**: The frontend automatically attaches the `X-API-Key` header (configured via `NEXT_PUBLIC_API_KEY` in `.env.local`)

### Latency Profiling

Verified wall-clock timings are logged in `docs/LATENCY_LOG.md`. Individual components can be profiled via scripts in `scripts/`:

```bash
python scripts/profile_retrieval.py
python scripts/profile_full_pipeline.py
python scripts/load_test.py --concurrency 2 --requests 3
```

---

## Testing

```bash
# Run all unit and integration tests
python -m pytest tests/ -v

# Run specific test categories
python -m pytest tests/unit/ -v
python -m pytest tests/integration/ -v
python -m pytest tests/unit/reasoning/ -v
python -m pytest tests/unit/guardrails/ -v

# Lint and type checking
ruff check .
ruff format --check .
mypy src/

# Frontend E2E tests
cd frontend && npx playwright test

# Run guardrail unit tests
python -m pytest tests/unit/guardrails/ -v

# Profile individual components
python scripts/profile_retrieval.py
python scripts/profile_full_pipeline.py
python scripts/load_test.py --concurrency 2 --requests 3

# Test a single query end-to-end
python scripts/test_single_query.py

# Adversarial stress testing
python src/stress_testing/runner.py --verbose
```

---

## Deployment

### Backend (Hugging Face Spaces)

The backend ships as a Docker container to Hugging Face Spaces:
1. Set the Space SDK to **Docker** in the HF Space settings
2. The `Dockerfile` builds a CPU-optimized image with torch, sentence-transformers, and all dependencies
3. Configure environment secrets in the HF Space dashboard (API keys, Qdrant URL, database URL)
4. The Space auto-builds on push to the connected repository

### Frontend (Vercel / Cloudflare Pages)

The frontend deploys independently:
- **Vercel**: Connect the repository, set build command to `cd frontend && npm run build`, output directory to `frontend/.next`
- **Cloudflare Pages**: Set build command to `npm run build`, build output to `.next`

### CI/CD

GitHub Actions workflows in `.github/workflows/`:
- `ci.yml` — Runs lint, typecheck, and tests on every PR
- `deploy.yml` — Deploys backend to HF Spaces on push to main
- `frontend-deploy.yml` — Deploys frontend to Vercel/Cloudflare
- `sync-to-hf.yml` — Synchronizes repository with HF Space

---

## Performance Targets

| Component | Target | Phase 6 Result |
|---|---|---|
| Retrieval | ≤ 500ms | ✅ Verified |
| Reranking | ≤ 600ms | ✅ Verified (ONNX) |
| Full pipeline (p95) | ≤ 180s | ⚠️ CPU-bound, 3-min budget |
| Faithfulness | > 0.80 | ✅ 0.87 |
| Answer Relevancy | > 0.75 | ✅ 0.78 |
| Context Precision | > 0.61 | ✅ 0.80 |
| Context Recall | > 0.75 | ⚠️ 0.55 |
| Answer Completeness | > 0.80 | ⚠️ 0.62 |
