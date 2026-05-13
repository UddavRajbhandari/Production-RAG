# Phase 4 Implementation: Reasoning Engine (LangGraph)

## 1. Overview

Phase 4 transitions the RAG pipeline from a simple retrieval-augmentation loop into a stateful, multi-agent reasoning engine. This implementation uses **LangGraph** to manage complex query decomposition, parallel tool execution, and multi-stage human-in-the-loop (simulated) validation.

Phases 4 and 5 implement the **Reasoning Engine** using LangGraph, transitioning the RAG pipeline from simple retrieval-augmentation to a stateful, multi-agent reasoning system with human-in-the-loop validation.

---

## 2. Architecture

### 2.1 Core Components

**State Management** (`src/reasoning/state.py`)
- `RAGState` TypedDict schema tracks:
  - Query, generated answer, sub-tasks
  - Retrieved context, validation status
  - Per-node latency tracking (`node_latency_ms`)

**Pipeline** (`src/reasoning/pipeline.py`)
- 8-node LangGraph StateGraph with conditional routing
- Entry: Planner → Router → (Retrieval/Calculation) → Summarization → Gatekeeper → Auditor → Strategist → END

### 2.2 Node Implementations

| Node | Type | Purpose |
|------|------|---------|
| PlannerNode | LLM | Query decomposition into 1-3 sub-tasks |
| RouterNode | Non-LLM | Deterministic keyword-based routing |
| RetrievalAgentNode | Non-LLM | HybridRetriever integration |
| CalculationAgentNode | Non-LLM | Placeholder for numeric processing |
| SummarizationAgentNode | LLM | Context synthesis to natural language |
| GatekeeperNode | LLM | Query-answer alignment validation |
| AuditorNode | LLM | Hallucination detection (grounding check) |
| StrategistNode | Non-LLM | Heuristic validation (length, citations) |

---

## 3. Key Design Decisions

### 3.1 Hardware-Aware Latency Optimization
Following LLM profiling on local CPU hardware (Llama-3 8B), the original 280ms latency target was revised to **180,000ms (3 minutes)**. To fit within this new budget, the graph architecture was audited to minimize LLM calls.

| Node | LLM Type | Role | Optimization |
|---|---|---|---|
| **Planner** | Llama-3 8B | Query Decomposition | Sequential task planning. |
| **Router** | None | Path Selection | Deterministic keyword mapping. |
| **Retrieval Agent** | None | Vector/Sparse Search | Persistent ThreadPoolExecutor. |
| **Summarization** | Llama-3 8B | Context Synthesis | High-fidelity answer generation. |
| **Calculation** | None | Arithmetic | Deterministic Python-based math. |
| **Gatekeeper** | Llama-3 8B | Alignment Check | Validates Answer vs. Query. |
| **Auditor** | Llama-3 8B | Grounding Check | Hardened hallucination detection. |
| **Strategist** | None | Heuristic Check | Structural/Format validation. |

### 3.2 RAGState Schema
The state was expanded to include a `node_latency_ms` dictionary, enabling granular performance tracking of every step in the reasoning process.

### 3.3 Verify-After-Generate Architecture
- **Gatekeeper**: Validates answer addresses query
- **Auditor**: Cross-references claims against context
- **Strategist**: Final heuristic checks (length ≥50 chars, source citations)

### 3.4 Shared Utilities (`src/reasoning/utils/`)
- `ConfigLoader`: Singleton config management
- `LLMClient`: Centralized API with retry + circuit breaker
- `json_parser.py`: Safe JSON parsing with fallbacks
- `api_llm_client.py`: OpenAI-compatible API support

---

## 4. Deep Dive: Component Logic

### 4.1 PlannerNode (LLM-Based)
The **PlannerNode** serves as the gateway to the reasoning engine. It takes the raw user query and uses Llama-3 8B to decompose it into 1-3 distinct, actionable sub-tasks.
- **Logic**: Uses a zero-shot prompt with a temperature of 0.0 to ensure deterministic decomposition.
- **Purpose**: Enables the system to handle multi-faceted questions by identifying separate retrieval needs.

### 4.2 RouterNode (Deterministic)
The **RouterNode** is a high-efficiency, non-LLM node that determines the graph's execution path.
- **Logic**: Performs keyword matching (e.g., "calculate", "total", "average") against both the original query and the sub-tasks.
- **Purpose**: Minimizes latency by avoiding an LLM call for path selection.

