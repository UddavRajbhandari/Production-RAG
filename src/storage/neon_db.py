"""
Relational Metadata Storage Module
Uses SQLAlchemy to manage chunk metadata in a SQL database (Postgres/SQLite).
Supports relational filtering and version tracking.
"""

import datetime
import os

import yaml
from llama_index.core.schema import TextNode
from sqlalchemy import JSON, Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()


class ChunkMetadata(Base):  # type: ignore
    """SQLAlchemy model for storing enriched chunk metadata."""

    __tablename__ = "chunk_metadata"

    id = Column(String, primary_key=True)
    text = Column(Text)
    source_file = Column(String)
    page_number = Column(Integer)
    date = Column(String)
    department = Column(String)
    version = Column(String, default="v1.1")
    full_metadata = Column(JSON)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class NeonStorage:
    """Storage client for the relational metadata database."""

    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        """Initializes engine with Neon URL or local SQLite fallback."""
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        # In a real scenario, this would be loaded from .env
        self.db_url = os.environ.get("DATABASE_URL")
        if not self.db_url:
            # Fallback to local sqlite for testing if Neon URL not provided
            self.db_url = "sqlite:///storage/metadata.db"
            print(f"DATABASE_URL not found. Using local SQLite: {self.db_url}")

        self.engine = create_engine(self.db_url)
        self.Session = sessionmaker(bind=self.engine)

    def create_tables(self) -> None:
        """Initializes the database schema."""
        Base.metadata.create_all(self.engine)
        print("Metadata tables created.")

    def insert_metadata(self, nodes: list[TextNode]) -> None:
        """Upserts metadata records for a list of nodes."""
        session = self.Session()
        try:
            for node in nodes:
                meta = node.metadata
                chunk = ChunkMetadata(
                    id=node.id_,
                    text=node.text,
                    source_file=meta.get("source_file"),
                    page_number=meta.get("page_number"),
                    date=meta.get("date"),
                    department=meta.get("department"),
                    version=meta.get("version", "v1.1"),
                    full_metadata=meta,
                )
                session.merge(chunk)  # merge handles upsert
            session.commit()
            print(f"Inserted metadata for {len(nodes)} chunks.")
        except Exception as e:
            session.rollback()
            print(f"Error inserting metadata: {e}")
        finally:
            session.close()
