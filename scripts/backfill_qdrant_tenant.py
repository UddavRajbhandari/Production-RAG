"""
One-time: backfill tenant_id on Qdrant points where it's missing or empty.
Reads your tenant_id from my_tenant.txt (line 2).
"""

import os
import sys

sys.path.insert(0, os.getcwd())

from qdrant_client.http import models

from src.storage.qdrant_storage import QdrantStorage

with open("my_tenant.txt") as f:
    TENANT_ID = f.read().strip().splitlines()[1].strip()

storage = QdrantStorage()
client = storage.client
collection = storage.collection_name

# Scroll all points in batches, filter for missing/empty tenant_id in Python
points_to_fix: list[models.Record] = []
next_offset: object = None

while True:
    scroll = client.scroll(
        collection_name=collection,
        limit=1000,
        offset=next_offset,
    )
    batch, next_offset = scroll[0], scroll[1]
    if not batch:
        break
    for p in batch:
        tid = p.payload.get("tenant_id", "")
        if not tid:
            points_to_fix.append(p)
    if next_offset is None:
        break

if not points_to_fix:
    print("No points missing tenant_id — all good!")
    sys.exit(0)

print(f"Found {len(points_to_fix)} points missing tenant_id. Backfilling...")

ids = [p.id for p in points_to_fix]
client.set_payload(
    collection_name=collection,
    payload={"tenant_id": TENANT_ID},
    points=ids,
)

print(f"Backfilled {len(ids)} points with tenant_id={TENANT_ID}")
