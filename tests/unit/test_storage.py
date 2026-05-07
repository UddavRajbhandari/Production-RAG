import os

from llama_index.core.schema import TextNode
from sqlalchemy import inspect

from src.storage.bm25_index import BM25Storage
from src.storage.neon_db import NeonStorage


def test_bm25_build_and_search() -> None:
    storage = BM25Storage()
    nodes = [
        TextNode(text="Apple is a fruit", id_="1"),
        TextNode(text="Microsoft makes software", id_="2"),
        TextNode(text="Nvidia makes GPUs", id_="3"),
    ]
    storage.build_index(nodes)
    results = storage.search("software", top_k=1)
    assert len(results) == 1
    assert "Microsoft" in results[0].text


def test_bm25_zero_score_results_are_filtered() -> None:
    storage = BM25Storage()
    nodes = [
        TextNode(text="Apple is a fruit", id_="1"),
        TextNode(text="Microsoft makes software", id_="2"),
    ]
    storage.build_index(nodes)

    results = storage.search("xyzzy_nonexistent_term_12345", top_k=20)

    assert results == []


def test_bm25_persistence() -> None:
    test_path = "storage/test_bm25.pkl"
    storage = BM25Storage()
    # Mock config
    storage.persist_path = test_path
    nodes = [TextNode(text="Persist me", id_="p1")]
    storage.build_index(nodes)
    storage.save()

    new_storage = BM25Storage()
    new_storage.persist_path = test_path
    new_storage.load()
    assert len(new_storage.nodes) == 1

    # Cleanup
    if os.path.exists(test_path):
        os.remove(test_path)


def test_neon_schema_and_filter_query() -> None:
    test_db = os.path.abspath("storage/test_metadata.db")
    previous_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = f"sqlite:///{test_db}"

    try:
        storage = NeonStorage()
        storage.create_tables(force_recreate=True)

        inspector = inspect(storage.engine)
        columns = {column["name"] for column in inspector.get_columns("chunk_metadata")}
        assert "section_heading" in columns
        assert "domain_tag" in columns

        nodes = [
            TextNode(
                text="Revenue increased year over year.",
                id_="550e8400-e29b-41d4-a716-446655440000",
                metadata={
                    "source_file": "report.pdf",
                    "section_heading": "Executive Summary",
                    "domain_tag": "financial",
                    "date": "2023",
                    "department": "Financial",
                },
            )
        ]
        storage.insert_metadata(nodes)

        results = storage.query_by_filters(department="Financial", date="2023", limit=5)
        assert len(results) == 1
        assert results[0]["section_heading"] == "Executive Summary"
        assert results[0]["domain_tag"] == "financial"
    finally:
        storage.engine.dispose()
        if previous_db_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_db_url
        if os.path.exists(test_db):
            os.remove(test_db)
