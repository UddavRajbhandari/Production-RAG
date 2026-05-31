"""Check Neon for rows missing tenant_id and show the query."""

import os
import sys

sys.path.insert(0, os.getcwd())

from sqlalchemy import inspect, text

from src.storage.neon_storage import NeonStorage

storage = NeonStorage()

with storage.engine.connect() as conn:
    inspector = inspect(storage.engine)
    cols = [c["name"] for c in inspector.get_columns("chunk_metadata")]
    print("Columns:", cols)

    if "tenant_id" not in cols:
        print("tenant_id column does not exist yet — restart backend to auto-migrate")
        sys.exit(0)

    total = conn.execute(text("SELECT COUNT(*) FROM chunk_metadata")).scalar()
    missing = conn.execute(
        text("SELECT COUNT(*) FROM chunk_metadata WHERE tenant_id IS NULL OR tenant_id = ''")
    ).scalar()

    print(f"Total rows: {total}")
    print(f"Rows missing tenant_id (NULL or empty): {missing}")

    if missing:
        print("\n--- SQL query to see them ---")
        print("SELECT id, source_file, tenant_id, full_metadata->>'tenant_id' AS meta_tenant_id")
        print("FROM chunk_metadata")
        print("WHERE tenant_id IS NULL OR tenant_id = ''")
        print("LIMIT 20;")

        print("\n--- Update to backfill from full_metadata ---")
        print("UPDATE chunk_metadata")
        print("SET tenant_id = full_metadata->>'tenant_id'")
        print("WHERE tenant_id IS NULL OR tenant_id = '';")
