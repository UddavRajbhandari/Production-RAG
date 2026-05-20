# Phase 8.2: Cloud Infrastructure Migration

**Project 02 - Production-Grade RAG Pipeline**
**Document Version: 1.0 | Date: May 2026**

---

## Table of Contents

1. [Overview](#1-overview)
2. [Architecture](#2-architecture)
3. [Cloud Infrastructure Setup](#3-cloud-infrastructure-setup)
4. [Detection Logic](#4-detection-logic)
5. [Development vs Production Modes](#5-development-vs-production-modes)
6. [Implementation Tasks](#6-implementation-tasks)
7. [Files to Modify](#7-files-to-modify)
8. [Implementation Order](#8-implementation-order)
9. [Testing Strategy](#9-testing-strategy)
10. [Risk Mitigation](#10-risk-mitigation)

---

## 1. Overview

### Objectives

1. Migrate Qdrant to Qdrant Cloud (with native BM25 sparse vectors)
2. Migrate Postgres to Neon
3. Implement automatic detection (cloud vs local)
4. Support both development flexibility and production resilience

### Key Changes from Phase 8.1

| Component | Before | After |
|-----------|--------|-------|
| Qdrant | Local Docker | Qdrant Cloud (primary) + Docker (fallback) |
| BM25 | Local pickle file | Qdrant native (cloud) + pickle (local fallback) |
| Postgres | SQLite (dev) | Neon (production) + SQLite (fallback) |

---

## 2. Architecture

### Connection Priority

```
Qdrant Connection:
1. QDRANT_URL (cloud) → Qdrant Cloud, native BM25 support
2. QDRANT_HOST:PORT (Docker) → Local development
3. localhost:6333 default → Fallback

Postgres Connection:
1. DATABASE_URL (Neon) → Production
2. SQLite fallback → Local dev / outage

BM25 Strategy:
1. Qdrant native (cloud) → Fast, server-side scoring
2. Local pickle (no cloud) → Development mode
3. Rebuild from Postgres (outage) → Recovery fallback
```

### Development Mode

| Component | Storage | Location |
|-----------|---------|----------|
| Dense vectors | Qdrant Docker (localhost) | Local |
| Sparse BM25 | Local pickle file | Local |
| Metadata | SQLite | Local |

### Production Mode

| Component | Storage | Location |
|-----------|---------|----------|
| Dense vectors | Qdrant Cloud | Cloud |
| Sparse BM25 | Qdrant native (cloud) | Cloud |
| Metadata | Neon Postgres | Cloud |

---

## 3. Cloud Infrastructure Setup

### 3.1 Qdrant Cloud Setup

**Steps:**
1. Sign up at https://cloud.qdrant.io/
2. Create new cluster (choose region closest to users)
3. Enable **Cloud Inference** for native BM25 support
4. Generate API key

**Required Environment Variables:**
```
QDRANT_URL=https://xxxxxxx.cloud.qdrant.io
QDRANT_API_KEY=<your-api-key>
```

**Collection Configuration:**
```python
client.create_collection(
    collection_name="production_rag_v1",
    vectors_config={
        "dense": VectorParams(size=384, distance=Distance.COSINE)
    },
    sparse_vectors_config={
        "sparse-bm25": SparseVectorParams()
    },
)
```

### 3.2 Neon Postgres Setup

**Steps:**
1. Sign up at https://neon.tech/
2. Create new project
3. Copy connection string

**Required Environment Variable:**
```bash
DATABASE_URL=postgres://user:pass@host.region.neon.tech/rag?sslmode=require  # pragma: allowlist secret
```

---

## 4. Detection Logic

### Storage Mode Detection

```python
# src/storage/storage_factory.py

def detect_storage_mode() -> str:
    """Detect storage mode based on environment variables."""

    # Check Qdrant mode
    if os.getenv("QDRANT_URL"):
        qdrant_mode = "cloud"
    elif os.getenv("QDRANT_HOST"):
        qdrant_mode = "docker"
    else:
        qdrant_mode = "local"

    # Check Postgres mode
    if os.getenv("DATABASE_URL"):
        postgres_mode = "neon"
    else:
        postgres_mode = "sqlite"

    return f"{qdrant_mode}_{postgres_mode}"
```

### BM25 Mode Selection

```python
# src/storage/bm25_storage.py

def get_bm25_mode() -> str:
    """
    Determine BM25 storage mode:
    - 'qdrant_cloud': Use Qdrant native sparse vectors (production)
    - 'local_pickle': Use local pickle file (development)
    - 'rebuild': Rebuild from Postgres (outage recovery)
    """

    if os.getenv("QDRANT_URL"):
        return "qdrant_cloud"  # Preferred: fast, server-side
    else:
        return "local_pickle"  # Development fallback

def should_use_qdrant_bm25() -> bool:
    """Check if Qdrant Cloud with inference is available."""
    return bool(os.getenv("QDRANT_URL"))
```

---

## 5. Development vs Production Modes

### Development Mode (No Cloud Variables)

```bash
# .env.development
# QDRANT_URL=           # Commented out = local mode
# QDRANT_API_KEY=       # Commented out = local mode
# DATABASE_URL=        # Commented out = SQLite

QDRANT_HOST=localhost
QDRANT_PORT=6333
```

**Behavior:**
- Qdrant: Connects to local Docker container
- BM25: Uses local pickle file (`storage/bm25_index.pkl`)
- Postgres: Uses SQLite

### Development Mode (With Cloud)

```bash
# .env.cloud-dev
QDRANT_URL=https://xxxx.cloud.qdrant.io
QDRANT_API_KEY=xxx
DATABASE_URL=postgres://...neon.tech/rag?sslmode=require
```

**Behavior:**
- Qdrant: Connects to cloud with native BM25
- BM25: Uses Qdrant sparse vectors (server-side)
- Postgres: Connects to Neon

### Production Mode

```bash
# .env.production
QDRANT_URL=https://xxxx.cloud.qdrant.io
QDRANT_API_KEY=xxx
DATABASE_URL=postgres://...neon.tech/rag?sslmode=require
```

**Behavior:**
- Qdrant: Cloud with native BM25
- BM25: Qdrant sparse vectors
- Postgres: Neon
- All instances share the same cloud data

### Outage Recovery Mode

If Qdrant Cloud is unavailable in production:

```python
# Fallback: Rebuild BM25 from Postgres chunks
if should_use_qdrant_bm25():
    use_qdrant_sparse_search()
else:
    # Rebuild from Neon chunks
    chunks = neon_storage.get_all_chunks()
    bm25_storage.build_index(chunks)
```

---

## 6. Implementation Tasks

### Task 1: Update Settings Model
**File:** `src/api/models/models.py`

Add cloud-specific environment variables:
```python
class Settings(BaseSettings):
    # Qdrant Cloud
    qdrant_url: str | None = Field(default=None, alias="QDRANT_URL")
    qdrant_api_key: str = Field(default="", alias="QDRANT_API_KEY")

    # Neon/Postgres
    database_url: str | None = Field(default=None, alias="DATABASE_URL")
```

### Task 2: Update QdrantStorage for Cloud + Native BM25
**File:** `src/storage/qdrant_storage.py`

Modify `_connect()` method:
```python
def _connect(self, q_config: dict[str, Any]) -> QdrantClient:
    # Priority 1: Cloud URL
    if qdrant_url := os.getenv("QDRANT_URL"):
        api_key = os.getenv("QDRANT_API_KEY", "")
        client = QdrantClient(
            url=qdrant_url,
            api_key=api_key if api_key else None,
            cloud_inference=True  # Enable for native BM25
        )
        self.mode = "cloud"
        ...

    # Priority 2: Docker (existing)
    elif q_config.get("host"):
        ...
        self.mode = "docker"

    # Priority 3: Local path (existing)
    else:
        ...
        self.mode = "local"
```

Update collection creation for sparse vectors:
```python
def _ensure_collection(self) -> None:
    # Enable sparse vectors for native BM25
    self.client.create_collection(
        collection_name=self.collection_name,
        vectors_config={
            "dense": VectorParams(size=384, distance=Distance.COSINE)
        },
        sparse_vectors_config={
            "sparse-bm25": SparseVectorParams()
        } if self.mode == "cloud" else {},
    )
```

### Task 3: Create Storage Factory
**File:** `src/storage/storage_factory.py` (NEW)

Factory pattern for unified storage access:
```python
class StorageFactory:
    @staticmethod
    def create_qdrant() -> QdrantStorage:
        return QdrantStorage()

    @staticmethod
    def create_neon() -> NeonStorage:
        return NeonStorage()

    @staticmethod
    def create_bm25() -> BM25Storage:
        if should_use_qdrant_bm25():
            return QdrantSparseStorage()  # NEW: wraps Qdrant sparse
        else:
            return BM25Storage()  # Legacy: local pickle
```

### Task 4: Create Qdrant Sparse Storage
**File:** `src/storage/qdrant_sparse_storage.py` (NEW)

Wrapper for Qdrant native sparse search:
```python
class QdrantSparseStorage:
    """
    Qdrant native sparse vector storage for BM25.
    Uses server-side inference for BM25 scoring.
    """

    def __init__(self):
        self.qdrant = QdrantStorage()
        self.using = "sparse-bm25"
        self.model = "Qdrant/bm25"

    def upsert_with_bm25(self, nodes: list[TextNode]) -> None:
        """Upsert nodes with BM25 sparse vectors."""
        points = []
        for node in nodes:
            points.append(PointStruct(
                id=node.id_,
                vector={
                    "sparse-bm25": Document(
                        text=node.text,
                        model=self.model
                    )
                },
                payload=node.metadata
            ))
        self.qdrant.client.upsert(
            collection_name=self.qdrant.collection_name,
            points=points
        )

    def search(self, query: str, top_k: int = 10) -> list[TextNode]:
        """Search using BM25 sparse vectors."""
        results = self.qdrant.client.query_points(
            collection_name=self.qdrant.collection_name,
            query=Document(text=query, model=self.model),
            using=self.using,
            limit=top_k
        )
        return [self._point_to_node(r) for r in results]
```

### Task 5: Update Hybrid Search for Dual Mode
**File:** `src/retrieval/hybrid_search.py`

Support both BM25 modes:
```python
class HybridSearchRetriever:
    def __init__(self):
        # Storage detection
        if should_use_qdrant_bm25():
            self.sparse = QdrantSparseStorage()  # Cloud mode
        else:
            self.sparse = BM25Storage()  # Local mode
            self.sparse.load()

        self.dense = QdrantStorage()
        self.dense.connect()

    def sparse_search(self, query: str, top_k: int) -> list[TextNode]:
        if should_use_qdrant_bm25():
            return self.sparse.search(query, top_k)
        else:
            return self.sparse.search(query, top_k)
```

### Task 6: Update Ingest Endpoint
**File:** `src/api/routes/ingest.py`

Support both storage modes:
```python
@router.post("/api/v1/ingest")
async def ingest_document(request: IngestRequest):
    # ... chunking logic ...

    # Upsert to Qdrant (dense + sparse if cloud)
    if should_use_qdrant_bm25():
        sparse_storage = QdrantSparseStorage()
        sparse_storage.upsert_with_bm25(nodes)
    else:
        # Local mode: add to pickle
        bm25 = BM25Storage()
        bm25.load()
        bm25.add_nodes(nodes)  # NEW: incremental add
        bm25.save()

    # Save to Postgres
    neon_storage.insert_chunks(nodes)
```

### Task 7: Add Incremental BM25 Support
**File:** `src/storage/bm25_storage.py`

Add method for incremental indexing:
```python
class BM25Storage:
    def add_nodes(self, nodes: list[TextNode]) -> None:
        """
        Add new nodes to existing index incrementally.
        Rebuilds index with combined corpus.
        """
        self.nodes.extend(nodes)
        tokenized_corpus = [node.text.lower().split() for node in self.nodes]
        self.index = BM25Okapi(tokenized_corpus)
        logger.info("BM25 index updated with %d new nodes.", len(nodes))
```

### Task 8: Update settings.yaml
**File:** `config/settings.yaml`

Add cloud configuration placeholders:
```yaml
storage:
  qdrant:
    # Cloud (production) - override with env vars
    # qdrant_url: https://xxx.qdrant.cloud
    # api_key: ${QDRANT_API_KEY}

    # Local (development)
    host: localhost
    port: 6333
    collection_name: production_rag_v1
    vector_size: 384
    distance: Cosine
    use_chunker_suffix: true

    # Cloud-specific: enable sparse vectors
    enable_sparse_vectors: true

  postgres:
    # Use DATABASE_URL env var for Neon/Postgres
    schema_name: rag_pipeline
```

### Task 9: Update .env.example
**File:** `.env.example`

Add cloud environment variables:
```bash
# ===========================================
# CLOUD SERVICES (Production)
# ===========================================
# Uncomment to enable cloud services

# Qdrant Cloud Configuration
# QDRANT_URL=https://your-cluster.qdrant.cloud
# QDRANT_API_KEY=your_qdrant_api_key

# Neon/Postgres Configuration
# DATABASE_URL=postgres://user:pass@ep-xxx.region.aws.neon.tech/rag?sslmode=require  # pragma: allowlist secret

# ===========================================
# LOCAL DEVELOPMENT (Default when cloud vars commented)
# ===========================================
QDRANT_HOST=localhost
QDRANT_PORT=6333
```

### Task 10: Add Storage Mode Health Check
**File:** `src/api/routes/health.py`

Report connection mode:
```python
def _get_storage_mode() -> dict:
    """Get current storage mode configuration."""
    mode = detect_storage_mode()
    qdrant_mode, postgres_mode = mode.split("_")

    return {
        "qdrant": {
            "mode": qdrant_mode,
            "bm25": "qdrant_native" if qdrant_mode == "cloud" else "local_pickle"
        },
        "postgres": {
            "mode": postgres_mode
        }
    }
```

### Task 11: Add Neon Health Check
**File:** `src/api/routes/health.py`

Add PostgreSQL connectivity check:
```python
def _check_postgres() -> tuple[str, str]:
    """Check Neon/Postgres connection."""
    try:
        if os.getenv("DATABASE_URL"):
            from src.storage.neon_storage import NeonStorage
            storage = NeonStorage()
            session = storage.Session()
            session.execute(text("SELECT 1"))
            session.close()
            return "healthy", "Neon connected"
        else:
            return "healthy", "SQLite (local dev)"
    except Exception as e:
        return "unhealthy", str(e)
```

### Task 12: Update populate_storage.py
**File:** `scripts/populate_storage.py`

Support cloud mode:
```python
if __name__ == "__main__":
    # Detect mode
    use_cloud = bool(os.getenv("QDRANT_URL"))

    if use_cloud:
        # Cloud mode: populate Qdrant with native BM25
        sparse_storage = QdrantSparseStorage()
        for batch in batch_nodes(nodes, batch_size=100):
            sparse_storage.upsert_with_bm25(batch)
    else:
        # Local mode: populate pickle
        bm25 = BM25Storage()
        bm25.build_index(nodes)
        bm25.save()
```

---

## 7. Files to Modify

| File | Action | Priority |
|------|--------|----------|
| `src/api/models/models.py` | Add cloud env vars | High |
| `src/storage/qdrant_storage.py` | Add cloud support + sparse vectors | High |
| `src/storage/storage_factory.py` | NEW - Factory pattern | High |
| `src/storage/qdrant_sparse_storage.py` | NEW - Qdrant native BM25 | High |
| `src/retrieval/hybrid_search.py` | Support dual BM25 mode | High |
| `src/api/routes/ingest.py` | Support cloud ingest | High |
| `src/storage/bm25_storage.py` | Add incremental add | Medium |
| `src/api/routes/health.py` | Add mode detection | Medium |
| `config/settings.yaml` | Add cloud placeholders | High |
| `.env.example` | Add cloud env vars | High |
| `scripts/populate_storage.py` | Support cloud mode | Medium |

**Total files to modify:** 8
**New files:** 2

---

## 8. Implementation Order

```
1. Task 1: Update Settings model (1 file)
   └── verify: pydantic validation works

2. Task 2: Update QdrantStorage for cloud (1 file)
   └── verify: connects to Qdrant Cloud with env vars

3. Task 4: Create Qdrant Sparse Storage (NEW file)
   └── verify: can upsert and search with BM25

4. Task 3: Create Storage Factory (NEW file)
   └── verify: creates correct storage based on env

5. Task 5: Update Hybrid Search (1 file)
   └── verify: hybrid search works in both modes

6. Task 6: Update Ingest Endpoint (1 file)
   └── verify: ingest works in both modes

7. Task 7: Add incremental BM25 (1 file)
   └── verify: can add nodes to existing index

8. Task 8: Update settings.yaml (1 file)
   └── verify: cloud placeholders added

9. Task 9: Update .env.example (1 file)
   └── verify: env vars documented

10. Task 10: Update health check (1 file)
    └── verify: shows correct storage mode

11. Task 11: Add Neon health check (1 file)
    └── verify: reports postgres status

12. Task 12: Update populate_storage.py (1 file)
    └── verify: can populate in both modes
```

---

## 9. Testing Strategy

### Unit Tests

| Test | File | Coverage |
|------|------|----------|
| Storage mode detection | `tests/unit/test_storage_factory.py` | NEW |
| Qdrant sparse upsert | `tests/unit/test_qdrant_sparse.py` | NEW |
| Qdrant sparse search | `tests/unit/test_qdrant_sparse.py` | NEW |
| Incremental BM25 add | `tests/unit/test_bm25_storage.py` | NEW |
| Cloud vs local detection | `tests/unit/test_storage_factory.py` | NEW |

### Integration Tests

| Test | Command | Mode |
|------|---------|------|
| Local Docker still works | `docker-compose up -d qdrant` | Local |
| Cloud connection | Set `QDRANT_URL` env var | Cloud |
| Neon connection | Set `DATABASE_URL` env var | Cloud |
| Health endpoint | `GET /api/v1/health` | Both |

### Test Commands

```bash
# Test local mode (no cloud vars)
pytest tests/unit/test_storage_factory.py -v

# Test cloud mode (with env vars)
QDRANT_URL=https://xxx.qdrant.io \
QDRANT_API_KEY=xxx \
DATABASE_URL=postgres://... \
pytest tests/integration/ -v
```

---

## 10. Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Breaking local dev | High | Keep fallbacks - cloud is opt-in via env vars |
| Connection string errors | Medium | Log connection mode at startup |
| Qdrant Cloud outage | Medium | Fallback to rebuild from Postgres chunks |
| BM25 index rebuild delay | Low | Cache pickled version; rebuild only when needed |
| API key exposure | High | Use detect-secrets pre-commit (already in place) |
| SSL/TLS issues with Neon | Low | `sslmode=require` in connection string |
| Version mismatch (cloud inference) | Medium | Check Qdrant Cloud version >= 1.14 |

### Startup Flow

```
App Start
    │
    ▼
Detect storage mode
    │
    ├─► Cloud mode (QDRANT_URL set)
    │       │
    │       ▼
    │   Connect to Qdrant Cloud
    │       │
    │       ▼
    │   Use native sparse vectors
    │
    └─► Local mode (no QDRANT_URL)
            │
            ▼
        Connect to Docker Qdrant
            │
            ▼
        Load local pickle
```

### Outage Recovery Flow

```
Qdrant Cloud Unavailable
    │
    ▼
Detect failure
    │
    ▼
Fallback: Rebuild BM25 from Postgres
    │
    ▼
Load chunks from Neon
    │
    ▼
Rebuild local BM25 index
    │
    ▼
Serve with degraded performance
```

---

## Appendix: Environment Variable Reference

| Variable | Description | Required For |
|----------|-------------|--------------|
| `QDRANT_URL` | Qdrant Cloud cluster URL | Cloud mode |
| `QDRANT_API_KEY` | Qdrant Cloud API key | Cloud mode |
| `DATABASE_URL` | Neon Postgres connection string | Cloud mode |
| `QDRANT_HOST` | Qdrant Docker host | Local mode |
| `QDRANT_PORT` | Qdrant Docker port | Local mode |

---

## Appendix: Qdrant Cloud Inference

**Requirements for native BM25:**
1. Qdrant Cloud cluster with version >= 1.14.0
2. Cloud Inference enabled (via Qdrant Cloud Console)
3. `cloud_inference=True` in Python client

**Usage:**
```python
client = QdrantClient(
    url=os.getenv("QDRANT_URL"),
    api_key=os.getenv("QDRANT_API_KEY"),
    cloud_inference=True
)

# Upsert with BM25
client.upsert(
    collection_name="collection",
    points=[models.PointStruct(
        id=1,
        vector={
            "sparse-bm25": models.Document(
                text="Your text here",
                model="Qdrant/bm25"
            )
        }
    )]
)
```

**Free Tier:** Qdrant Cloud offers unlimited BM25 tokens for paid clusters. Development use is free.

---

## Definition of Done

- [ ] All files modified as per implementation order
- [ ] Unit tests created and passing
- [ ] Integration tests pass for both modes
- [ ] Ruff passes
- [ ] Mypy passes
- [ ] Pre-commit passes
- [ ] Documentation updated
- [ ] Cloud infrastructure verified working
