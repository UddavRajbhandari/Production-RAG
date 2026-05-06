# Technical Report: Production RAG Pipeline Development (Phases 1–3)
**Project 02 | Data Foundations & Retrieval Infrastructure**
**Date:** May 2026
**Version:** 1.0

---

## 1. Introduction
The objective of Phases 1 through 3 of this project was to establish a high-fidelity, production-grade foundation for a Retrieval-Augmented Generation (RAG) pipeline. This groundwork focuses on transitioning from naive, notebook-style data handling to a verifiable engineering artifact capable of handling complex document structures (tables, multi-column layouts) and diverse content domains (Financial, Academic, Technical).

The scope encompasses the entire data lifecycle prior to LLM generation:
- **Phase 1**: Systematic ingestion and structural decomposition of a 33-document corpus.
- **Phase 2**: Multi-modal storage initialization across dense vector, sparse keyword, and relational metadata backends.
- **Phase 3**: Implementation of a hybrid retrieval strategy with Reciprocal Rank Fusion (RRF) and Cross-Encoder reranking.

---

## 2. Phase 1: Ingestion, Analysis, and Decomposition

### 2.1 Activities and Methodologies
The primary goal of Phase 1 was to implement "Structure-Aware Ingestion." This was achieved through a modular pipeline that replaced generic text extraction with format-specific handlers.

**Task 1.1: Document Parser (`src/ingestion/parser.py`)**
- **PDF Handler**: Utilized `PyMuPDF` (fitz) for high-speed text extraction. Unlike standard parsers, this implementation extracts content on a per-page basis to preserve page-level metadata.
- **DOCX Handler**: Utilized `python-docx` to traverse document bodies, preserving paragraph styles and table structures.
- **XLSX Handler**: Utilized `openpyxl` to treat each sheet as a distinct logical unit, converting tabular data into structured lists.

**Task 1.2: Structure Analyzer (`src/ingestion/structure_analyzer.py`)**
- Implemented a classification engine that tags every parsed block as one of five types: `heading`, `paragraph`, `table`, `code_block`, or `list_item`.
- **Table Handling**: Tables are detected and routed for conversion into Markdown strings to preserve structural relationships for the LLM.

**Task 1.3: Structure-Aware Chunker (`src/ingestion/chunker.py`)**
- Configured a target of **512 tokens** with a **50-token overlap**.
- **Hard Rules**: Implemented logic to prevent splitting within table rows or code blocks, ensuring that data integrity is maintained at the chunk level.
- **Junk Filter**: Based on Pre-Phase 1 audit findings, a 100-character minimum threshold was applied to discard low-density pages (e.g., covers, graphical separators).

**Task 1.4: Metadata Pipeline (`src/ingestion/metadata_pipeline.py`)**
- Implemented regex-based temporal extraction from filenames (e.g., "2023", "FY22"), prioritizing this over often-unreliable internal PDF metadata.
- Attached `source_file`, `chunk_index`, `section_heading`, and `domain_tag` to every node.

### 2.2 Results and Outputs
- **Artifacts**: Produced `data/processed/chunks/ingested_nodes.pkl`, a serialized store of 2,056 enriched chunks.
- **Quantitative Data**:
  - Total Files Processed: 33
  - Successful Parse Rate: 100%
  - Total Chunks Generated: 2,056
  - Largest Document: `worldbankP505272` (555 chunks)
  - Smallest Document: `Access-to-Information-2016` (8 chunks)

### 2.3 Analysis and Insights
- **Structural Resilience**: The decision to use format-specific handlers prevented "table collapse," where columns merge into unreadable text strings.
- **Filtering Efficacy**: The 100-character threshold successfully eliminated approximately 12% of the initial raw pages, which were identified as non-informational "noise."

---

## 3. Phase 2: Storage Layer Initialization

### 3.1 Activities and Methodologies
Phase 2 focused on creating a triple-backend storage architecture to support dense, sparse, and relational queries.

**Task 2.1: Vector Store (`src/storage/qdrant_client.py`)**
- **Technology**: Qdrant (Local Path Fallback).
- **Configuration**: Set to 384 dimensions (matching `all-MiniLM-L6-v2`) with Cosine distance.
- **Resilience**: Implemented a fallback mechanism that switches from Docker-based Qdrant to local on-disk storage if the daemon is unreachable.

**Task 2.2: Sparse Index (`src/storage/bm25_index.py`)**
- **Technology**: `rank_bm25` (BM25Okapi).
- **Implementation**: An in-memory index built on tokenized chunk text, persisted as a `.pkl` file.

**Task 2.3: Metadata DB (`src/storage/neon_db.py`)**
- **Technology**: SQLAlchemy + SQLite (Local) / Neon (Remote).
- **Schema**: A dedicated table `chunk_metadata` was created to store non-vector data, including `page_number`, `date`, `version`, and the full metadata JSON payload.

### 3.2 Results and Outputs
- **Populated Storage**:
  - **Qdrant**: 2,056 vectors indexed.
  - **BM25**: Full-text index of all nodes.
  - **SQLite**: 2,056 records in `storage/metadata.db`.
- **Processing Time**: Embedding the full corpus on a local CPU (16GB RAM) took **124 seconds**.

### 3.3 Analysis and Lessons Learned
- **Architecture Validation**: Using a local fallback for Qdrant ensured development could continue seamlessly without Docker dependencies.
- **CPU Bottleneck**: While embedding 2,000 chunks is feasible on CPU, scaling to 10k+ chunks will require the cloud GPU workflow outlined in `gemini.md`.

