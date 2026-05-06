import os

from llama_index.core.schema import TextNode

from src.storage.bm25_index import BM25Storage


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
