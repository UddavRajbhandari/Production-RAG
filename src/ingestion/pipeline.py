"""
Ingestion Pipeline Coordinator
Wires together parsing, analysis, chunking, and metadata extraction.
Serves as the high-level API for processing individual documents.
"""

import os
from typing import Any

import yaml

from src.ingestion.chunker import StructureAwareChunker
from src.ingestion.metadata_pipeline import MetadataPipeline
from src.ingestion.parser import DocumentParser
from src.ingestion.structure_analyzer import StructureAnalyzer


class IngestionPipeline:
    """Coordinates the full ingestion sequence for a single document."""

    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        """Initializes all sub-components from global configuration."""
        with open(config_path) as f:
            self.config = yaml.safe_load(f)

        self.parser = DocumentParser()
        self.analyzer = StructureAnalyzer(
            min_char_threshold=self.config["ingestion"]["min_char_threshold"]
        )
        self.chunker = StructureAwareChunker(
            chunk_size=self.config["ingestion"]["chunk_size"],
            chunk_overlap=self.config["ingestion"]["chunk_overlap"],
        )
        self.metadata_pipeline = MetadataPipeline(self.config)

    def run(self, file_path: str) -> list[Any]:
        """
        Executes the full ingestion sequence for a single file:
            Parse → Analyze → Chunk → Metadata (including heading propagation)

        Returns a list of enriched TextNodes ready for storage population.
        """
        print(f"Processing: {file_path}")

        raw_blocks = self.parser.parse(file_path)
        structured_tree = self.analyzer.analyze(raw_blocks)
        nodes = self.chunker.chunk(structured_tree)

        # process() now handles heading propagation internally.
        # Do NOT call _extract_section_heading separately.
        nodes = self.metadata_pipeline.process(nodes, file_path)

        print(f"  -> {len(nodes)} chunks | {os.path.basename(file_path)}")
        return nodes


if __name__ == "__main__":
    pipeline = IngestionPipeline()
    test_file = "data/raw/pdf/Access-to-Information-2023-annual-report.pdf"
    if os.path.exists(test_file):
        nodes = pipeline.run(test_file)
        if nodes:
            print(f"Sample metadata: {nodes[0].metadata}")
