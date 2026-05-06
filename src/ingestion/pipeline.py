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
    """Class coordinating the multi-step document processing flow."""

    def __init__(self, config_path: str = "config/settings.yaml") -> None:
        """Initializes all sub-components based on global configuration."""
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
        Parse -> Analyze -> Chunk -> Metadata.
        """
        print(f"Processing: {file_path}")

        # 1. Parsing (Format-specific)
        raw_blocks = self.parser.parse(file_path)

        # 2. Structure Analysis (Classification)
        structured_tree = self.analyzer.analyze(raw_blocks)

        # 3. Chunking (Structure-aware)
        nodes = self.chunker.chunk(structured_tree)

        # 4. Metadata Extraction (Temporal + Structural)
        nodes = self.metadata_pipeline.process(nodes, file_path)
        nodes = self.metadata_pipeline._extract_section_heading(nodes)

        print(f"Generated {len(nodes)} chunks for {os.path.basename(file_path)}")
        return nodes


if __name__ == "__main__":
    # Test execution on a single known file
    pipeline = IngestionPipeline()
    test_file = "data/raw/pdf/Access-to-Information-2023-annual-report.pdf"
    if os.path.exists(test_file):
        nodes = pipeline.run(test_file)
        if nodes:
            print(f"Sample Node Metadata: {nodes[0].metadata}")
