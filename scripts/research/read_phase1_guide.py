"""
Phase 1 Guide Reader
Small utility script to extract text from the Word-based implementation guide.
Used to bootstrap project requirements during the research phase.
"""

import os

import docx


def read_guide() -> None:
    """Reads the implementation guide and prints its content."""
    file_path = "docs/phase 1/Phase1_Implementation_Guide.docx"
    if os.path.exists(file_path):
        doc = docx.Document(file_path)
        full_text = []
        for para in doc.paragraphs:
            full_text.append(para.text)
        print("\n".join(full_text))
    else:
        print(f"File not found: {file_path}")


if __name__ == "__main__":
    read_guide()