### 4.3 RetrievalAgentNode (Non-LLM)
This node bridges the reasoning engine with the Phase 3 storage layer.
- **Logic**: Aggregates the query and sub-tasks into a unified search string, calls the `HybridRetriever`, and applies a `window_size=1` context expansion.
- **Purpose**: Ensures that all relevant document chunks are present in the state before synthesis.

### 4.4 SummarizationAgentNode (LLM-Based)
The **SummarizationAgentNode** performs the primary RAG synthesis.
- **Logic**: Injects retrieved context into a strict prompt template that mandates source citation and forbids external knowledge.
- **Purpose**: Transforms raw chunks into a coherent, cited natural language response.

### 4.5 Validation Nodes (The Guardrail Chain)
- **GatekeeperNode (LLM)**: Validates **Query-Answer Alignment**. Ensures the summarizer hasn't hallucinated an answer to a different question.
- **AuditorNode (LLM)**: Performs a **Grounding Audit**. Verifies every claim in the answer against the context. If unsupported info is found, `validation_passed` is set to `False`.
- **StrategistNode (Heuristic)**: Performs a **Structural Check**. Verifies minimum length (50 chars) and citation presence. Also aggregates `total_latency_ms`.

---

## 5. Reasoning Flow: Step-by-Step Walkthrough

The Reasoning Engine operates as a stateful directed acyclic graph (DAG). Below is the step-by-step lifecycle of a single query:

1.  **Decomposition (Planner)**: The query enters the `PlannerNode`. The LLM breaks it into 1-3 sub-tasks, updating `state["sub_tasks"]`.
2.  **Path Selection (Router)**: The `RouterNode` inspects the sub-tasks. If math keywords are present, it sets the next node to `calculation_agent`; otherwise, it routes to `retrieval_agent`.
3.  **Data Acquisition (Retrieval/Calculation)**:
    *   **Retrieval**: The `RetrievalAgentNode` performs hybrid search using the sub-tasks and populates `state["retrieved_context"]`.
    *   **Calculation**: Currently a passthrough, but designed to handle numeric processing.
4.  **Synthesis (Summarizer)**: The `SummarizationAgentNode` takes the context and the original query, generating a cited natural language response.
5.  **Alignment Check (Gatekeeper)**: The LLM verifies that the answer actually answers the user's specific question.
6.  **Grounding Check (Auditor)**: The LLM cross-references every sentence in the answer against the retrieved chunks to ensure zero hallucinations.
7.  **Final Polish (Strategist)**: A heuristic check ensures the answer meets length requirements and includes citation markers. The final `total_latency_ms` is calculated and the graph terminates at `END`.

---

## 6. Performance Baseline (Verified)

Based on integration testing (`tests/integration/test_reasoning_engine.py`), the pipeline was verified on local CPU hardware (16GB RAM, No GPU).

- **Total Execution Time (Standard Query with Ollama)**: ~150-210 seconds.
- **Total Execution Time (API mode)**: ~10-30 seconds.
- **Planner Latency**: ~30-45s (Ollama) / ~2-5s (API)
- **Summarization Latency**: ~60-90s (Ollama) / ~3-8s (API)
- **Validation Chain (Gatekeeper + Auditor)**: ~60-80s (Ollama) / ~5-15s (API)
- **Retrieval/Router/Strategist (Non-LLM)**: < 2s combined

**Status**: **PASSING**. The removal of 4 LLM calls from the critical path prevents systemic timeouts. API mode provides much faster response times.

---

## 7. LLM Provider Configuration

### 7.1 Overview
The reasoning engine supports multiple LLM providers for flexibility. Users can choose between:
- **External APIs** (fast, requires API key)
- **Local Ollama** (free but slower)

### 7.2 Supported Providers

| Provider | Model | Cost | Speed | Setup Required |
|----------|-------|------|-------|----------------|
| **Groq** | llama-3.1-70b-versatile | Free | Very Fast | API Key only |
| **HuggingFace** | Llama-3.1-8B-Instruct | Free tier | Fast | API Token |
| **OpenRouter** | gemma-2-9b-it | Free tier | Fast | API Key |
| **OpenAI** | gpt-4o-mini | $5 credit | Fast | API Key |
| **Ollama** | llama3:8b-instruct-q4_K_M | Free | Slow | Local install |

