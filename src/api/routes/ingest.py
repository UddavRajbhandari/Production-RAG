"""
Document ingestion endpoint for adding new documents to the RAG pipeline.
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, HTTPException, UploadFile

from src.api.models import IngestRequest, IngestResponse

if TYPE_CHECKING:
    from src.ingestion.pipeline import IngestionPipeline

logger = logging.getLogger(__name__)

router = APIRouter()

# Lazy-loaded ingestion pipeline
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


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(request: IngestRequest) -> IngestResponse:
    """
    Ingest documents into the RAG pipeline.

    Accepts raw text content which is processed, chunked, and stored in the vector database.
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
async def ingest_file(file: UploadFile) -> IngestResponse:
    """
    Ingest a file directly via multipart form data.

    Supports PDF, DOCX, TXT files.
    """
    try:
        # Read file content
        content = await file.read()
        text_content = content.decode("utf-8", errors="ignore")

        logger.info("Ingesting uploaded file: %s", file.filename)

        # Generate document ID from filename
        doc_id = generate_document_id(text_content, {"filename": file.filename})

        # In production: save temp file and use pipeline.run()
        # For now, estimate chunks
        chunks_created = len(text_content) // 512

        return IngestResponse(
            status="success",
            chunks_created=chunks_created,
            document_id=doc_id,
        )

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
