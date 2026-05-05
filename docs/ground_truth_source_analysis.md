# Ground Truth Source Analysis
**ByteMonk | Project 02 | Pre-Phase 1 Activity**

## Overview
This document tracks which files from `@data/raw` were utilized to generate the initial **25 Ground Truth QA pairs** (Track A). 

**Total Files in Corpus**: 33  
**Files Analyzed for QA**: 10  
**Status**: Initial batch (25/60) complete.

## Analysis Summary Table

| Filename | Domain | Pages | QA Pairs Generated | Key Topics Covered |
| :--- | :--- | :--- | :--- | :--- |
| `Access-to-Information-2023-annual-report.pdf` | Financial | 11 | 3 | FY23 metrics, page views, data indicators. |
| `2605.02520v1.pdf` | Academic | 15 | 3 | RAG benchmarking, DeepEval metrics, retrieval strategies. |
| `Python-tutorial-pdf1.pdf` | Technical | ~100 | 4 | Author, Release date, Control flow, Coding style. |
| `AtI-annual-report-2012.pdf` | Financial | 80 | 2 | Transparency theme, data accuracy disclaimers. |
| `AtI-annual-report-2014.pdf` | Financial | 84 | 1 | Rights and permissions contact info. |
| `2604.27415v1.pdf` | Academic | 22 | 2 | ChipLingo framework, EDA-Bench accuracy. |
| `Python-tutorial-pdf2.pdf` | Technical | 139 | 2 | Function definitions, Web pages. |
| `FAO_EMSTOT.pdf` | Academic | 10 | 2 | Greenhouse gas types, IPCC global warming potentials. |
| `WB_CLEAR.pdf` | Technical | 17 | 2 | CLEAR Water Dashboard purpose, generation date. |
| `Access-to-Information-2016-annual-report.pdf` | Financial | 7 | 2 | ATI Policy 6th year anniversary, WBG Finances. |
| `worldbankSECBOS-8b71cac3...pdf` | Financial | 67 | 2 | President Ajay Banga, 2025 Fiscal Year period. |

## Clarification on Coverage
We did **not** read all 33 documents for question generation. To meet the "Track A" milestone efficiently, we focused on 10 representative documents that span all three required domains (`financial`, `academic`, `technical`). 

The remaining 23 documents were:
1.  **Audited** (for structure/parsing issues) in `docs/audit_pre_phase.md`.
2.  **Reserved** for generating the remaining 35-45 QA pairs during Phase 1 development to ensure the dataset covers the full breadth of the corpus.

---
*Last Updated: May 2026*
