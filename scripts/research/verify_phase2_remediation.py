import os
import uuid

from sqlalchemy import inspect

from src.storage.bm25_storage import BM25Storage
from src.storage.neon_storage import NeonStorage
from src.storage.qdrant_storage import QdrantStorage


def verify_phase2() -> None:
    print("--- Phase 2 Verification Checklist ---")

    # 1. Qdrant UUID validation
    print("\n1. Verifying Qdrant UUID validation...")
    qs = QdrantStorage()
    valid_uuid = str(uuid.uuid4())
    try:
        validated = qs._validated_uuid(valid_uuid)
        assert validated == valid_uuid
        print(f"  Valid UUID accepted: {validated} ✓")
    except ValueError as e:
        print(f"  ERROR: Valid UUID rejected: {e}")

    try:
        qs._validated_uuid("not-a-uuid")
        print("  ERROR: Invalid string was not rejected")
    except ValueError as e:
        print(f"  Invalid UUID correctly rejected ✓ ({e})")

    # 2. File location
    print("\n2. Verifying file locations...")
    neon_path = "src/storage/neon_storage.py"
    if os.path.exists(neon_path):
        print(f"  {neon_path} exists in storage directory ✓")
    else:
        print(f"  ERROR: {neon_path} not found in storage directory")

    # 3. BM25 zero-score filtering
    print("\n3. Verifying BM25 zero-score filtering...")
    bm25 = BM25Storage()
    bm25.load()
    results = bm25.search("xyzzy_nonexistent_term_99999", top_k=20)
    if len(results) == 0:
        print("  Zero-score filtering works (0 results for nonsense) ✓")
    else:
        print(f"  ERROR: BM25 returned {len(results)} results for nonsense query")

    # 4. Neon schema columns
    print("\n4. Verifying Neon/SQLite schema columns...")
    neon = NeonStorage()
    inspector = inspect(neon.engine)
    cols = [c["name"] for c in inspector.get_columns("chunk_metadata")]
    required = {
        "id",
        "source_file",
        "section_heading",
        "date",
        "department",
        "full_metadata",
    }
    missing = required - set(cols)
    if not missing:
        print(f"  All required columns present: {list(required)} ✓")
    else:
        print(f"  ERROR: Missing columns: {missing}")


if __name__ == "__main__":
    verify_phase2()
