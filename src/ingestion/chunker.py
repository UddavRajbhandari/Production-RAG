"""
Structure-Aware Chunker Module
Splits document trees into LLM-sized context chunks.
Ensures semantic units like tables and code blocks remain intact.
"""

from typing import Any

from llama_index.core.node_parser import SentenceWindowNodeParser
from llama_index.core.schema import TextNode


class StructureAwareChunker:
    """Chunker that respects document boundaries and structural tags."""

    def __init__(self, chunk_size: int = 512, chunk_overlap: int = 50) -> None:
        """Initializes chunking parameters."""
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.semantic_parser = SentenceWindowNodeParser.from_defaults(
            window_size=3,
            window_metadata_key="window",
            original_text_metadata_key="original_text",
        )

    def chunk(self, structured_tree: list[dict[str, Any]]) -> list[TextNode]:
        """
        Iterates through the document tree and splits content into TextNodes.
        Prevents splitting within 'table' or 'code_block' types.
        """
        nodes = []
        for block in structured_tree:
            block_type = block["type"]
            content = block["content"]
            metadata = block.get("metadata", {})

            if block_type in ["table", "code_block"]:
                # Satisfies the 'never split table rows' hard rule
                nodes.append(
                    TextNode(text=content, metadata={**metadata, "type": block_type})
                )
            else:
                # Applies size-based splitting to paragraphs and headings
                word_count = len(content.split())
                if word_count > self.chunk_size:
                    sub_chunks = self._simple_split(
                        content, self.chunk_size, self.chunk_overlap
                    )
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
                            text=content, metadata={**metadata, "type": block_type}
                        )
                    )

        return nodes

    def _simple_split(self, text: str, size: int, overlap: int) -> list[str]:
        """Performs word-based splitting with defined overlap."""
        words = text.split()
        chunks = []
        for i in range(0, len(words), size - overlap):
            chunk = " ".join(words[i : i + size])
            chunks.append(chunk)
            if i + size >= len(words):
                break
        return chunks
