"""
Structure Analyzer Module
Classifies raw parsed blocks into a tagged document tree.
Enforces junk filters and converts tables to LLM-friendly formats.
"""

import json
from typing import Any


class StructureAnalyzer:
    """Analyzer for classifying content blocks into semantic types."""

    def __init__(self, min_char_threshold: int = 100) -> None:
        """Initializes threshold for the low-density page filter."""
        self.min_char_threshold = min_char_threshold

    def analyze(self, raw_blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Filters out low-text noise and classifies each remaining block.
        Returns a structured tree of tagged blocks.
        """
        structured_tree = []
        for block in raw_blocks:
            # Junk Filter: Audit finding #1 (zero-text / low-density pages)
            char_count = block.get("metadata", {}).get("char_count", 0)
            if block["type"] == "page" and char_count < self.min_char_threshold:
                continue

            classified_block = self._classify(block)
            if classified_block:
                structured_tree.append(classified_block)

        return structured_tree

    def _classify(self, block: dict[str, Any]) -> dict[str, Any] | None:
        """
        Heuristic-based classification into:
        heading, paragraph, table, code_block, list_item.
        """
        content = block["content"]
        block_type = block["type"]
        metadata = block.get("metadata", {})

        if block_type == "table":
            return {
                "type": "table",
                "content": self._table_to_markdown(content),
                "metadata": metadata,
            }

        if block_type == "sheet":
            return {
                "type": "table",
                "content": self._table_to_markdown(content),
                "metadata": metadata,
            }

        if block_type == "page":
            return {"type": "paragraph", "content": content, "metadata": metadata}

        if block_type == "paragraph":
            style = metadata.get("style", "").lower()
            if "heading" in style:
                return {"type": "heading", "content": content, "metadata": metadata}

            if content.startswith(("- ", "* ", "1. ", "• ")):
                return {"type": "list_item", "content": content, "metadata": metadata}

            if content.startswith(("```", "def ", "import ", "class ")):
                return {"type": "code_block", "content": content, "metadata": metadata}

            return {"type": "paragraph", "content": content, "metadata": metadata}

        return {"type": "paragraph", "content": str(content), "metadata": metadata}

    def _table_to_markdown(self, table_data: list[list[Any]]) -> str:
        """Converts raw nested list data to a Markdown formatted table string."""
        if not table_data:
            return ""

        markdown = ""
        for i, row in enumerate(table_data):
            row_str = (
                "| "
                + " | ".join([str(cell) if cell is not None else "" for cell in row])
                + " |"
            )
            markdown += row_str + "\n"
            if i == 0:  # Add separator after header
                separator = "| " + " | ".join(["---"] * len(row)) + " |"
                markdown += separator + "\n"

        return markdown

    def save_tree(self, tree: list[dict[str, Any]], output_path: str) -> None:
        """Serializes the structured tree to a JSON file for debugging."""
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(tree, f, indent=2, ensure_ascii=False)
