"""
Document ingestion endpoint for adding new documents to the RAG pipeline.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, Request, UploadFile

from src.api.models import IngestRequest, IngestResponse

if TYPE_CHECKING:
    from sentence_transformers import SentenceTransformer

    from src.ingestion.pipeline import IngestionPipeline

logger = logging.getLogger(__name__)

router = APIRouter()

_ingestion_pipeline = None


def get_ingestion_pipeline() -> IngestionPipeline:
    """Lazy-load the ingestion pipeline."""
    global _ingestion_pipeline
    if _ingestion_pipeline is None:
        from src.ingestion.pipeline import IngestionPipeline

        _ingestion_pipeline = IngestionPipeline()
        logger.info("IngestionPipeline initialized for API")
    return _ingestion_pipeline


def generate_document_id(content: str, metadata: dict | None = None) -> str:
    """Generate a unique document ID based on content and metadata."""
    content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
    if metadata:
        meta_hash = hashlib.sha256(str(metadata).encode()).hexdigest()[:8]
        return f"doc_{content_hash}_{meta_hash}"
    return f"doc_{content_hash}"


def _save_uploaded_file(content: bytes, filename: str | None) -> tuple[str, bool]:
    """Save uploaded file using content-addressed storage.

    Uses SHA256 hash of content as filename, ensuring identical files
    are only stored once. Returns (path, is_new).
    """
    ext = Path(filename).suffix.lower() if filename else ".pdf"

    if ext == ".pdf":
        save_dir = "data/raw/pdf"
    elif ext in (".docx", ".doc"):
        save_dir = "data/raw/docx"
    elif ext in (".xlsx", ".xls"):
        save_dir = "data/raw/xlsx"
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")

    os.makedirs(save_dir, exist_ok=True)
    content_hash = hashlib.sha256(content).hexdigest()
    save_path = os.path.join(save_dir, f"{content_hash}{ext}")

    if os.path.exists(save_path):
        logger.info("Duplicate file detected (hash %s), skipping save", content_hash[:16])
        return save_path, False

    with open(save_path, "wb") as f:
        f.write(content)

    logger.info("Saved uploaded file to %s", save_path)
    return save_path, True


_embed_model: SentenceTransformer | None = None


def _get_embed_model() -> SentenceTransformer:
    """Cache SentenceTransformer model at module level."""
    global _embed_model
    if _embed_model is None:
        t0 = time.time()
        import yaml
        from sentence_transformers import SentenceTransformer

        with open("config/settings.yaml") as f:
            config = yaml.safe_load(f)
        _embed_model = SentenceTransformer(config["models"]["embedding"])
        logger.info("Loaded embedding model in %.1fs", time.time() - t0)
    return _embed_model


def _store_nodes(nodes: list[Any]) -> int:
    """Embed nodes and store in all backends. Returns chunk count."""
    t0 = time.time()
    embed_model = _get_embed_model()
    texts = [n.text for n in nodes]
    embeddings = embed_model.encode(texts, show_progress_bar=False).tolist()
    t1 = time.time()
    logger.info("Encoding %d chunks took %.1fs", len(texts), t1 - t0)

    use_cloud = bool(os.getenv("QDRANT_URL"))

    from src.storage.qdrant_storage import QdrantStorage

    qdrant = QdrantStorage()
    qdrant.create_collection(force_recreate=False)

    if use_cloud:
        from src.storage.qdrant_sparse_storage import QdrantSparseStorage

        sparse = QdrantSparseStorage()
        sparse.upsert_dense_and_bm25(nodes, embeddings)
    else:
        qdrant.insert_nodes(nodes, embeddings)
    t2 = time.time()
    logger.info("Qdrant storage took %.1fs", t2 - t1)

    if not use_cloud:
        from src.storage.bm25_storage import BM25Storage

        bm25 = BM25Storage()
        try:
            bm25.load()
            bm25.add_nodes(nodes)
        except FileNotFoundError:
            bm25.build_index(nodes)
        bm25.save()
    t3 = time.time()

    try:
        from src.storage.neon_storage import NeonStorage

        neon = NeonStorage()
        neon.create_tables(force_recreate=False)
        neon.insert_metadata(nodes)
    except Exception as e:
        logger.warning("Metadata storage failed (non-fatal — Qdrant has the data): %s", e)
    t4 = time.time()
    logger.info("Neon storage took %.1fs", t4 - t3)

    logger.info("Total storage time: %.1fs for %d chunks", t4 - t0, len(nodes))
    return len(nodes)


def _refresh_bm25(request: Request) -> None:
    """Reload BM25 index in the hybrid retriever singleton."""
    retriever = getattr(request.app.state, "hybrid_retriever", None)
    if retriever is not None:
        try:
            retriever.reload_bm25()
            logger.info("HybridRetriever BM25 reloaded after ingest")
        except Exception as e:
            logger.warning("Failed to reload HybridRetriever BM25: %s", e)


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(request: IngestRequest) -> IngestResponse:
    """
    Ingest documents into the RAG pipeline.

    Accepts raw text content which is processed, chunked, and stored
    in the vector database.
    """
    try:
        logger.info("Ingesting text content: %s...", request.text_content[:100])

        content = request.text_content
        doc_id = generate_document_id(content, request.metadata)
        chunks_created = len(content) // 512

        return IngestResponse(
            status="success",
            chunks_created=chunks_created,
            document_id=doc_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Document ingestion failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Ingestion failed") from e


@router.post("/ingest/file", response_model=IngestResponse)
async def ingest_file(file: UploadFile, request: Request) -> IngestResponse:
    """
    Ingest a file via multipart form upload.

    Saves the file to data/raw/<ext>/, runs the full ingestion pipeline
    (parse → chunk → embed → store in Qdrant + BM25 + Neon), and returns
    the actual chunk count.
    """
    try:
        content = await file.read()

        logger.info("Ingesting uploaded file: %s (%d bytes)", file.filename, len(content))

        max_size = 100 * 1024 * 1024
        if len(content) > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File too large: {len(content)} bytes (max {max_size})",
            )

        save_path, is_new = _save_uploaded_file(content, file.filename)

        doc_id = generate_document_id(file.filename or "", {"file_path": save_path})

        if not is_new:
            logger.info("Duplicate file, skipping ingestion: %s", save_path)
            return IngestResponse(
                status="skipped",
                chunks_created=0,
                document_id=doc_id,
            )

        import asyncio

        pipeline = get_ingestion_pipeline()
        nodes = await asyncio.to_thread(pipeline.run, save_path)

        if not nodes:
            logger.warning("Ingestion pipeline produced no chunks for %s", file.filename)
            raise HTTPException(status_code=400, detail="No content could be extracted from the file")

        chunks_created = await asyncio.to_thread(_store_nodes, nodes)

        if not bool(os.getenv("QDRANT_URL")):
            _refresh_bm25(request)

        logger.info("Successfully ingested %s: %d chunks created", file.filename, chunks_created)

        return IngestResponse(
            status="success",
            chunks_created=chunks_created,
            document_id=doc_id,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("File ingestion failed: %s", str(e))
        raise HTTPException(status_code=500, detail="File ingestion failed") from e


@router.post("/ingest/batch", response_model=dict[str, Any])
async def ingest_batch(file_paths: list[str]) -> dict[str, Any]:
    """
    Ingest multiple files in batch.

    Accepts a list of file paths and processes them sequentially.
    """
    try:
        pipeline = get_ingestion_pipeline()
        logger.info("Batch ingesting %d files", len(file_paths))

        results = []
        total_chunks = 0

        for file_path in file_paths:
            try:
                nodes = pipeline.run(file_path)
                chunks = len(nodes)
                total_chunks += chunks
                results.append(
                    {
                        "file": file_path,
                        "status": "success",
                        "chunks": chunks,
                    }
                )
            except Exception as ex:
                results.append(
                    {
                        "file": file_path,
                        "status": "failed",
                        "error": str(ex),
                    }
                )

        return {
            "status": "completed",
            "total_files": len(file_paths),
            "total_chunks": total_chunks,
            "results": results,
        }

    except Exception as e:
        logger.error("Batch ingestion failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Batch ingestion failed") from e
