"""
Tenant key storage for API-key-based tenant isolation.

Stores the mapping from API key to tenant_id in Neon/Postgres
so it survives HF Space restarts.

Uses the same SQLAlchemy engine pattern as neon_storage.py.
"""

from __future__ import annotations

import datetime
import logging
import os
import secrets
import time
from collections.abc import Callable
from typing import TypeVar

import yaml
from sqlalchemy import Column, DateTime, String, create_engine, event
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import sessionmaker

from src.storage.neon_storage import Base

logger = logging.getLogger(__name__)

_RETRY_DELAY_S = 1.0
_RETRY_ATTEMPTS = 3
_FnT = TypeVar("_FnT")


def _with_retry(fn: Callable[[], _FnT]) -> _FnT:
    """Retry DB operation on transient OperationalError (Neon cold start)."""
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            return fn()
        except OperationalError as e:
            if attempt < _RETRY_ATTEMPTS - 1:
                logger.warning("DB retry %d/%d after: %s", attempt + 1, _RETRY_ATTEMPTS, e)
                time.sleep(_RETRY_DELAY_S)
            else:
                raise
    raise RuntimeError("Unreachable")


class TenantKey(Base):
    __tablename__ = "tenant_keys"

    api_key = Column(String, primary_key=True)
    tenant_id = Column(String, index=True, nullable=False)
    created_at = Column(
        DateTime,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )


_store_instance: TenantStore | None = None


def get_tenant_store() -> TenantStore:
    global _store_instance
    if _store_instance is None:
        _store_instance = TenantStore()
    return _store_instance


class TenantStore:
    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        db_url = os.environ.get("DATABASE_URL")
        if not db_url:
            from pathlib import Path

            storage_dir = Path("storage")
            storage_dir.mkdir(exist_ok=True)
            db_url = "sqlite:///storage/tenants.db"
            logger.warning("DATABASE_URL not set — using local SQLite: %s", db_url)
        else:
            logger.info("TenantStore using database: %s", db_url.split("@")[-1])

        self.engine = create_engine(db_url)
        if db_url.startswith("postgresql"):

            @event.listens_for(self.engine, "connect")
            def _set_statement_timeout(dbapi_connection: object, connection_record: object) -> None:
                if hasattr(dbapi_connection, "cursor"):
                    cursor = dbapi_connection.cursor()
                    cursor.execute("SET statement_timeout = 60000")
                    cursor.close()

        self.Session = sessionmaker(bind=self.engine)
        Base.metadata.create_all(self.engine)
        logger.info("TenantStore initialized")

    def create_tenant(self) -> tuple[str, str]:
        api_key = "rag_" + secrets.token_hex(32)  # pragma: allowlist secret
        tenant_id = "tnt_" + secrets.token_hex(6)

        def _create() -> tuple[str, str]:
            session = self.Session()
            try:
                session.add(TenantKey(api_key=api_key, tenant_id=tenant_id))
                session.commit()
                logger.info("Created tenant %s", tenant_id)
                return api_key, tenant_id
            except Exception:
                session.rollback()
                logger.error("Failed to create tenant", exc_info=True)
                raise
            finally:
                session.close()

        return _with_retry(_create)

    def lookup_tenant(self, api_key: str) -> str | None:
        def _lookup() -> str | None:
            session = self.Session()
            try:
                row = session.get(TenantKey, api_key)
                if row:
                    return str(row.tenant_id)
                return None
            finally:
                session.close()

        return _with_retry(_lookup)

    def tenant_exists(self, tenant_id: str) -> bool:
        def _exists() -> bool:
            session = self.Session()
            try:
                return bool(session.query(TenantKey).filter(TenantKey.tenant_id == tenant_id).first())
            finally:
                session.close()

        return _with_retry(_exists)
