# Phase 8: Production RAG API Documentation

**Project**: Production-Grade RAG Pipeline
**Version**: 1.0
**Date**: May 2026

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Storage Layers](#3-storage-layers)
4. [API Endpoints](#4-api-endpoints)
5. [Search Pipeline](#5-search-pipeline)
6. [Usage Guide](#6-usage-guide)
7. [Data Flow](#7-data-flow)
8. [Testing](#8-testing)

---

## 1. Overview

The Production RAG API provides a RESTful interface for querying documents using a hybrid retrieval system that combines:

- **Dense Vector Search** (Qdrant) - Semantic similarity
- **Sparse Keyword Search** (BM25) - Full-text keyword matching
- **Relational Metadata** (Neon/SQLite) - Structured filtering

### System Components

```
┌─────────────────────────────────────────────────────────────────────┐
│                         CLIENT (Swagger UI / API)                  │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         FASTAPI APPLICATION                         │
│                                                                       │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │
│   │  Health     │  │   Query     │  │   Ingest    │               │
│   │  Endpoints  │  │  Endpoints  │  │  Endpoints   │               │
│   └─────────────┘  └─────────────┘  └─────────────┘               │
│                                                                       │
│   ┌─────────────┐                                                  │
│   │  Metadata   │                                                  │
│   │  Endpoints  │                                                  │
│   └─────────────┘                                                  │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    REASONING PIPELINE (LangGraph)                   │
│                                                                       │
│   Planner → Router → Retrieval Agent → Summarization Agent          │
│              → Gatekeeper → Auditor → Strategist                    │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
                                  ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    HYBRID RETRIEVER                                  │
│            (Qdrant + BM25 + Reciprocal Rank Fusion)               │
└─────────────────────────────────┬───────────────────────────────────┘
                                  │
              ┌───────────────────┴───────────────────┐
              ▼                                       ▼
┌─────────────────────────┐           ┌─────────────────────────┐
│      QDRANT             │           │         BM25            │
│   (Vector Database)    │           │   (Keyword Index)        │
│     Port: 6333          │           │   In-memory              │
└─────────────────────────┘           └─────────────────────────┘

┌─────────────────────────┐
│         NEON            │
│    (SQLite/Postgres)    │
│   Relational Metadata   │
└─────────────────────────┘
```

---

## 2. Architecture

### Technology Stack

| Component | Technology | Port |
|-----------|------------|------|
| API Framework | FastAPI | 8000 |
| Vector Store | Qdrant (Docker) | 6333 |
| Keyword Index | rank_bm25 (in-memory) | - |
| Relational DB | SQLite (local) / Neon (cloud) | - |
| Reasoning Engine | LangGraph StateGraph | - |
| Embedding Model | sentence-transformers/all-MiniLM-L6-v2 | - |
| Reranking | cross-encoder/ms-marco-MiniLM-L-6-v2 | - |

### Data Statistics

| Metric | Value |
|--------|-------|
| Total Chunks | 2,717 |
| Vector Dimensions | 384 |
| Departments | Academic, Financial, General, Technical |
| Year Range | 2012-2023 |

---

## 3. Storage Layers

### 3.1 Qdrant (Dense Vectors)

**Purpose**: Semantic similarity search using vector embeddings

**Configuration**:
```yaml
storage:
  qdrant:
    host: localhost
    port: 6333
    collection_name: production_rag_v1_structure_aware
    vector_size: 384
    distance: Cosine
```

**How it works**:
1. Query text is embedded using SentenceTransformer
2. 384-dimensional vector is created
3. Cosine similarity is calculated against all stored vectors
4. Top-k results returned

### 3.2 BM25 (Sparse Keywords)

**Purpose**: Full-text keyword search using Okapi BM25

**Configuration**:
```yaml
storage:
  bm25:
    persist_path: storage/bm25_index_structure_aware.pkl
    use_chunker_suffix: true
```

**How it works**:
1. Query is tokenized (lowercase, split by whitespace)
2. BM25 scoring formula calculates relevance
3. Top-k results returned

### 3.3 Neon/SQLite (Relational Metadata)

**Purpose**: Structured metadata storage for filtering

**Schema**:
```python
class ChunkMetadata:
    id: String (primary key)
    text: Text
    source_file: String (indexed)
    page_number: Integer
    section_heading: String
    domain_tag: String (indexed)
    date: String (indexed)  # year
    department: String (indexed)
    version: String
    full_metadata: JSON
    created_at: DateTime
```

---

## 4. API Endpoints

### 4.1 Health Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/health` | GET | Full health check (Qdrant, BM25, LLM) |
| `/api/v1/health/ready` | GET | Readiness check for deployment |
| `/api/v1/health/live` | GET | Liveness check (is service running?) |

### 4.2 Query Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/query` | POST | Full RAG pipeline with LLM |
| `/api/v1/query/stream` | POST | Streaming response (SSE) |
| `/api/v1/query/retrieve` | POST | Retrieval only (no LLM) |

**Query Request**:
```json
{
  "query": "What is this project about?",
  "stream": false,
  "include_sources": true
}
```

**Query Response**:
```json
{
  "answer": "Based on the documents...",
  "sources": [
    {
      "text": "...",
      "score": 0.0323,
      "source": "hybrid"
    }
  ],
  "latency_ms": 45000.0,
  "validation_passed": true
}
```

### 4.3 Ingestion Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/ingest` | POST | Ingest document by file path |
| `/api/v1/ingest/file` | POST | Ingest via file upload |
| `/api/v1/ingest/batch` | POST | Batch ingest multiple files |

### 4.4 Metadata Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/metadata/query` | POST | Query with filters |
| `/api/v1/metadata/stats` | GET | Get statistics |
| `/api/v1/metadata/departments` | GET | List departments |

**Metadata Query Request**:
```json
{
  "department": "Financial",
  "year": "2023",
  "offset": 0,
  "limit": 50
}
```

**Metadata Stats Response**:
```json
{
  "total_chunks": 2711,
  "by_department": {
    "Academic": 343,
    "Financial": 1358,
    "General": 385,
    "Technical": 625
  },
  "by_year": {
    "2012": 116,
    "2013": 118,
    "2014": 56
  },
  "by_domain": {}
}
```

---

## 5. Search Pipeline

### How Search Works

```
USER QUERY: "World Bank annual report"
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│           PARALLEL SEARCH (Qdrant + BM25)                  │
└─────────────────────────────────────────────────────────────┘
       │                          │
       ▼                          ▼
┌───────────────────┐      ┌───────────────────┐
│     QDRANT        │      │       BM25        │
│  (Dense Search)   │      │  (Sparse Search)  │
│                   │      │                    │
│ 1. Embed query   │      │ 1. Tokenize query │
│ 2. Vector search │      │ 2. BM25 scoring   │
│ 3. Top 20 results│      │ 3. Top 20 results │
└────────┬─────────┘      └────────┬─────────┘
         │                          │
         └──────────┬──────────────┘
                    ▼
┌─────────────────────────────────────────────────────────────┐
│          RECIPROCAL RANK FUSION (RRF k=60)                  │
│                                                             │
│  Formula: score = Σ 1 / (k + rank)                        │
│                                                             │
│  Example:                                                  │
│  - Doc A: Qdrant rank 1 + BM25 rank 2                    │
│    → 1/(60+1) + 1/(60+2) = 0.0164 + 0.0159 = 0.0323     │
│                                                             │
│  - Doc B: Qdrant rank 5 only                               │
│    → 1/(60+5) = 0.0154                                    │
└─────────────────────────────────────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────┐
│                  TOP 15 RESULTS                             │
│           (Sorted by combined RRF score)                    │
└─────────────────────────────────────────────────────────────┘
```

### Why RRF?

| Approach | Pros | Cons |
|-----------|------|------|
| **RRF** | Works without training, handles different scoring scales | May miss exact matches |
| **Linear** | Simple | Requires normalized scores |
| **Learning-to-rank** | Best accuracy | Requires training data |

---

## 6. Usage Guide

### Starting the API

```bash
# 1. Start Qdrant (if not running)
docker-compose up -d qdrant

# 2. Start the API
cd D:\Production RAG
python -m uvicorn src.api.main:app --reload --port 8000
```

### Accessing Swagger UI

- **URL**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Testing the Endpoints

#### 1. Health Check
```bash
curl http://localhost:8000/api/v1/health
```

#### 2. Retrieval Only (No LLM)
```bash
curl -X POST http://localhost:8000/api/v1/query/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "World Bank annual report", "stream": false, "include_sources": true}'
```

#### 3. Full RAG Query (With LLM)
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is this project about?", "stream": false, "include_sources": true}'
```

#### 4. Metadata Query
```bash
curl -X POST http://localhost:8000/api/v1/metadata/query \
  -H "Content-Type: application/json" \
  -d '{"department": "Financial"}'
```

#### 5. Get Statistics
```bash
curl http://localhost:8000/api/v1/metadata/stats
```

---

## 7. Data Flow

### Full RAG Query Flow

```
┌──────────────┐
│   USER      │
│   QUERY     │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│                    RETRIEVAL LAYER                          │
│                                                              │
│  ┌────────────────┐    ┌────────────────┐                    │
│  │   QDRANT      │    │     BM25       │                    │
│  │  (Vectors)    │    │  (Keywords)    │                    │
│  │  2,717 pts   │    │ 2,717 nodes   │                    │
│  └───────┬────────┘    └───────┬────────┘                    │
│          │                     │                             │
│          └─────────┬───────────┘                             │
│                    ▼                                         │
│          ┌─────────────────┐                                 │
│          │  RRF FUSION     │                                 │
│          │    (k=60)       │                                 │
│          └────────┬────────┘                                 │
│                   ▼                                          │
│          ┌─────────────────┐                                 │
│          │   TOP 15 CHUNKS │ ← Retrieved Context             │
│          └─────────────────┘                                 │
└──────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────┐
│              REASONING PIPELINE (LangGraph)                 │
│                                                              │
│  ┌─────────┐  ┌─────────┐  ┌─────────────┐  ┌──────────┐ │
│  │ Planner  │→ │ Router  │→ │ Retrieval   │→ │ Summariz │ │
│  │          │  │          │  │   Agent     │  │  er      │ │
│  └─────────┘  └─────────┘  └─────────────┘  └──────────┘ │
│                                                      │     │
│  ┌──────────┐  ┌────────┐  ┌──────────┐  ┌────────┘     │
│  │Calculate │→ │Gatekeep│→ │ Auditor  │→ │ Strategist│ │
│  │  Agent   │  │        │  │          │  │           │ │
│  └──────────┘  └────────┘  └──────────┘  └────────────┘ │
└──────────────────────────────────────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────────────────────────┐
│                    LLM RESPONSE                              │
│                                                              │
│  {                                                           │
│    "answer": "Based on the retrieved context...",           │
│    "sources": [...],                                        │
│    "latency_ms": 45000,                                     │
│    "validation_passed": true                                 │
│  }                                                           │
└──────────────────────────────────────────────────────────────┘
```

### Ingestion Flow

```
┌──────────────┐
│   RAW FILE   │
│  (PDF/DOCX)  │
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│                 INGESTION PIPELINE                          │
│                                                              │
│  ┌─────────┐    ┌─────────────┐    ┌──────────┐           │
│  │ Parser  │ →  │  Structure  │ →  │  Chunker  │           │
│  │          │    │  Analyzer   │    │          │           │
│  └─────────┘    └─────────────┘    └──────────┘           │
│                                               │            │
│                                               ▼            │
│                                    ┌────────────────────┐ │
│                                    │  METADATA EXTRACTION │ │
│                                    │  (Summary, Keyword,  │ │
│                                    │   Questions)         │ │
│                                    └────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
                   │
       ┌───────────┴───────────┐
       ▼                       ▼
┌───────────────┐      ┌───────────────┐
│    QDRANT     │      │     BM25      │
│  (Vectors)    │      │  (Keywords)   │
│               │      │               │
│ Embed + Store│      │ Build Index   │
└───────────────┘      └───────────────┘

┌───────────────┐
│    NEON      │
│ (Metadata)   │
│              │
│ Store in DB  │
└───────────────┘
```

---

## 8. Testing

### Prerequisites

1. Qdrant running: `docker-compose up -d qdrant`
2. Storage populated (2,717 chunks)
3. API started: `python -m uvicorn src.api.main:app --port 8000`

### Test Checklist

| Test | Endpoint | Expected Result |
|------|----------|-----------------|
| Health | `GET /api/v1/health` | All components "healthy" |
| Stats | `GET /api/v1/metadata/stats` | Total: 2,717 chunks |
| Departments | `GET /api/v1/metadata/departments` | 4 departments |
| Retrieve | `POST /api/v1/query/retrieve` | 15 results with scores |
| Full Query | `POST /api/v1/query` | Answer with sources |

### Example Test Query

```json
// Request to /api/v1/query/retrieve
{
  "query": "World Bank annual report",
  "stream": false,
  "include_sources": true
}

// Expected response
{
  "query": "World Bank annual report",
  "results": [
    {
      "text": "This annual report, which covers the period...",
      "score": 0.0323,
      "source": "hybrid",
      "metadata": {
        "department": "Financial",
        "source_file": "annual-report-2023.pdf"
      }
    }
  ],
  "count": 15
}
```

---

## Appendix: Configuration

### Environment Variables

```bash
# API
API_HOST=0.0.0.0
API_PORT=8000

# Storage
QDRANT_HOST=localhost
QDRANT_PORT=6333

# LLM (for full queries)
OPENROUTER_API_KEY=your_key_here
# OR
OPENAI_API_KEY=your_key_here
```

### File Locations

| File | Path |
|------|------|
| API Code | `src/api/` |
| Configuration | `config/settings.yaml` |
| Raw Data | `data/raw/` |
| Processed Chunks | `data/processed/chunks/` |
| BM25 Index | `storage/bm25_index_structure_aware.pkl` |
| Qdrant Data | Docker volume |
| Metadata DB | `storage/metadata_structure_aware.db` |

---

*Document Version 1.0 | Created May 2026*
