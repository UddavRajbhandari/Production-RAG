
import json
import os

ground_truth_path = "data/ground_truth/ground_truth.json"

hardened_pairs = [
    {
        "question_id": "gt_001",
        "question": "What period does the fiscal year 2023 (FY23) cover in the World Bank Access to Information report?",
        "ground_truth_answer": "In the World Bank Access to Information report, fiscal year 2023 (FY23) refers to the period beginning on July 1, 2022, and ending on June 30, 2023. During this period, the Bank continued its commitment to transparency and accountability through the rigorous implementation of its Access to Information (ATI) Policy.",
        "ground_truth_chunk_ids": [],
        "source_document": "Access-to-Information-2023-annual-report.pdf",
        "domain_tag": "financial"
    },
    {
        "question_id": "gt_002",
        "question": "How many page views were recorded for the World Bank's Open Data in the FY23 Access to Information report?",
        "ground_truth_answer": "According to the FY23 Access to Information report, the World Bank's Open Data initiatives recorded over 114 million page views. Additionally, the report notes over 15,700 available development datasets, indicators, and visualizations, with total downloads exceeding 2.5 million.",
        "ground_truth_chunk_ids": [],
        "source_document": "Access-to-Information-2023-annual-report.pdf",
        "domain_tag": "financial"
    },
    {
        "question_id": "gt_003",
        "question": "Which retrieval strategy achieved the best composite score in the benchmarking study for biomedical RAG?",
        "ground_truth_answer": "The benchmarking study for biomedical RAG found that Cross-Encoder Reranking achieved the best composite score of 0.827. It also attained the highest contextual precision (0.852), which confirms that detailed query-document interaction yields significant and measurable retrieval gains in high-stakes domains like biomedicine.",
        "ground_truth_chunk_ids": [],
        "source_document": "2605.02520v1.pdf",
        "domain_tag": "academic"
    },
    {
        "question_id": "gt_004",
        "question": "What are the four DeepEval metrics used in the evaluation framework of the biomedical RAG study?",
        "ground_truth_answer": "The evaluation framework utilized in the study is built on four DeepEval metrics: (1) contextual precision, which measures the signal-to-noise ratio in the retrieved context; (2) contextual recall, which assesses the coverage of necessary evidence; (3) faithfulness, which checks the factual consistency of the generated answer with the provided context; and (4) answer relevancy, which evaluates how well the answer addresses the original question.",
        "ground_truth_chunk_ids": [],
        "source_document": "2605.02520v1.pdf",
        "domain_tag": "academic"
    },
    {
        "question_id": "gt_005",
        "question": "Who is listed as the primary author of the Python 3.7.0 Tutorial released on September 02, 2018?",
        "ground_truth_answer": "The primary author of the Python 3.7.0 Tutorial, released on September 02, 2018, by the Python Software Foundation, is Guido van Rossum, assisted by the Python development team.",
        "ground_truth_chunk_ids": [],
        "source_document": "Python-tutorial-pdf1.pdf",
        "domain_tag": "technical"
    },
    {
        "question_id": "gt_010",
        "question": "What is ChipLingo and what are its three primary stages of training?",
        "ground_truth_answer": "ChipLingo is a systematic training pipeline for domain-adapted large language models (LLMs) specifically tailored for Electronic Design Automation (EDA) scenarios. It addresses challenges such as insufficient domain expertise and cross-tool knowledge confusion through three stages: (1) multi-source data curation and QA augmentation to construct domain-specific corpora, (2) domain-adaptive pretraining to optimize parameter training strategies, and (3) instruction alignment and RAG scenario training to improve the model's ability to leverage external knowledge.",
        "ground_truth_chunk_ids": [],
        "source_document": "2604.27415v1.pdf",
        "domain_tag": "academic"
    },
    {
        "question_id": "gt_014",
        "question": "Which greenhouse gases are included in the FAOSTAT 'Emissions Totals' domain?",
        "ground_truth_answer": "The FAOSTAT 'Emissions Totals' domain includes methane (CH4), nitrous oxide (N2O), and carbon dioxide (CO2) emissions generated from agrifood systems. Additionally, it disseminates aggregate fluorinated gases (F-gases) emissions used in various industrial processes.",
        "ground_truth_chunk_ids": [],
        "source_document": "FAO_EMSTOT.pdf",
        "domain_tag": "academic"
    },
    {
        "question_id": "gt_016",
        "question": "What is the primary purpose of the CLEAR Water Dashboard?",
        "ground_truth_answer": "The primary purpose of the CLEAR Water Dashboard is to support Water teams in informing the standardized diagnostic framework for Climate and Economic Analyses of Resilience (CLEAR) in Water within Country Climate and Development Reports. It achieves this by curating and assembling more than twenty global datasets from recognized institutions.",
        "ground_truth_chunk_ids": [],
        "source_document": "WB_CLEAR.pdf",
        "domain_tag": "technical"
    },
    {
        "question_id": "gt_020",
        "question": "Who is the President of the World Bank Group listed in the 2025 Annual Report?",
        "ground_truth_answer": "As listed in the World Bank Group Annual Report 2025, Ajay Banga is the President of the World Bank Group and Chairman of the Board of Executive Directors. He submitted the report, budgets, and financial statements to the Board of Governors.",
        "ground_truth_chunk_ids": [],
        "source_document": "worldbankSECBOS-8b71cac3-074c-43c1-ac8c-c3b5fc34cb5b.pdf",
        "domain_tag": "financial"
    },
    {
        "question_id": "gt_025",
        "question": "In the Python tutorial, what is the purpose of section 4.1 'if Statements'?",
        "ground_truth_answer": "Section 4.1 of the Python tutorial introduces 'if statements', which are described as perhaps the most well-known statement type for control flow. They are used for conditional execution, allowing the program to execute different blocks of code based on whether a specific condition evaluates to true.",
        "ground_truth_chunk_ids": [],
        "source_document": "Python-tutorial-pdf1.pdf",
        "domain_tag": "technical"
    }
]

# Update existing json with hardened answers (matching by ID)
with open(ground_truth_path, 'r') as f:
    all_pairs = json.load(f)

# Create a map for easy updates
hardened_map = {p["question_id"]: p["ground_truth_answer"] for p in hardened_pairs}

for pair in all_pairs:
    if pair["question_id"] in hardened_map:
        pair["ground_truth_answer"] = hardened_map[pair["question_id"]]

with open(ground_truth_path, 'w') as f:
    json.dump(all_pairs, f, indent=2)

print(f"Hardened {len(hardened_pairs)} Ground Truth answers.")
