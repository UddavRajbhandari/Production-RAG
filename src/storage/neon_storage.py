"""
Relational Metadata Storage Module
Uses SQLAlchemy to manage chunk metadata in a SQL database.

Supports local SQLite (development) and Neon/Postgres (production).
Connection string loaded from DATABASE_URL environment variable.

Changes from v1:
- File moved to src/storage/ (was incorrectly in src/retrieval/)
- declarative_base() replaced with DeclarativeBase (SQLAlchemy 2.x)
- Added section_heading and domain_tag columns to match Phase 1 metadata
- datetime.utcnow() replaced with datetime.now(UTC) (Python 3.12 warning)
- Batched inserts to avoid single giant transaction for large corpora
- query_by_filters() method added for Phase 3 metadata filtering tests
"""

import datetime
import logging
import os
from typing import Any

import yaml
from llama_index.core.schema import TextNode
from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import DeclarativeBase, sessionmaker

logger = logging.getLogger(__name__)

_INSERT_BATCH_SIZE = 500


# SQLAlchemy 2.x style — replaces deprecated declarative_base()
class Base(DeclarativeBase):
    pass


class ChunkMetadata(Base):
    """SQLAlchemy model for storing enriched chunk metadata."""

    __tablename__ = "chunk_metadata"

    id = Column(String, primary_key=True)
    text = Column(Text, nullable=False)
    source_file = Column(String, index=True)
    page_number = Column(Integer)
    chunk_index = Column(Integer, index=True)  # needed for context expansion
    section_heading = Column(String)  # populated by Phase 1 metadata pipeline
    domain_tag = Column(String, index=True)
    date = Column(String, index=True)  # year extracted from filename
    department = Column(String, index=True)
    # Financial / Academic / Technical / General
    version = Column(String, default="v1.1")
    full_metadata = Column(JSON)  # complete metadata dict for arbitrary fields
    created_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


class NeonStorage:
    """Storage client for the relational metadata database."""

    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            # Auto-append chunker suffix for Phase 6 iteration comparison
            # e.g., "storage/metadata.db" -> "storage/metadata_naive.db"
            if self.config["storage"]["postgres"].get("use_chunker_suffix", True):
                ing = self.config.get("ingestion", {})
                chunker_type = ing.get("chunker_type", "structure_aware")
                base_name = "storage/metadata.db".replace(".db", "")
                db_url = f"sqlite:///{base_name}_{chunker_type}.db"
            else:
                db_url = "sqlite:///storage/metadata.db"
            logger.warning("DATABASE_URL not set — using local SQLite: %s", db_url)
        else:
            logger.info("Using database: %s", db_url.split("@")[-1])  # hide credentials

        self.engine = create_engine(db_url)
        self.Session = sessionmaker(bind=self.engine)

    def create_tables(self, force_recreate: bool = False) -> None:
        """Creates all tables defined in the schema."""
        if force_recreate:
            Base.metadata.drop_all(self.engine)
            logger.info("Dropped existing metadata schema.")
        Base.metadata.create_all(self.engine)
        logger.info("Schema initialised (chunk_metadata table ready).")

    def insert_metadata(
        self,
        nodes: list[TextNode],
        batch_size: int = _INSERT_BATCH_SIZE,
    ) -> None:
        """
        Upserts metadata records for a list of nodes in batches.

        Uses session.merge() for upsert semantics — safe to re-run after
        re-ingestion without creating duplicates.
        """
        total = len(nodes)
        inserted = 0

        for start in range(0, total, batch_size):
            batch = nodes[start : start + batch_size]
            session = self.Session()
            try:
                for node in batch:
                    meta = node.metadata
                    # Strip NUL characters from text (Postgres doesn't allow them)
                    clean_text = node.text.replace("\x00", "")
                    record = ChunkMetadata(
                        id=node.id_,
                        text=clean_text,
                        source_file=meta.get("source_file"),
                        page_number=meta.get("page_number"),
                        chunk_index=meta.get("chunk_index"),
                        section_heading=meta.get("section_heading"),
                        domain_tag=meta.get("domain_tag"),
                        date=meta.get("date"),
                        department=meta.get("department"),
                        version=meta.get("version", "v1.1"),
                        full_metadata=meta,
                    )
                    session.merge(record)
                session.commit()
                inserted += len(batch)
                logger.info("Inserted %d/%d metadata records.", inserted, total)
            except Exception as exc:
                session.rollback()
                logger.error("Batch insert failed at offset %d: %s", start, exc)
                raise
            finally:
                session.close()

    def query_by_filters(
        self,
        department: str | None = None,
        date: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Returns metadata records matching the given filters.

        Used for Phase 3 metadata filtering verification and Phase 6 debugging.
        Both filters are optional — omit to return unfiltered rows.
        """
        session = self.Session()
        try:
            stmt = select(ChunkMetadata)
            if department:
                stmt = stmt.where(ChunkMetadata.department == department)
            if date:
                stmt = stmt.where(ChunkMetadata.date == date)
            stmt = stmt.limit(limit)

            rows = session.execute(stmt).scalars().all()
            return [
                {
                    "id": r.id,
                    "source_file": r.source_file,
                    "section_heading": r.section_heading,
                    "domain_tag": r.domain_tag,
                    "date": r.date,
                    "department": r.department,
                }
                for r in rows
            ]
        finally:
            session.close()

    def get_node_by_id(self, node_id: str) -> ChunkMetadata | None:
        """Fetch a single metadata record by its primary key ID."""
        session = self.Session()
        try:
            result: ChunkMetadata | None = session.get(ChunkMetadata, node_id)
            return result
        finally:
            session.close()

    def get_chunks_by_source_file(self, source_file: str) -> list[ChunkMetadata]:
        """Fetch all chunks for a given source file."""
        session = self.Session()
        try:
            stmt = select(ChunkMetadata).where(ChunkMetadata.source_file == source_file)
            return list(session.execute(stmt).scalars().all())
        finally:
            session.close()
