import os

from src.ingestion.chunker import StructureAwareChunker
from src.ingestion.parser import DocumentParser
from src.ingestion.structure_analyzer import StructureAnalyzer


def test_parser_pdf_exists() -> None:
    parser = DocumentParser()
    # Testing with a known file from the corpus
    test_file = "data/raw/pdf/Access-to-Information-2023-annual-report.pdf"
    if os.path.exists(test_file):
        blocks = parser.parse(test_file)
        assert len(blocks) > 0
        assert blocks[0]["type"] == "page"


def test_analyzer_junk_filter() -> None:
    analyzer = StructureAnalyzer(min_char_threshold=100)
    raw_blocks = [
        {"type": "page", "content": "Short", "metadata": {"char_count": 5}},
        {
            "type": "page",
            "content": "Long enough content " * 10,
            "metadata": {"char_count": 200},
        },
    ]
    tree = analyzer.analyze(raw_blocks)
    assert len(tree) == 1
    assert tree[0]["content"].startswith("Long enough")


def test_chunker_hard_rules() -> None:
    chunker = StructureAwareChunker(chunk_size=10, chunk_overlap=0)
    # Testing that table type is preserved and not split (if implemented as whole units)
    structured_tree = [
        {
            "type": "table",
            "content": "| Col 1 | Col 2 |\n|---|---|\n| Data | Data |",
            "metadata": {},
        }
    ]
    nodes = chunker.chunk(structured_tree)
    assert len(nodes) == 1
    assert nodes[0].metadata["type"] == "table"
