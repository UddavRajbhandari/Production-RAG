"""
Qdrant Vector Storage Module
Manages dense vector indexing and retrieval using Qdrant.
Supports both Docker-based remote connections and local disk fallback.
"""

import os

import yaml
from llama_index.core.schema import TextNode
from qdrant_client import QdrantClient
from qdrant_client.http import models


class QdrantStorage:
    """Storage client for the Qdrant dense vector backend."""

    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        """Initializes client with connectivity checks and local storage fallback."""
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        q_config = self.config["storage"]["qdrant"]

        # Try connecting to Docker, fallback to local path if not available
        try:
            self.client = QdrantClient(host=q_config["host"], port=q_config["port"])
            # Ping to verify connection
            self.client.get_collections()
            print(f"Connected to Qdrant at {q_config['host']}:{q_config['port']}")
        except Exception:
            local_path = "storage/qdrant_data"
            os.makedirs(local_path, exist_ok=True)
            self.client = QdrantClient(path=local_path)
            print(
                f"Docker Qdrant not available. Using local path storage: {local_path}"
            )

        self.collection_name = q_config["collection_name"]
        self.vector_size = q_config["vector_size"]
        self.distance = q_config["distance"]

    def create_collection(self, force_recreate: bool = False) -> None:
        """Initializes a new vector collection with the specified dimensions."""
        if force_recreate and self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)

        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=models.VectorParams(
                    size=self.vector_size,
                    distance=models.Distance.COSINE
                    if self.distance == "Cosine"
                    else models.Distance.EUCLID,
                ),
            )
            print(f"Collection '{self.collection_name}' created.")
        else:
            print(f"Collection '{self.collection_name}' already exists.")

    def insert_nodes(
        self, nodes: list[TextNode], embeddings: list[list[float]]
    ) -> None:
        """Upserts a list of TextNodes and their vectors into the collection."""
        points = []
        for _, (node, vector) in enumerate(zip(nodes, embeddings, strict=False)):
            points.append(
                models.PointStruct(
                    id=node.id_,
                    vector=vector,
                    payload={"text": node.text, **node.metadata},
                )
            )

        self.client.upsert(collection_name=self.collection_name, points=points)
        print(f"Inserted {len(points)} points into Qdrant.")


if __name__ == "__main__":
    storage = QdrantStorage()
    storage.create_collection()