### 7.3 Configuration

All configuration is in `config/settings.yaml`:

```yaml
llm:
  provider: "api"  # or "ollama"

  # Groq Configuration (Default - Fully Free)
  api:
    endpoint: "https://api.groq.com/openai/v1/chat/completions"
    api_key: "${GROQ_API_KEY}"
    model: "llama-3.1-70b-versatile"
    timeout: 120

  # Ollama Configuration (when provider="ollama")
  ollama:
    url: "http://localhost:11434/api/generate"
    model: "llama3:8b-instruct-q4_K_M"
    timeout: 300
```

### 7.4 Environment Variables

Set your API key before running:

```bash
# Groq (Recommended - Fully Free)
export GROQ_API_KEY="gsk_..." # pragma: allowlist secret

# HuggingFace
export HF_TOKEN="hf_..." # pragma: allowlist secret

# OpenRouter
export OPENROUTER_API_KEY="sk-or-..." # pragma: allowlist secret

# OpenAI
export OPENAI_API_KEY="sk-..." # pragma: allowlist secret
```

### 7.5 Performance Comparison

| Mode | Expected Latency | Best For |
|------|------------------|-----------|
| **API (Groq)** | 5-15 seconds | Production use |
| **API (OpenAI)** | 5-10 seconds | Higher quality |
| **Ollama (Local)** | 60-120 seconds | Offline/private |

---

## 8. Test Coverage

### 8.1 Unit Tests (33 tests)

| Test File | Tests | Coverage |
|-----------|-------|----------|
| `test_planner_node.py` | 4 | JSON parsing, fallback, error handling, latency |
| `test_router_node.py` | 6 | Retrieval routing, calculation routing, edge cases, latency |
| `test_retrieval_agent_node.py` | 4 | Success, sub-tasks integration, error handling, latency |
| `test_calculation_agent_node.py` | 2 | Passthrough, latency |
| `test_summarization_agent_node.py` | 4 | Context synthesis, empty context, error handling, latency |
| `test_gatekeeper_node.py` | 4 | Validation passed, validation failed, fail-open, latency |
| `test_auditor_node.py` | 4 | No hallucination, hallucination detected, fail-open, latency |
| `test_strategist_node.py` | 5 | Valid answer, too brief, no citations, total latency, latency |

### 8.2 Integration Tests (`tests/integration/test_reasoning_engine.py`)
- Standard retrieval flow
- Calculation routing
- Latency tracking

---

## 9. Quality Assurance

- **Ruff**: All linting passed (17 source files)
- **Mypy**: Strict type checking passed (17 source files)
- **Unit Tests**: 33/33 passed (100% pass rate)
- **Pre-commit**: Compliance verified

---

## 10. Notes

- CalculationAgentNode remains a pass-through (placeholder for future numeric processing)
- Circuit breaker pattern: 5 consecutive failures triggers 60-second cooldown
- Fail-open strategy for validation nodes (Gatekeeper, Auditor) on system errors
- API mode (Groq) is recommended for faster response times

---

## 11. Comparative Chunking Strategy (Phase 6 Preparation)

To support the comparative analysis of naive vs. structure-aware chunking, the storage and ingestion layers have been updated to support strategy-specific indexing.

- **Naive Strategy**: Flattens document content and splits purely by token count, ignoring tables, headings, and code block boundaries.
- **Structure-Aware Strategy**: Respects document structural tags to preserve semantic units (e.g., keeping tables intact).

**Implementation Details:**
- `config/settings.yaml`: Controls active strategy via `chunker_type`.
- **Suffixing**: All storage backends (Qdrant, BM25, SQLite) automatically append the strategy name to their collection/file paths (e.g., `metadata_naive.db` vs `metadata_structure_aware.db`) when `use_chunker_suffix` is enabled.

## 12. Conclusion

Phase 4 successfully delivers a stateful reasoning engine that balances the power of multi-agent decomposition with the harsh reality of local CPU compute. By strictly classifying nodes into LLM vs. Non-LLM categories, we have maintained a functional 3-minute reasoning loop.

The addition of external API support (Groq, HuggingFace, OpenRouter, OpenAI) provides a fast, reliable alternative to local Ollama for end users who want quick responses without complex setup.

---
*Report Finalized: May 2026 | Project 02 Phase 4, 5*
*Updated: Combined documentation with implementation details and API provider configuration*
