"""
Ground Truth Source Verification Script
Extracts specific pages from target documents to verify ground truth accuracy.
Ensures that the 'Gold Standard' answers are factually grounded.
"""

import os

import docx
import fitz


def read_pages(file_path: str, pages: list[int]) -> None:
    """Reads and prints specified pages from a PDF or first paragraphs of a DOCX."""
    print(f"\n--- VERIFYING: {os.path.basename(file_path)} ---")
    try:
        if file_path.endswith(".pdf"):
            doc = fitz.open(file_path)
            for p in pages:
                if p < len(doc):
                    print(f"PAGE {p+1}:")
                    print(doc[p].get_text())
            doc.close()
        elif file_path.endswith(".docx"):
            doc = docx.Document(file_path)
            print("\n".join([p.text for p in doc.paragraphs[:50]]))
    except Exception as e:
        print(f"Error: {e}")


# Verification targets (file_path, page_indices)
targets: list[tuple[str, list[int]]] = [
    ("data/raw/pdf/Python-tutorial-pdf1.pdf", [2]),
    ("data/raw/pdf/AtI-annual-report-2012.pdf", [0, 2]),
    ("data/raw/pdf/AtI-annual-report-2014.pdf", [1]),
    ("data/raw/pdf/2604.27415v1.pdf", [0]),
    ("data/raw/pdf/Python-tutorial-pdf2.pdf", [2, 3]),
    ("data/raw/pdf/FAO_EMSTOT.pdf", [1]),
    ("data/raw/pdf/WB_CLEAR.pdf", [1]),
    ("data/raw/pdf/Access-to-Information-2016-annual-report.pdf", [0]),
    ("data/raw/pdf/worldbankSECBOS-8b71cac3-074c-43c1-ac8c-c3b5fc34cb5b.pdf", [0]),
    ("data/raw/pdf/2605.02520v1.pdf", [0]),
    ("data/raw/pdf/Access-to-Information-2023-annual-report.pdf", [2]),
    ("data/raw/pdf/Python-tutorial-pdf1.pdf", [2]),
]

if __name__ == "__main__":
    for path, page_list in targets:
        if os.path.exists(path):
            read_pages(path, page_list)
