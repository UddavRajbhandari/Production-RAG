"""
Unit tests for Storage Factory and Cloud Detection.
Tests the automatic mode detection and factory functions.
"""

import os
from unittest.mock import patch

import pytest


class TestStorageModeDetection:
    """Tests for storage mode detection functions."""

    def test_detect_storage_mode_local(self) -> None:
        """Test storage mode detection with no cloud vars set."""
        with patch.dict(os.environ, {}, clear=True):
            from src.storage.storage_factory import detect_storage_mode

            mode = detect_storage_mode()
            assert mode == "local_sqlite"

    def test_detect_storage_mode_cloud(self) -> None:
        """Test storage mode detection with cloud vars set."""
        test_env = {
            "QDRANT_URL": "https://test.qdrant.cloud",
            "QDRANT_API_KEY": "test-key",  # pragma: allowlist secret
            "DATABASE_URL": "postgres://user:pass@host/neon",  # pragma: allowlist secret
        }

        with patch.dict(os.environ, test_env, clear=True):
            import importlib

            import src.storage.storage_factory as sf_module

            importlib.reload(sf_module)

            mode = sf_module.detect_storage_mode()
            assert mode == "cloud_neon"

    def test_should_use_qdrant_bm25_true(self) -> None:
        """Test that should_use_qdrant_bm25 returns True when QDRANT_URL is set."""
        test_env = {
            # pragma: allowlist secret
            "QDRANT_URL": "https://test.qdrant.cloud"
        }

        with patch.dict(os.environ, test_env, clear=True):
            import importlib

            import src.storage.storage_factory as sf_module

            importlib.reload(sf_module)

            assert sf_module.should_use_qdrant_bm25() is True

    def test_should_use_qdrant_bm25_false(self) -> None:
        """Test that should_use_qdrant_bm25 returns False when QDRANT_URL is not set."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib

            import src.storage.storage_factory as sf_module

            importlib.reload(sf_module)

            assert sf_module.should_use_qdrant_bm25() is False

    def test_should_use_qdrant_bm25_empty_string(self) -> None:
        """Test that should_use_qdrant_bm25 returns False for empty string."""
        with patch.dict(os.environ, {"QDRANT_URL": ""}, clear=True):
            import importlib

            import src.storage.storage_factory as sf_module

            importlib.reload(sf_module)

            assert sf_module.should_use_qdrant_bm25() is False


class TestQdrantStorageModeDetection:
    """Tests for QdrantStorage mode detection."""

    def test_qdrant_mode_cloud(self) -> None:
        """Test QdrantStorage mode is 'cloud' when QDRANT_URL is set."""
        test_env = {
            "QDRANT_URL": "https://test.qdrant.cloud",
            "QDRANT_API_KEY": "test-key",  # pragma: allowlist secret
        }

        with (
            patch.dict(os.environ, test_env, clear=True),
            patch("src.storage.qdrant_storage.QdrantClient") as mock_client,
        ):
            mock_instance = mock_client.return_value
            mock_instance.get_collections.return_value = None

            import importlib

            import src.storage.qdrant_storage as qs_module

            importlib.reload(qs_module)

            from src.storage.qdrant_storage import get_qdrant_mode

            mode = get_qdrant_mode()
            assert mode == "cloud"

    def test_qdrant_mode_local(self) -> None:
        """Test QdrantStorage mode is 'local' when QDRANT_URL is not set."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib

            import src.storage.qdrant_storage as qs_module

            importlib.reload(qs_module)

            from src.storage.qdrant_storage import get_qdrant_mode

            mode = get_qdrant_mode()
            assert mode == "local"


class TestBM25StorageAddNodes:
    """Tests for BM25Storage incremental add functionality."""

    def test_add_nodes_incremental(self) -> None:
        """Test that add_nodes incrementally adds to existing index."""
        from llama_index.core.schema import TextNode

        from src.storage.bm25_storage import BM25Storage

        storage = BM25Storage()
        storage.persist_path = "storage/test_incremental.pkl"

        initial_nodes = [
            TextNode(text="Apple is a fruit", id_="1"),
            TextNode(text="Microsoft makes software", id_="2"),
            TextNode(text="Google makes search engine", id_="3"),
            TextNode(text="Amazon makes cloud services", id_="4"),
        ]
        storage.build_index(initial_nodes)
        assert len(storage.nodes) == 4

        new_nodes = [
            TextNode(text="Nvidia makes GPUs for gaming", id_="5"),
            TextNode(text="Tesla makes electric cars", id_="6"),
        ]
        storage.add_nodes(new_nodes)

        assert len(storage.nodes) == 6

        results = storage.search("software", top_k=1)
        assert len(results) >= 1
        assert "Microsoft" in results[0].text

        results2 = storage.search("cloud", top_k=1)
        assert len(results2) >= 1
        assert "Amazon" in results2[0].text

        if os.path.exists(storage.persist_path):
            os.remove(storage.persist_path)

    def test_add_nodes_rebuilds_index(self) -> None:
        """Test that add_nodes rebuilds the full index with combined corpus."""
        from llama_index.core.schema import TextNode

        from src.storage.bm25_storage import BM25Storage

        storage = BM25Storage()
        storage.persist_path = "storage/test_rebuild.pkl"

        nodes1 = [
            TextNode(text="Python is a programming language", id_="1"),
            TextNode(text="Java is another language", id_="2"),
            TextNode(text="Ruby is a scripting language", id_="3"),
        ]
        storage.build_index(nodes1)

        nodes2 = [
            TextNode(text="JavaScript runs in browsers", id_="4"),
            TextNode(text="TypeScript is JavaScript with types", id_="5"),
        ]
        storage.add_nodes(nodes2)

        python_results = storage.search("language", top_k=3)
        js_results = storage.search("javascript", top_k=3)

        assert len(python_results) >= 1
        assert len(js_results) >= 1
        assert any("Python" in r.text or "programming" in r.text for r in python_results)

        if os.path.exists(storage.persist_path):
            os.remove(storage.persist_path)


class TestHealthCheckModeReporting:
    """Tests for health check mode reporting."""

    def test_get_storage_mode_local(self) -> None:
        """Test _get_storage_mode returns correct format for local mode."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib

            import src.api.routes.health as health_module

            importlib.reload(health_module)

            mode_info = health_module._get_storage_mode()

            assert mode_info["qdrant_mode"] == "local"
            assert mode_info["postgres_mode"] == "sqlite"
            assert mode_info["bm25_mode"] == "local_pickle"

    def test_get_storage_mode_cloud(self) -> None:
        """Test _get_storage_mode returns correct format for cloud mode."""
        test_env = {
            "QDRANT_URL": "https://test.qdrant.cloud",
            "DATABASE_URL": "postgres://user:pass@host/neon",  # pragma: allowlist secret
        }

        with patch.dict(os.environ, test_env, clear=True):
            import importlib

            import src.api.routes.health as health_module

            importlib.reload(health_module)

            mode_info = health_module._get_storage_mode()

            assert mode_info["qdrant_mode"] == "cloud"
            assert mode_info["postgres_mode"] == "neon"
            assert mode_info["bm25_mode"] == "qdrant_native"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
