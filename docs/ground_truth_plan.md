# Ground Truth Dataset — Construction Plan
**ByteMonk | Project 02 | Pre-Phase 1 Artifact**
*Version 1.0 — May 2026*

---

## Purpose

This document formalizes the ground truth dataset construction workflow for the RAGAS
evaluation layer. It is a prerequisite for Phase 6, not a Phase 6 deliverable.
Construction runs in parallel with Phase 1 ingestion.

> **Critical constraint from v1.1:** Do not build QA pairs from naive chunking output.
> Wait until structure-aware chunking is validated in Phase 1 before populating
> `ground_truth_chunk_ids`. Building retroactively risks chunk ID misalignment.

---

## The Two-Track Workflow

Construction is split into two tracks to resolve the timing constraint: chunk IDs
cannot be assigned before Phase 1 chunking is validated, but question and answer
writing can — and must — begin immediately.

---

## Track A — Do Now (Before / During Phase 1)

### Step 1: Establish the Schema

Create `/data/ground_truth/ground_truth.json` with the following structure.
The file should be initialized as an empty array and populated incrementally.

```json
[
  {
    "question_id": "gt_001",
    "question": "",
    "ground_truth_answer": "",
    "ground_truth_chunk_ids": [],
    "source_document": "",
    "domain_tag": ""
  }
]
```

**Field definitions:**

| Field | Type | Description |
|---|---|---|
| `question_id` | string | Unique identifier, format: `gt_NNN` (zero-padded) |
| `question` | string | Realistic natural language query a user would ask |
| `ground_truth_answer` | string | Correct answer in natural language |
| `ground_truth_chunk_ids` | array | Source chunk IDs — **leave empty in Track A** |
| `source_document` | string | Filename of the source document |
| `domain_tag` | string | One of: `financial`, `academic`, `technical` |

The `domain_tag` field is added beyond v1.1's minimum spec. It enables post-hoc
RAGAS score analysis by document type — a useful diagnostic given the corpus
diversity surfaced in the pre-Phase 1 audit.

---

### Step 2: Write Questions and Answers

Target **60–70 QA pairs** at this stage (buffer above the 50-pair minimum; some
pairs will be discarded in Track B if they cannot be mapped to a specific chunk).

Questions must reflect realistic user queries against the actual corpus. Do not
write synthetic or generic prompts.

**Distribution target across domain tags:**

| Domain | Count | Rationale |
|---|---|---|
| `financial` | ~25 | Annual reports and financial docs — high table density per audit |
| `academic` | ~25 | ArXiv papers — high text density, conceptual queries |
| `technical` | ~15 | Tutorial files — procedural, step-by-step queries |

This distribution is grounded in the corpus audit findings. The three document
types have fundamentally different structural characteristics and will likely
produce different RAGAS scores — domain tagging surfaces that signal.

**Question quality checklist (per pair):**
- [ ] Would a real user plausibly ask this against this corpus?
- [ ] Is the answer fully contained within a single document?
- [ ] Is the answer specific enough to map to a discrete chunk later?
- [ ] Does the question avoid referencing chunk boundaries or internal structure?

---

### Step 3: Write and Run the Validation Script

Create `/src/evaluation/validate_ground_truth.py` before Track B begins.
Run it now against the incomplete dataset to confirm tooling works.

```python
import json
import sys

def validate(path: str) -> None:
    with open(path) as f:
        pairs = json.load(f)

    errors = []
    seen_ids = set()

    for i, pair in enumerate(pairs):
        qid = pair.get("question_id", f"[index {i}]")

        if qid in seen_ids:
            errors.append(f"{qid}: duplicate question_id")
        seen_ids.add(qid)

        if not pair.get("question", "").strip():
            errors.append(f"{qid}: empty question")

        if not pair.get("ground_truth_answer", "").strip():
            errors.append(f"{qid}: empty ground_truth_answer")

        if pair.get("domain_tag") not in {"financial", "academic", "technical"}:
            errors.append(f"{qid}: invalid domain_tag '{pair.get('domain_tag')}'")

    # Track B check — only warn, not error, on empty chunk IDs
    empty_chunks = [p["question_id"] for p in pairs if not p.get("ground_truth_chunk_ids")]
    if empty_chunks:
        print(f"WARNING: {len(empty_chunks)} pairs have no chunk IDs yet (expected in Track A).")

    if errors:
        print(f"VALIDATION FAILED — {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print(f"VALIDATION PASSED — {len(pairs)} pairs, {len(empty_chunks)} pending chunk IDs.")

if __name__ == "__main__":
    validate(sys.argv[1] if len(sys.argv) > 1 else "data/ground_truth/ground_truth.json")
```

Run as: `python src/evaluation/validate_ground_truth.py`

---

## Track B — Do After Phase 1 Chunking is Validated

### Step 4: Map Chunk IDs

Once the Phase 1 milestone is reached (50 chunks manually sampled and validated),
return to each QA pair and populate `ground_truth_chunk_ids` by locating which
chunks contain the evidence for each answer.

**Labor estimate:** 5–10 minutes per pair × 60 pairs = **5–10 hours of annotation**.
Budget this explicitly. Do not compress it into the Phase 5–6 transition.

**Annotation rules:**
- A pair must have at least one chunk ID — pairs with no traceable chunk are discarded
- A pair may reference multiple chunk IDs if the answer spans more than one chunk
- Chunk IDs must match the IDs assigned by the chunker in Phase 1 exactly —
  copy them, do not reconstruct from memory

---

### Step 5: Final Validation and Discard Pass

Re-run `validate_ground_truth.py`. At this stage, any pair with an empty
`ground_truth_chunk_ids` array is a discard candidate.

**Acceptance criteria before Phase 6:**
- [ ] Minimum 50 pairs remaining after discards
- [ ] Zero pairs with empty `question`, `ground_truth_answer`, or `ground_truth_chunk_ids`
- [ ] Zero duplicate `question_id` values
- [ ] All `domain_tag` values are valid
- [ ] Validation script exits with code 0

If discards push the total below 50, return to Step 2 and write additional pairs
targeting the deficit domain.

---

## File Layout

```
/data/ground_truth/
  ground_truth.json        # Primary dataset (JSON, append-only during Track A)
  ground_truth.csv         # CSV mirror (optional, for spreadsheet review)

/src/evaluation/
  validate_ground_truth.py # Validation script (written in Track A, Step 3)
```

---

## Track A / Track B Checklist

| Task | Track | Status |
|---|---|---|
| Schema defined and file initialized | A | ☐ |
| 60–70 questions written | A | ☐ |
| 60–70 answers written | A | ☐ |
| Validation script written and passing | A | ☐ |
| Phase 1 chunking milestone reached | — | ☐ |
| Chunk IDs mapped for all pairs | B | ☐ |
| Pairs without chunk IDs discarded | B | ☐ |
| Final validation passing (≥50 pairs) | B | ☐ |

---

*Document prepared May 2026 | ByteMonk — Project 02 | Pre-Phase 1 Artifact*
*All targets are engineering goals, not guaranteed outcomes.*