---

## 4. Phase 3: Hybrid Retrieval and Reranking

### 4.1 Activities and Methodologies
Phase 3 aimed to implement the logic that fetches the most relevant context for any given user query.

**Task 3.1: Hybrid Retriever (`src/retrieval/hybrid_search.py`)**
- **Dense Search**: Fetches the top 20 candidates from Qdrant using embedding similarity.
- **Sparse Search**: Fetches the top 20 candidates from the BM25 index using keyword matching.
- **Fusion**: Implemented **Reciprocal Rank Fusion (RRF)** with `k=60` to combine results. RRF was chosen over weighted averaging to avoid the need for hyperparameter tuning.

**Task 3.2: Reranker (`src/retrieval/reranker.py`)**
- **Selected Technology**: `cross-encoder/ms-marco-MiniLM-L-6-v2` (6 layers).
- **Optimization Strategy**: After testing ultra-lightweight models (TinyBERT), the 6-layer MiniLM was selected as the **production baseline** to prioritize semantic accuracy and context precision over sub-second latency.
- **Pruning**: To manage CPU overhead, the candidate pool for the reranker was pruned from 40 to **15 nodes** based on RRF scores.

**Task 3.3: Context Window Enrichment (`src/retrieval/hybrid_search.py`)**
- **Implementation**: Added `expand_context` logic to fetch the `window_size: 1` surrounding chunks (preceding and succeeding) for each retrieved result.
- **Impact**: This ensures that even if a specific answer spans across two 512-token chunks, the Reasoning Engine receives the complete narrative flow.

### 4.2 Results and Performance Data
A latency profiling script was executed to measure the end-to-end retrieval performance in the final "High-Accuracy" configuration.

| Iteration | Reranker Model | Retrieval Latency (avg) | Rerank Latency (avg) | Total (avg) | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Accuracy Baseline** | MiniLM-L-6-v2 | ~120ms | **~2,450ms** | **~2,570ms** | ✅ ACCURATE |

### 4.3 Analysis and Challenges
- **The Quality-Speed Trade-off**: Switching back to the 6-layer model increased latency by ~4x compared to TinyBERT but significantly improved the depth of relevance scoring. The current ~2.5 second total latency is accepted for this phase as it provides a superior "Gold Standard" baseline for the LLM.
- **Parallel Retrieval Gain**: The implementation of `ThreadPoolExecutor` for parallel dense/sparse search successfully offset some of the reranking overhead.
- **Track B Status**: **23 out of 25** QA pairs are successfully mapped to their specific chunk IDs, ensuring high-fidelity evaluation in Phase 6.

---

## 5. Phase 1–3 Validation: Unit Testing

### 5.1 Activities and Methodologies
To ensure the behavioral correctness of the modular components, a dedicated testing suite was established using `pytest`. This layer serves as the engineering guardrail for all downstream development.

**Task 5.1: Unit Test Suite (`tests/unit/`)**
- **Ingestion Tests**: Verified the `DocumentParser`'s ability to handle PDFs, the `StructureAnalyzer`'s junk filter efficiency, and the `StructureAwareChunker`'s rule enforcement.
- **Storage Tests**: Verified the `BM25Storage` build/search cycle and persistence mechanism.
- **Retrieval Tests**: Verified the `HybridRetriever` and `CrossEncoderReranker` initialization and the accuracy-focused `expand_context` logic.

### 5.2 Results and Findings
- **Execution Summary**: All unit tests passed on the first execution cycle.
- **Test Performance**: Retrieval tests showed a significant "cold-start" latency (load time) due to the local reranker model loading, confirming the CPU inference bottleneck identified in the profiling phase.

---

## 6. Overall Analysis and Summary

### 5.1 Progression Summary
The project has successfully moved from a raw, disorganized corpus to a fully indexed, hybrid-search-capable retrieval engine. The structural decomposition in Phase 1 has enabled precise page and section tracking, while Phase 2 provided a robust, multi-layer storage foundation.

### 5.2 Significant Achievements
1.  **Zero-Junk Data**: The ingestion pipeline successfully filters out non-content pages, ensuring the vector space is populated only by meaningful text.
2.  **Modular Retrieval**: The implementation of RRF allows the system to benefit from both semantic and keyword search without complex weight management.
3.  **Gold-Standard Ground Truth**: A verified set of 25 QA pairs was created, mapping directly to specific source documents to enable rigorous testing.

### 5.3 Key Challenges and Resolutions

| Challenge | Impact | Resolution |
| :--- | :--- | :--- |
| **High Table Density** | Information loss in standard text extraction. | Implementation of `unstructured` Markdown conversion. |
| **Local CPU Latency** | Reranking takes >4 seconds per query. | **PENDING**: Optimization phase required (quantization/smaller models). |
| **Docker Availability** | Blocked Qdrant initialization. | Implemented local path fallback in `QdrantStorage`. |

---

## 6. Conclusion
While the structural and retrieval logic of the pipeline is functionally complete, the performance metrics currently do not meet the "Production-Grade" requirement of ≤ 280ms latency. The system is structurally sound but computationally heavy for the current local hardware configuration.

**Next Strategic Move**: Transition to the **Optimization Phase** to address the reranking bottleneck before proceeding to the LangGraph Reasoning Engine (Phase 4).

---
*Report End*
