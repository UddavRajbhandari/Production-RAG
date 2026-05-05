
import fitz
import os

def extract_sample(file_path, pages=[0, 1, 2]):
    print(f"\n=== Sample from {os.path.basename(file_path)} ===")
    try:
        doc = fitz.open(file_path)
        for p in pages:
            if p < len(doc):
                print(f"--- Page {p+1} ---")
                print(doc[p].get_text())
        doc.close()
    except Exception as e:
        print(f"Error: {e}")

# Sample files
samples = [
    "data/raw/pdf/Access-to-Information-2023-annual-report.pdf",
    "data/raw/pdf/2605.02520v1.pdf",
    "data/raw/pdf/Python-tutorial-pdf1.pdf"
]

for s in samples:
    extract_sample(s)
