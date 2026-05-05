
import fitz
import docx
import os

def analyze_document(file_path):
    print(f"\n{'='*60}")
    print(f"ANALYZING: {os.path.basename(file_path)}")
    print(f"{'='*60}")
    try:
        if file_path.endswith(".pdf"):
            doc = fitz.open(file_path)
            # Sample pages 1-5 for better context
            text = ""
            for i in range(min(5, len(doc))):
                text += doc[i].get_text() + "\n"
            print(text[:2000]) # Limit output but get enough for QA
            doc.close()
        elif file_path.endswith(".docx"):
            doc = docx.Document(file_path)
            text = "\n".join([p.text for p in doc.paragraphs[:20]])
            print(text[:2000])
    except Exception as e:
        print(f"Error: {e}")

# Target files for the final batch to reach 25
targets = [
    "data/raw/pdf/AtI-annual-report-2012.pdf",
    "data/raw/pdf/AtI-annual-report-2014.pdf",
    "data/raw/pdf/2604.27415v1.pdf",
    "data/raw/pdf/Python-tutorial-pdf2.pdf",
    "data/raw/pdf/FAO_EMSTOT.pdf",
    "data/raw/pdf/WB_CLEAR.pdf",
    "data/raw/pdf/Access-to-Information-2016-annual-report.pdf",
    "data/raw/pdf/worldbankSECBOS-8b71cac3-074c-43c1-ac8c-c3b5fc34cb5b.pdf"
]

for t in targets:
    analyze_document(t)
