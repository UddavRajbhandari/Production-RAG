
import json
import os

ground_truth_path = "data/ground_truth/ground_truth.json"

# Load existing pairs
with open(ground_truth_path, 'r') as f:
    pairs = json.load(f)

# Define the next 19 pairs based on the analysis
new_pairs = [
    # --- AtI-annual-report-2012.pdf (Financial) ---
    {
        "question_id": "gt_007",
        "question": "What is the theme of the World Bank's Access to Information Annual Report for FY 2012?",
        "ground_truth_answer": "The theme is 'Moving Forward Transparency and Accountability'.",
        "ground_truth_chunk_ids": [],
        "source_document": "AtI-annual-report-2012.pdf",
        "domain_tag": "financial"
    },
    {
        "question_id": "gt_008",
        "question": "Does the World Bank guarantee the accuracy of the data included in the FY 2012 Access to Information report?",
        "ground_truth_answer": "No, the report states that 'The World Bank does not guarantee the accuracy of the data included in this work'.",
        "ground_truth_chunk_ids": [],
        "source_document": "AtI-annual-report-2012.pdf",
        "domain_tag": "financial"
    },
    # --- AtI-annual-report-2014.pdf (Financial) ---
    {
        "question_id": "gt_009",
        "question": "Who should be contacted for queries on rights and licenses for the FY 2014 Access to Information report?",
        "ground_truth_answer": "Queries should be addressed to World Bank Publications, e-mail: pubrights@worldbank.org.",
        "ground_truth_chunk_ids": [],
        "source_document": "AtI-annual-report-2014.pdf",
        "domain_tag": "financial"
    },
    # --- 2604.27415v1.pdf (Academic) ---
    {
        "question_id": "gt_010",
        "question": "What is ChipLingo and what are its three primary stages of training?",
        "ground_truth_answer": "ChipLingo is a systematic training pipeline for domain-adapted LLMs tailored to EDA. Its three stages are: (1) domain-specific corpora construction, (2) domain-adaptive pretraining, and (3) instruction alignment and RAG scenario training.",
        "ground_truth_chunk_ids": [],
        "source_document": "2604.27415v1.pdf",
        "domain_tag": "academic"
    },
    {
        "question_id": "gt_011",
        "question": "What accuracy did ChipLingo-32B achieve on the EDA-Bench benchmark?",
        "ground_truth_answer": "ChipLingo-32B achieved 70.02% accuracy on EDA-Bench.",
        "ground_truth_chunk_ids": [],
        "source_document": "2604.27415v1.pdf",
        "domain_tag": "academic"
    },
    # --- Python-tutorial-pdf2.pdf (Technical) ---
    {
        "question_id": "gt_012",
        "question": "In 'Hands-On Python' by Dr. Andrew Harrington, what is covered in section 1.11 of Chapter 1?",
        "ground_truth_answer": "Section 1.11 covers 'Defining Functions of your Own'.",
        "ground_truth_chunk_ids": [],
        "source_document": "Python-tutorial-pdf2.pdf",
        "domain_tag": "technical"
    },
    {
        "question_id": "gt_013",
        "question": "Which chapter in 'Hands-On Python' covers 'Dynamic Web Pages'?",
        "ground_truth_answer": "Chapter 4 covers 'Dynamic Web Pages'.",
        "ground_truth_chunk_ids": [],
        "source_document": "Python-tutorial-pdf2.pdf",
        "domain_tag": "technical"
    },
    # --- FAO_EMSTOT.pdf (Academic/Financial) ---
    {
        "question_id": "gt_014",
        "question": "Which greenhouse gases are included in the FAOSTAT 'Emissions Totals' domain?",
        "ground_truth_answer": "The domain includes methane (CH4), nitrous oxide (N2O), carbon dioxide (CO2), and aggregate fluorinated gases (F-gases).",
        "ground_truth_chunk_ids": [],
        "source_document": "FAO_EMSTOT.pdf",
        "domain_tag": "academic"
    },
    {
        "question_id": "gt_015",
        "question": "What global warming potentials are used to compute CO2 equivalent units in the FAOSTAT emissions database?",
        "ground_truth_answer": "They are computed using the IPCC Fifth Assessment report (AR5) global warming potentials from 2014.",
        "ground_truth_chunk_ids": [],
        "source_document": "FAO_EMSTOT.pdf",
        "domain_tag": "academic"
    },
    # --- WB_CLEAR.pdf (Technical/Financial) ---
    {
        "question_id": "gt_016",
        "question": "What is the primary purpose of the CLEAR Water Dashboard?",
        "ground_truth_answer": "The CLEAR Water Dashboard aims to support Water teams in informing the standardized diagnostic framework for Climate and Economic Analyses of Resilience in Water in Country Climate and Development Reports.",
        "ground_truth_chunk_ids": [],
        "source_document": "WB_CLEAR.pdf",
        "domain_tag": "technical"
    },
    {
        "question_id": "gt_017",
        "question": "When was the report for 'Climate and Economic Analyses for Resilience in Water' (CLEAR Water) generated?",
        "ground_truth_answer": "The report was generated on August 27, 2025.",
        "ground_truth_chunk_ids": [],
        "source_document": "WB_CLEAR.pdf",
        "domain_tag": "technical"
    },
    # --- Access-to-Information-2016-annual-report.pdf (Financial) ---
    {
        "question_id": "gt_018",
        "question": "Which date marked the end of the sixth year of implementation of the World Bank's Access to Information Policy?",
        "ground_truth_answer": "June 30, 2016.",
        "ground_truth_chunk_ids": [],
        "source_document": "Access-to-Information-2016-annual-report.pdf",
        "domain_tag": "financial"
    },
    {
        "question_id": "gt_019",
        "question": "What is the function of 'World Bank Group Finances' as described in the FY2016 report?",
        "ground_truth_answer": "It makes data related to the WBG’s financials available to everybody in a social, interactive, visually compelling, and machine readable format.",
        "ground_truth_chunk_ids": [],
        "source_document": "Access-to-Information-2016-annual-report.pdf",
        "domain_tag": "financial"
    },
    # --- worldbankSECBOS-8b71cac3-074c-43c1-ac8c-c3b5fc34cb5b.pdf (Financial) ---
    {
        "question_id": "gt_020",
        "question": "Who is the President of the World Bank Group listed in the 2025 Annual Report?",
        "ground_truth_answer": "Ajay Banga.",
        "ground_truth_chunk_ids": [],
        "source_document": "worldbankSECBOS-8b71cac3-074c-43c1-ac8c-c3b5fc34cb5b.pdf",
        "domain_tag": "financial"
    },
    {
        "question_id": "gt_021",
        "question": "What period is covered by the World Bank Group Annual Report 2025?",
        "ground_truth_answer": "The period from July 1, 2024, to June 30, 2025.",
        "ground_truth_chunk_ids": [],
        "source_document": "worldbankSECBOS-8b71cac3-074c-43c1-ac8c-c3b5fc34cb5b.pdf",
        "domain_tag": "financial"
    },
    # --- Additional Academic pairs from 2605.02520v1.pdf ---
    {
        "question_id": "gt_022",
        "question": "Which retrieval strategy achieved the weakest contextual precision in the BioASQ benchmarking study?",
        "ground_truth_answer": "Multi-Query Expansion produced the weakest contextual precision (0.671).",
        "ground_truth_chunk_ids": [],
        "source_document": "2605.02520v1.pdf",
        "domain_tag": "academic"
    },
    # --- Additional Financial pairs from 2023 report ---
    {
        "question_id": "gt_023",
        "question": "How many available development datasets, indicators, and visualizations were cited in the FY23 ATI report?",
        "ground_truth_answer": "Over 15,700.",
        "ground_truth_chunk_ids": [],
        "source_document": "Access-to-Information-2023-annual-report.pdf",
        "domain_tag": "financial"
    },
    # --- Additional Technical pairs from Python-tutorial-pdf1.pdf ---
    {
        "question_id": "gt_024",
        "question": "Which section of the Python 3.7.0 tutorial discusses 'Coding Style'?",
        "ground_truth_answer": "Section 4.8, titled 'Intermezzo: Coding Style'.",
        "ground_truth_chunk_ids": [],
        "source_document": "Python-tutorial-pdf1.pdf",
        "domain_tag": "technical"
    },
    {
        "question_id": "gt_025",
        "question": "In the Python tutorial, what is the purpose of section 4.1 'if Statements'?",
        "ground_truth_answer": "It discusses the control flow tool used for conditional execution.",
        "ground_truth_chunk_ids": [],
        "source_document": "Python-tutorial-pdf1.pdf",
        "domain_tag": "technical"
    }
]

# Append and save
all_pairs = pairs + new_pairs
with open(ground_truth_path, 'w') as f:
    json.dump(all_pairs, f, indent=2)

print(f"Total QA pairs now: {len(all_pairs)}")
