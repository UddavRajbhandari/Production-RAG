"""
Metadata Pipeline Module
Enriches chunks with source-level and content-level metadata.

Responsibilities:
- Temporal extraction from filename (Audit Finding #4)
- Department mapping from filename prefix (replaces hardcoded "Corporate")
- Section heading propagation across chunks
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
        # Load department mapping once at init time.
        # Falls back to empty dict if key absent — handled in _resolve_department.
        self._dept_map: dict[str, str] = config.get("ingestion", {}).get("department_mapping", {})

    def process(self, nodes: list[TextNode], source_file: str) -> list[TextNode]:
        """
        Primary entry point for metadata enrichment.
        Runs all enrichment steps in the correct order and returns the
        enriched node list. Callers do not need to call any other method.

        Steps:
        1. Temporal extraction from filename
        2. Department resolution from filename
        3. Source-level metadata attachment
        4. Section heading propagation (internal — do not call separately)
        """
        filename = os.path.basename(source_file)
        document_year = self._extract_year(filename)
        department = self._resolve_department(filename)

        for i, node in enumerate(nodes):
            node.metadata.update(
                {
                    "source_file": filename,
                    "chunk_index": i,
                    "date": document_year,
                    "department": department,
                }
            )

        # Section heading must run after chunk_index is assigned
        self._propagate_section_headings(nodes)

        return nodes

    # ------------------------------------------------------------------
    # Private helpers — not part of the public API
    # ------------------------------------------------------------------

    def _extract_year(self, filename: str) -> str:
        """
        Extracts a four-digit year or fiscal year tag from the filename.
        Priority over internal PDF metadata per Pre-Phase-1 Audit Finding #4.

        Examples:
            "annual-report-2023.pdf"  → "2023"
            "FY22-budget-summary.pdf" → "FY22"
            "worldbankP505272.pdf"    → "Unknown"
        """
        match = re.search(r"(20\d{2}|FY\d{2})", filename, re.IGNORECASE)
        return match.group(1) if match else "Unknown"

    def _resolve_department(self, filename: str) -> str:
        """
        Maps a filename to a department label using the prefix mapping
        defined in config/settings.yaml under ingestion.department_mapping.

        If no prefix matches, falls back to "General" so the field is
        never empty (required for Phase 2 relational filtering).

        The mapping is intentionally prefix-based so a single config entry
        covers all files from a domain (e.g., "financial_" → "Financial").
        """
        filename_lower = filename.lower()
        for prefix, dept in self._dept_map.items():
            if filename_lower.startswith(prefix.lower()):
                return dept
        return "General"

    def _propagate_section_headings(self, nodes: list[TextNode]) -> None:
        """
        Walks the node list in order and propagates the most recently
        seen heading to all subsequent nodes until the next heading appears.

        Mutates nodes in place — no return value.

        Why in-place: the list is already allocated; a copy would double
        memory for large corpora with no benefit.
        """
        current_heading = "Introduction"
        for node in nodes:
            if node.metadata.get("type") == "heading":
                current_heading = node.text
            node.metadata["section_heading"] = current_heading
