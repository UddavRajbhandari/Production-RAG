# Latency Tracking Log — Project 02

This log tracks the end-to-end performance of the RAG pipeline. Metrics are recorded at the exit of each phase and after major architectural changes.

**Target p95 Budget:** 280ms

| Date | Phase | Description | Retrieval (ms) | Rerank (ms) | LLM Gen (ms) | Total (ms) | Status |
|---|---|---|---|---|---|---|---|
| 2026-05-07 | Phase 3 Exit | Pre-Remediation Baseline | ~120 | ~2,450 | N/A | ~2,570 | ❌ OVER BUDGET |
| 2026-05-07 | Phase 3 Exit | Post-Remediation (PyTorch) | 188.5 | 2,269.2 | N/A | 2,457.7 | ❌ OVER BUDGET |
| 2026-05-08 | Phase 3 Exit | Post-Remediation (ONNX - Est.) | 188.5 | ~500.0 | TBD | ~688.5 | ⚠️ WARM |
| 2026-05-08 | Phase 3 Exit | 8B Model CPU Baseline | 152.0 | ~500.0 | ~47,568 | ~48,220 | ❌ 3-MIN BUDGET |

---

## Component Benchmarks (Averages)

### LLM Inference (Ollama - Llama-3-8B-Instruct - CPU)
*Profiled 2026-05-08. Hardware: 16GB RAM, No GPU.*

| Prompt Type | TTFT (ms) | TPS (tokens/s) | Total Time (ms) |
|---|---|---|---|
| Routing (short) | 10,333 | 0.4 | 11,287 |
| Summary (med) | 21,392 | 1.8 | 51,510 |
| Reasoning (long) | 15,448 | 2.5 | 79,908 |

---

## Strategic Risk: Hardware Latency Ceiling
The **Llama-3 8B model** on local CPU is too slow for sequential "Planner -> Agent -> Validator" logic under original RAG targets.

**Decision Log:**
1. **Revised Target:** Updated `total_p95_ms` in `settings.yaml` to **180,000ms** (3 minutes).
2. **Inference Mode:** Path B (Streaming) will be implemented in Phase 8 to mitigate UX impact. Phase 4 will focus on **Accuracy/Correctness** via sequential nodes.
3. **Retrieval Optimization:** Moved `ThreadPoolExecutor` to persistent class attribute in `HybridRetriever` to reduce ~128ms spawn overhead.

### Retrieval Backends
* Qdrant (Local): ~40ms
* BM25 (In-memory): ~15ms
* RRF Fusion: ~5ms
* Overhead/Wait: ~128ms (Parallel execution latency)
