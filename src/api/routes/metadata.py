"""
Metadata query endpoint for relational database queries.
Provides filtering and search by metadata fields.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, cast

from fastapi import APIRouter, HTTPException

from src.api.models import (
    MetadataChunkResponse,
    MetadataQueryRequest,
    MetadataQueryResponse,
)

if TYPE_CHECKING:
    from src.storage.neon_storage import NeonStorage

logger = logging.getLogger(__name__)

router = APIRouter()


def get_neon_storage() -> NeonStorage:
    """Lazy-load the Neon storage."""
    from src.storage.neon_storage import NeonStorage

    return NeonStorage()


@router.post("/metadata/query", response_model=MetadataQueryResponse)
async def query_metadata(request: MetadataQueryRequest) -> MetadataQueryResponse:
    """
    Query the relational metadata database.

    Supports filtering by:
    - department (Financial, Academic, Technical, General)
    - year/date
    - source_file
    - domain_tag
    - section_heading
    """
    try:
        neon = get_neon_storage()
        session = neon.Session()

        # Build query based on filters
        from sqlalchemy import and_, func, select

        from src.storage.neon_storage import ChunkMetadata

        # Base count query
        base_filter = []
        if request.department:
            base_filter.append(ChunkMetadata.department == request.department)
        if request.year:
            base_filter.append(ChunkMetadata.date == request.year)
        if request.source_file:
            base_filter.append(ChunkMetadata.source_file.like(f"%{request.source_file}%"))
        if request.domain_tag:
            base_filter.append(ChunkMetadata.domain_tag == request.domain_tag)

        # Get total count
        count_query = select(func.count(ChunkMetadata.id))
        if base_filter:
            count_query = count_query.where(and_(*base_filter))

        total = session.execute(count_query).scalar()

        # Get paginated results
        select_query = select(ChunkMetadata)
        if base_filter:
            select_query = select_query.where(and_(*base_filter))

        # Apply offset and limit
        select_query = select_query.offset(request.offset or 0).limit(request.limit or 50)

        results = session.execute(select_query).scalars().all()

        # Format response
        chunks: list[MetadataChunkResponse] = []
        for r in results:
            chunks.append(
                MetadataChunkResponse(
                    id=cast(str, r.id),
                    text=cast(str, r.text)[:200],  # Truncate for response
                    source_file=cast(str, r.source_file),
                    department=cast(str, r.department),
                    year=cast(str, r.date),
                    section_heading=cast(str, r.section_heading),
                    domain_tag=cast(str, r.domain_tag),
                )
            )

        session.close()

        logger.info("Metadata query returned %d results", len(chunks))

        return MetadataQueryResponse(
            total=total if total is not None else 0,
            offset=request.offset or 0,
            limit=request.limit or 50,
            chunks=chunks,
        )

    except Exception as e:
        logger.error("Metadata query failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Metadata query failed") from e


@router.get("/metadata/stats")
async def get_metadata_stats() -> dict[str, Any]:
    """
    Get statistics about the metadata database.

    Returns counts by department, year, and domain_tag.
    """
    try:
        neon = get_neon_storage()
        session = neon.Session()

        from sqlalchemy import func, select

        from src.storage.neon_storage import ChunkMetadata

        stats: dict[str, Any] = {
            "total_chunks": 0,
            "by_department": {},
            "by_year": {},
            "by_domain": {},
        }

        # Total count
        stats["total_chunks"] = session.execute(select(func.count(ChunkMetadata.id))).scalar()

        # Department breakdown
        dept_results = session.execute(
            select(ChunkMetadata.department, func.count(ChunkMetadata.id)).group_by(ChunkMetadata.department)
        ).all()
        stats["by_department"] = {str(r[0] or "unknown"): r[1] for r in dept_results}

        # Year breakdown
        year_results = session.execute(
            select(ChunkMetadata.date, func.count(ChunkMetadata.id)).group_by(ChunkMetadata.date)
        ).all()
        stats["by_year"] = {str(r[0] or "unknown"): r[1] for r in year_results}

        # Domain breakdown
        domain_results = session.execute(
            select(ChunkMetadata.domain_tag, func.count(ChunkMetadata.id)).group_by(ChunkMetadata.domain_tag)
        ).all()
        stats["by_domain"] = {str(r[0] or "unknown"): r[1] for r in domain_results}

        session.close()

        return stats

    except Exception as e:
        logger.error("Stats query failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Stats query failed") from e


@router.get("/metadata/departments")
async def get_departments() -> list[str]:
    """Get list of available departments."""
    try:
        neon = get_neon_storage()
        session = neon.Session()

        from sqlalchemy import select

        from src.storage.neon_storage import ChunkMetadata

        results = (
            session.execute(select(ChunkMetadata.department).where(ChunkMetadata.department.isnot(None)).distinct())
            .scalars()
            .all()
        )

        session.close()

        return [str(r) for r in results if r]

    except Exception as e:
        logger.error("Departments query failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Departments query failed") from e


@router.get("/metadata/documents")
async def get_documents() -> list[dict[str, Any]]:
    """
    Get list of source documents with chunk counts.

    Returns distinct source_file values from the metadata database
    along with their chunk counts.
    """
    try:
        neon = get_neon_storage()
        session = neon.Session()

        from sqlalchemy import func, select

        from src.storage.neon_storage import ChunkMetadata

        results = session.execute(
            select(
                ChunkMetadata.source_file,
                func.count(ChunkMetadata.id),
                func.min(ChunkMetadata.date),
                func.min(ChunkMetadata.department),
            )
            .where(ChunkMetadata.source_file.isnot(None))
            .group_by(ChunkMetadata.source_file)
            .order_by(ChunkMetadata.source_file)
        ).all()

        session.close()

        documents = [
            {
                "source_file": row[0],
                "chunk_count": row[1],
                "year": row[2] or "Unknown",
                "department": row[3] or "General",
            }
            for row in results
        ]

        return documents

    except Exception as e:
        logger.error("Documents query failed: %s", str(e))
        raise HTTPException(status_code=500, detail="Documents query failed") from e
