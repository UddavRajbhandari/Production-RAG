# Production RAG — Operational Runbook

## 1. Startup Sequence

```bash
# 1. Start Qdrant (if using local Docker mode)
docker-compose up -d qdrant

# 2. Verify Qdrant is healthy
curl http://localhost:6333/health

# 3. Start the API
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# 4. Verify API is healthy
curl http://localhost:8000/api/v1/health

# 5. Start the frontend (if running locally)
cd frontend && npm run dev
```

## 2. Shutdown Sequence

```bash
# 1. Stop the API (Ctrl+C)

# 2. Stop Qdrant (if running locally)
docker-compose down

# 3. Stop the frontend (Ctrl+C)
```

## 3. Health Check Interpretation

| Component | Healthy | Degraded | Unhealthy |
|-----------|---------|----------|-----------|
| `api` | Always "healthy" if running | N/A | N/A |
| `qdrant` | `healthy: Connected (cloud/local mode)` | N/A | `unhealthy: <error>` |
| `bm25` | `healthy: Qdrant native BM25 (cloud)` or `healthy: Local pickle (N nodes)` | N/A | `unhealthy: Index not found` or `unhealthy: <error>` |
| `postgres` | `healthy: Neon connected` or `healthy: SQLite (local dev)` | N/A | `unhealthy: <error>` |
| `llm` | `healthy: Available: OPENROUTER_API_KEY` | `degraded: No API keys configured` | N/A |

Full health: `GET /api/v1/health`

## 4. Qdrant Recovery

### Symptom: Health check shows Qdrant unhealthy

```bash
# Check if container is running
docker ps | findstr qdrant

# If not running, restart it
docker-compose restart qdrant

# Wait for it to be ready
curl http://localhost:6333/health

# Restart the API to reconnect
# (Restart the uvicorn process)
```

### Symptom: Collection missing or corrupted

```bash
# Check collections
python -c "from src.storage.qdrant_storage import QdrantStorage; s=QdrantStorage(); print(s.client.get_collections())"

# Re-populate from processed chunks
python -c "from scripts.populate_storage import main; main()"
```

## 5. BM25 Recovery

### Symptom: BM25 health check shows "Index not found"

**Local mode:**
```bash
# Rebuild BM25 index from processed chunks
python -c "
from src.storage.bm25_storage import BM25Storage
from src.ingestion.pipeline import load_ingested_nodes
nodes = load_ingested_nodes()
bm25 = BM25Storage()
bm25.build_index(nodes)
bm25.save()
print(f'BM25 rebuilt: {len(nodes)} nodes')
"
```

**Cloud mode:**
```bash
# BM25 is native to Qdrant Cloud — check Qdrant connection instead
curl http://localhost:8000/api/v1/health
```

## 6. LLM Fallback

### Symptom: 503 error "No LLM available"

**Check 1: Is Ollama running?**
```bash
curl http://localhost:11434/api/tags
# If not running: ollama serve
```

**Check 2: Is an API key set?**
```bash
# Check if OPENROUTER_API_KEY is set
python -c "import os; print('Set' if os.getenv('OPENROUTER_API_KEY') else 'Not set')"
```

**Check 3: Health endpoint**
```bash
curl http://localhost:8000/api/v1/health | python -m json.tool
# Look for "llm" field
```

### LLM Provider Priority
1. User-provided API key (per-request, from frontend)
2. `OPENROUTER_API_KEY` env var
3. `OPENAI_API_KEY` env var
4. `GROQ_API_KEY` env var
5. Ollama (local)

## 7. Rollback Procedure

### Code Rollback
```bash
# Revert to previous commit
git revert HEAD --no-edit
git push origin main

# Or rollback to a specific version
git log --oneline -10
git revert <commit-hash>
git push origin main
```

### Data Rollback (re-populate storage)
```bash
# Re-populate all three storage backends
python scripts/populate_storage.py
```

### Full Reset
```bash
# 1. Stop services
docker-compose down

# 2. Clear volumes
docker volume rm production-rag_qdrant_data

# 3. Clear local storage
Remove-Item -Recurse -Force storage/bm25_index*.pkl
Remove-Item -Recurse -Force storage/metadata*.db

# 4. Restart and re-populate
docker-compose up -d
python scripts/populate_storage.py
```

## 8. Data Re-ingestion

Re-run the full ingestion pipeline to update all storage backends:

```bash
# For structure-aware chunker (default)
python -c "
from src.ingestion.pipeline import IngestionPipeline
pipeline = IngestionPipeline()
pipeline.run_all()
print('Ingestion complete')
"

# Verify
curl http://localhost:8000/api/v1/metadata/stats
```

## 9. Monitoring

| URL | What it shows |
|-----|---------------|
| `GET /api/v1/health` | Component health status |
| `GET /api/v1/health/ready` | Kubernetes-style readiness |
| `GET /api/v1/health/live` | Kubernetes-style liveness |
| `GET /api/v1/metrics` | Prometheus metrics (request count, latency, RAGAS scores) |

## 10. Common Issues

| Issue | Likely Cause | Fix |
|-------|-------------|-----|
| `ModuleNotFoundError` | Missing dependency | `pip install -r requirements.txt` |
| Qdrant connection refused | Qdrant not running | `docker-compose up -d qdrant` |
| BM25 index not found | Storage not populated | Run populate script |
| 503 on query | No LLM available | Set API key or start Ollama |
| Slow responses | CPU inference on Ollama | Use OpenRouter API key instead |
| Rate limit errors (429) | Too many requests | Wait 1 minute or reduce concurrency |
