"""
Structure-Aware Chunker Module
Splits document trees into LLM-sized context chunks.
Enforces token-accurate size limits — not word counts.
Ensures semantic units like tables and code blocks remain intact.
"""

import hashlib
from typing import Any

import tiktoken
from llama_index.core.schema import TextNode


def generate_deterministic_id(text: str, prefix: str = "", index: int = 0) -> str:
    """
    Generate a deterministic ID based on chunk content.
    Uses SHA256 hash of first 200 characters + index for uniqueness.
    """
    content_hash = hashlib.sha256(f"{text[:200]}_{index}".encode()).hexdigest()[:12]
    if prefix:
        return f"{prefix}_{content_hash}"
    return content_hash


class StructureAwareChunker:
    """Chunker that respects document boundaries and structural tags."""

    # Encoding used for token counting.
    # cl100k_base covers GPT-3.5/4 and is a reliable proxy for
    # sentence-transformers tokenisation for size-capping purposes.
    _ENCODING_NAME = "cl100k_base"

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50) -> None:
        """
        Args:
            chunk_size:    Maximum tokens per chunk (hard ceiling).
            chunk_overlap: Token overlap between adjacent split chunks.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._enc = tiktoken.get_encoding(self._ENCODING_NAME)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chunk(self, structured_tree: list[dict[str, Any]]) -> list[TextNode]:
        """
        Iterates through the tagged document tree and produces TextNodes.

        Rules:
        - table / code_block → never split, emit as single node even if large
        - heading / paragraph / list_item → split when token count > chunk_size
        """
        nodes: list[TextNode] = []
        chunk_index = 0

        for block in structured_tree:
            block_type = block["type"]
            content = block["content"]
            metadata = block.get("metadata", {})
            chunk_type = "sa"  # structure-aware

            if block_type in ("table", "code_block"):
                # Hard rule: never split tables or code blocks.
                node = TextNode(text=content, metadata={**metadata, "type": block_type})
                node.id_ = generate_deterministic_id(
                    content, prefix=chunk_type, index=chunk_index
                )
                chunk_index += 1
                nodes.append(node)
            else:
                token_count = self._count_tokens(content)
                if token_count > self.chunk_size:
                    sub_chunks = self._token_split(content)
                    for i, sub_content in enumerate(sub_chunks):
                        node = TextNode(
                            text=sub_content,
                            metadata={
                                **metadata,
                                "type": block_type,
                                "sub_index": i,
                            },
                        )
                        node.id_ = generate_deterministic_id(
                            sub_content, prefix=chunk_type, index=chunk_index
                        )
                        chunk_index += 1
                        nodes.append(node)
                else:
                    node = TextNode(
                        text=content,
                        metadata={**metadata, "type": block_type},
                    )
                    node.id_ = generate_deterministic_id(
                        content, prefix=chunk_type, index=chunk_index
                    )
                    chunk_index += 1
                    nodes.append(node)

        return nodes

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _count_tokens(self, text: str) -> int:
        """Returns the exact token count for a string."""
        return len(self._enc.encode(text))

    def _token_split(self, text: str) -> list[str]:
        """
        Splits text into chunks of at most `chunk_size` tokens with
        `chunk_overlap` token overlap between adjacent chunks.

        Works on the token ID sequence directly — no word boundary
        approximation. Decodes each window back to a string.
        """
        token_ids = self._enc.encode(text)
        chunks: list[str] = []

        step = self.chunk_size - self.chunk_overlap
        if step <= 0:
            # Safeguard: overlap must be smaller than chunk_size
            step = self.chunk_size

        start = 0
        while start < len(token_ids):
            end = min(start + self.chunk_size, len(token_ids))
            window = token_ids[start:end]
            chunks.append(self._enc.decode(window))
            if end == len(token_ids):
                break
            start += step

        return chunks


class NaiveChunker:
    """
    Naive chunker that simply splits text by token count.
    Does NOT respect document structure - tables, code blocks, and headings
    are treated the same as regular text.

    This serves as the baseline for Phase 6 RAGAS iteration comparison.
    """

    _ENCODING_NAME = "cl100k_base"

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50) -> None:
        """
        Args:
            chunk_size:    Maximum tokens per chunk (hard ceiling).
            chunk_overlap: Token overlap between adjacent split chunks.
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._enc = tiktoken.get_encoding(self._ENCODING_NAME)

    def chunk(self, structured_tree: list[dict[str, Any]]) -> list[TextNode]:
        """
        Flattens all content and chunks without structure awareness.
        Tables and code blocks are split just like regular text.
        """
        nodes: list[TextNode] = []
        chunk_index = 0

        # Flatten all blocks into one text stream
        all_text_parts = []
        for block in structured_tree:
            content = block.get("content", "")
            if content:
                all_text_parts.append(content)

        combined_text = "\n\n".join(all_text_parts)

        # Simply split by token count - no structure awareness
        token_count = self._count_tokens(combined_text)
        if token_count > self.chunk_size:
            sub_chunks = self._token_split(combined_text)
            for i, sub_content in enumerate(sub_chunks):
                node = TextNode(
                    text=sub_content,
                    metadata={"type": "naive_chunk", "sub_index": i},
                )
                node.id_ = generate_deterministic_id(
                    sub_content, prefix="naive", index=chunk_index
                )
                chunk_index += 1
                nodes.append(node)
        else:
            node = TextNode(
                text=combined_text,
                metadata={"type": "naive_chunk"},
            )
            node.id_ = generate_deterministic_id(
                combined_text, prefix="naive", index=chunk_index
            )
            nodes.append(node)

        return nodes

    def _count_tokens(self, text: str) -> int:
        """Returns the exact token count for a string."""
        return len(self._enc.encode(text))

    def _token_split(self, text: str) -> list[str]:
        """Splits text into chunks of at most `chunk_size` tokens."""
        token_ids = self._enc.encode(text)
        chunks: list[str] = []

        step = self.chunk_size - self.chunk_overlap
        if step <= 0:
            step = self.chunk_size

        start = 0
        while start < len(token_ids):
            end = min(start + self.chunk_size, len(token_ids))
            window = token_ids[start:end]
            chunks.append(self._enc.decode(window))
            if end == len(token_ids):
                break
            start += step

        return chunks


def get_chunker(
    chunker_type: str = "structure_aware",
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> StructureAwareChunker | NaiveChunker:
    """
    Factory function to get the appropriate chunker.

    Args:
        chunker_type: "structure_aware" or "naive"
        chunk_size: Maximum tokens per chunk
        chunk_overlap: Token overlap between chunks

    Returns:
        An instance of the appropriate chunker
    """
    if chunker_type == "naive":
        return NaiveChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    else:
        return StructureAwareChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
