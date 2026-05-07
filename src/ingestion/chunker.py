"""
Structure-Aware Chunker Module
Splits document trees into LLM-sized context chunks.
Enforces token-accurate size limits — not word counts.
Ensures semantic units like tables and code blocks remain intact.
"""

from typing import Any

import tiktoken
from llama_index.core.schema import TextNode


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

        for block in structured_tree:
            block_type = block["type"]
            content = block["content"]
            metadata = block.get("metadata", {})

            if block_type in ("table", "code_block"):
                # Hard rule: never split tables or code blocks.
                nodes.append(
                    TextNode(text=content, metadata={**metadata, "type": block_type})
                )
            else:
                token_count = self._count_tokens(content)
                if token_count > self.chunk_size:
                    sub_chunks = self._token_split(content)
                    for i, sub_content in enumerate(sub_chunks):
                        nodes.append(
                            TextNode(
                                text=sub_content,
                                metadata={
                                    **metadata,
                                    "type": block_type,
                                    "sub_index": i,
                                },
                            )
                        )
                else:
                    nodes.append(
                        TextNode(
                            text=content,
                            metadata={**metadata, "type": block_type},
                        )
                    )

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
