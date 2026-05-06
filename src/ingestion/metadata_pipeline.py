"""
Metadata Pipeline Module
Enriches chunks with source-level and content-level metadata.
Handles temporal extraction and placeholder logic for LLM-based metadata.
"""

import os
import re
from typing import Any

from llama_index.core.schema import TextNode


class MetadataPipeline:
    """Pipeline for attaching rich metadata to ingested TextNodes."""

    def __init__(self, config: dict[str, Any]) -> None:
        """Initializes with project configuration."""
        self.config = config

    def process(self, nodes: list[TextNode], source_file: str) -> list[TextNode]:
        """
        Primary entry point for metadata enrichment.
        Handles temporal extraction from filenames (Audit Finding #4).
        """
        year_match = re.search(r"(20\d{2}|FY\d{2})", source_file)
        document_year = year_match.group(1) if year_match else "Unknown"

        for i, node in enumerate(nodes):
            node.metadata.update(
                {
                    "source_file": os.path.basename(source_file),
                    "chunk_index": i,
                    "date": document_year,
                    "department": "Corporate",
                }
            )

            # Placeholders for future Phase 1 LLM enhancements
            node.metadata["summary"] = "..."
            node.metadata["keywords"] = []
            node.metadata["hypothetical_questions"] = []

        return nodes

    def _extract_section_heading(self, nodes: list[TextNode]) -> list[TextNode]:
        """
        Propagates the nearest preceding heading to all subsequent chunks.
        Ensures context is preserved in fragmented sections.
        """
        current_heading = "Introduction"
        for node in nodes:
            if node.metadata.get("type") == "heading":
                current_heading = node.text
            node.metadata["section_heading"] = current_heading
        return nodes
