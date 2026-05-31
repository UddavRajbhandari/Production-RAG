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
    event,
    inspect,
    select,
    text,
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
    tenant_id = Column(String, index=True)
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
        if db_url.startswith("postgresql"):

            @event.listens_for(self.engine, "connect")
            def _set_statement_timeout(dbapi_connection: object, connection_record: object) -> None:
                if hasattr(dbapi_connection, "cursor"):
                    cursor = dbapi_connection.cursor()
                    cursor.execute("SET statement_timeout = 60000")
                    cursor.close()

        self.Session = sessionmaker(bind=self.engine)

    def _migrate_schema(self) -> None:
        """Add missing columns to existing tables without dropping data."""
        try:
            inspector = inspect(self.engine)
            if "chunk_metadata" not in inspector.get_table_names():
                return
            existing = {c["name"] for c in inspector.get_columns("chunk_metadata")}
            wanted = {
                "chunk_index": "INTEGER",
                "section_heading": "VARCHAR",
                "domain_tag": "VARCHAR",
                "date": "VARCHAR",
                "department": "VARCHAR",
                "tenant_id": "VARCHAR",
            }
            with self.engine.connect() as conn:
                for col_name, col_type in wanted.items():
                    if col_name not in existing:
                        conn.execute(text(f"ALTER TABLE chunk_metadata ADD COLUMN {col_name} {col_type}"))
                        logger.info("Added missing column '%s' to chunk_metadata", col_name)
                # Backfill tenant_id from full_metadata JSON for existing rows
                if "tenant_id" not in existing:
                    try:
                        dialect = conn.dialect.name
                        if dialect == "postgresql":
                            conn.execute(
                                text(
                                    "UPDATE chunk_metadata "
                                    "SET tenant_id = full_metadata->>'tenant_id' "
                                    "WHERE tenant_id IS NULL AND full_metadata->>'tenant_id' IS NOT NULL"
                                )
                            )
                        else:
                            conn.execute(
                                text(
                                    "UPDATE chunk_metadata "
                                    "SET tenant_id = json_extract(full_metadata, '$.tenant_id') "
                                    "WHERE tenant_id IS NULL AND json_extract(full_metadata, '$.tenant_id') IS NOT NULL"
                                )
                            )
                        conn.commit()
                        logger.info("Backfilled tenant_id from full_metadata JSON")
                    except Exception as e:
                        logger.warning("tenant_id backfill skipped (non-fatal): %s", e)
                conn.commit()
        except Exception as e:
            logger.warning("Schema migration skipped (non-fatal): %s", e)

    def create_tables(self, force_recreate: bool = False) -> None:
        """Creates all tables defined in the schema."""
        if force_recreate:
            Base.metadata.drop_all(self.engine)
            logger.info("Dropped existing metadata schema.")
        Base.metadata.create_all(self.engine)
        self._migrate_schema()
        logger.info("Schema initialised (chunk_metadata table ready).")

    def insert_metadata(
        self,
        nodes: list[TextNode],
        batch_size: int = _INSERT_BATCH_SIZE,
    ) -> None:
        """
        Bulk-inserts metadata records for a list of nodes in batches.

        Uses add_all() for fast bulk insert (single round-trip per batch).
        Falls back to individual merge() if bulk insert fails (e.g. conflict).
        """
        total = len(nodes)
        inserted = 0

        def _build_record(node: TextNode) -> ChunkMetadata:
            meta = node.metadata
            return ChunkMetadata(
                id=node.id_,
                text=node.text.replace("\x00", ""),
                source_file=meta.get("source_file"),
                page_number=meta.get("page_number"),
                chunk_index=meta.get("chunk_index"),
                section_heading=meta.get("section_heading"),
                domain_tag=meta.get("domain_tag"),
                date=meta.get("date"),
                department=meta.get("department"),
                tenant_id=meta.get("tenant_id"),
                version=meta.get("version", "v1.1"),
                full_metadata=meta,
            )

        for start in range(0, total, batch_size):
            batch = nodes[start : start + batch_size]
            session = self.Session()
            try:
                records = [_build_record(n) for n in batch]
                session.add_all(records)
                session.commit()
                inserted += len(batch)
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug("Inserted %d/%d metadata records.", inserted, total)
            except Exception:
                session.rollback()
                logger.warning("Bulk insert failed at offset %d, falling back to individual merge", start)
                try:
                    for node in batch:
                        record = _build_record(node)
                        session.merge(record)
                    session.commit()
                    inserted += len(batch)
                except Exception as exc2:
                    session.rollback()
                    logger.error("Merge insert also failed at offset %d: %s", start, exc2)
                    raise
            finally:
                session.close()
        logger.info("Inserted %d metadata records.", inserted)

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
