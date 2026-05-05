
import fitz
import docx
import os

def read_pages(file_path, pages):
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
            # Find relevant text based on keywords if needed, but for now just first few paragraphs
            print("\n".join([p.text for p in doc.paragraphs[:50]]))
    except Exception as e:
        print(f"Error: {e}")

# Verification targets for the remaining 15 pairs
targets = [
    ("data/raw/pdf/Python-tutorial-pdf1.pdf", [2]), # gt_006
    ("data/raw/pdf/AtI-annual-report-2012.pdf", [0, 2]), # gt_007, gt_008
    ("data/raw/pdf/AtI-annual-report-2014.pdf", [1]), # gt_009
    ("data/raw/pdf/2604.27415v1.pdf", [0]), # gt_011
    ("data/raw/pdf/Python-tutorial-pdf2.pdf", [2, 3]), # gt_012, gt_013
    ("data/raw/pdf/FAO_EMSTOT.pdf", [1]), # gt_015
    ("data/raw/pdf/WB_CLEAR.pdf", [1]), # gt_017
    ("data/raw/pdf/Access-to-Information-2016-annual-report.pdf", [0]), # gt_018, gt_019
    ("data/raw/pdf/worldbankSECBOS-8b71cac3-074c-43c1-ac8c-c3b5fc34cb5b.pdf", [0]), # gt_021
    ("data/raw/pdf/2605.02520v1.pdf", [0]), # gt_022
    ("data/raw/pdf/Access-to-Information-2023-annual-report.pdf", [2]), # gt_023
    ("data/raw/pdf/Python-tutorial-pdf1.pdf", [2]) # gt_024
]

for path, pages in targets:
    if os.path.exists(path):
        read_pages(path, pages)
