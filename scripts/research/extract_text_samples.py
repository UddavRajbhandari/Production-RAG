"""
Text Sample Extraction Script
Extracts first few pages of representative documents for manual inspection.
Provides a quick view of document structure and text quality.
"""

import os

import fitz


def extract_sample(file_path: str, pages: list[int] | None = None) -> None:
    """Extracts and prints text from specified pages of a PDF."""
    if pages is None:
        pages = [0, 1, 2]
    print(f"\n=== Sample from {os.path.basename(file_path)} ===")
    try:
        doc = fitz.open(file_path)
        for p in pages:
            if p < len(doc):
                print(f"--- Page {p + 1} ---")
                print(doc[p].get_text())
        doc.close()
    except Exception as e:
        print(f"Error: {e}")


# Sample files for verification
samples: list[str] = [
    "data/raw/pdf/Access-to-Information-2023-annual-report.pdf",
    "data/raw/pdf/2605.02520v1.pdf",
    "data/raw/pdf/Python-tutorial-pdf1.pdf",
]

if __name__ == "__main__":
    for s in samples:
        if os.path.exists(s):
            extract_sample(s)
