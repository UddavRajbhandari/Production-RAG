# Corpus Audit Report (Pre-Phase 1)

## Overview
This audit covered 25 out of 33 documents (approx. 75% of the corpus), including the initial 5-file sample and a 20-file expanded audit. The goal was to validate parsing assumptions for the production RAG pipeline.

## Key Findings

### 1. The "Zero-Text" & Low-Density Page Issue
- **Observation**: Multiple PDFs (e.g., `AtI-annual-report-2012`, `Python-tutorial-pdf3`, `worldbankP505272`) contain pages with **0 to 100 characters**.
- **Context**: These are typically cover pages, graphical separators, or images without an OCR layer.
- **Risk**: Naive chunking will create "junk" nodes that pollute retrieval results.
- **Mitigation**: Implement a minimum character threshold (e.g., < 100 chars) for node creation in `src/ingestion/chunker.py`.

### 2. Tabular Data Complexity
- **Observation**: High table density detected in financial and annual reports (e.g., `FAO_EMSTOT.pdf`, `WB_CLEAR.pdf`, and DOCX files).
- **Context**: Up to 3 tables per page detected in some cases.
- **Risk**: Standard PDF text extraction collapses table columns, making numerical reasoning impossible.
- **Mitigation**: Use `unstructured` or `LlamaParse` to convert tables into Markdown/HTML format during ingestion to preserve structural relationships.

### 3. Document Scale & Diversity
- **Observation**: Document lengths vary significantly, from 7 pages to **408 pages** (`worldbankP505272-3c838d61...`).
- **Context**: The corpus contains a mix of academic ArXiv papers (high text density), annual reports (high graphical/tabular density), and technical tutorials.
- **Risk**: Large files can cause memory spikes or timeouts during embedding generation.
- **Mitigation**: Use batch processing and asynchronous node insertion in the ingestion pipeline.

### 4. Temporal Metadata
- **Observation**: Filenames consistently contain year markers (e.g., `2012`, `FY21`, `2023`).
- **Context**: Internal PDF metadata (Author, CreationDate) is often less reliable than the filename convention.
- **Mitigation**: The metadata extractor must prioritize regex-based year extraction from the filename to support the project's "Temporal Disambiguation" goal.

## Final Parsing Strategy
Based on these findings, the Phase 1 implementation will utilize:
1. **Parser**: `unstructured` (for table preservation).
2. **Chunker**: `SentenceWindowNodeParser` (LlamaIndex) with a filtering layer for low-text pages.
3. **Metadata**: Hybrid approach (Filename regex + Document summary).

---
*Generated: May 2026 | Pre-Phase 1 Audit Documentation*
