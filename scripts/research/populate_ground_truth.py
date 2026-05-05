
import json
import os

ground_truth_path = "data/ground_truth/ground_truth.json"

initial_pairs = [
    {
        "question_id": "gt_001",
        "question": "What period does the fiscal year 2023 (FY23) cover in the World Bank Access to Information report?",
        "ground_truth_answer": "Fiscal year 2023 (FY23) covers the period from July 1, 2022, to June 30, 2023.",
        "ground_truth_chunk_ids": [],
        "source_document": "Access-to-Information-2023-annual-report.pdf",
        "domain_tag": "financial"
    },
    {
        "question_id": "gt_002",
        "question": "How many page views were recorded for the World Bank's Open Data in the FY23 Access to Information report?",
        "ground_truth_answer": "Over 114 million page views.",
        "ground_truth_chunk_ids": [],
        "source_document": "Access-to-Information-2023-annual-report.pdf",
        "domain_tag": "financial"
    },
    {
        "question_id": "gt_003",
        "question": "Which retrieval strategy achieved the best composite score in the benchmarking study for biomedical RAG?",
        "ground_truth_answer": "Cross-Encoder Reranking achieved the best composite score of 0.827.",
        "ground_truth_chunk_ids": [],
        "source_document": "2605.02520v1.pdf",
        "domain_tag": "academic"
    },
    {
        "question_id": "gt_004",
        "question": "What are the four DeepEval metrics used in the evaluation framework of the biomedical RAG study?",
        "ground_truth_answer": "The four DeepEval metrics are contextual precision, contextual recall, faithfulness, and answer relevancy.",
        "ground_truth_chunk_ids": [],
        "source_document": "2605.02520v1.pdf",
        "domain_tag": "academic"
    },
    {
        "question_id": "gt_005",
        "question": "Who is listed as the primary author of the Python 3.7.0 Tutorial released on September 02, 2018?",
        "ground_truth_answer": "Guido van Rossum (and the Python development team).",
        "ground_truth_chunk_ids": [],
        "source_document": "Python-tutorial-pdf1.pdf",
        "domain_tag": "technical"
    },
    {
        "question_id": "gt_006",
        "question": "According to the Python 3.7.0 tutorial contents, which section covers 'Using the Python Interpreter'?",
        "ground_truth_answer": "Section 2 covers 'Using the Python Interpreter'.",
        "ground_truth_chunk_ids": [],
        "source_document": "Python-tutorial-pdf1.pdf",
        "domain_tag": "technical"
    }
]

with open(ground_truth_path, 'w') as f:
    json.dump(initial_pairs, f, indent=2)

print(f"Initialized {len(initial_pairs)} QA pairs in {ground_truth_path}")
