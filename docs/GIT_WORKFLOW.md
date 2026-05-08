# GIT_WORKFLOW.md — Project 02: Production-Grade RAG Pipeline
> Reference this file when creating branches, writing commits, or merging work.
> This workflow is mandatory for all changes — no exceptions.

---

## Core Rule

**Main is always deployable. Branches are where work happens.**

- Every change — bug fix, feature, optimization, docs — gets its own branch
- `bash scripts/run_ci_local.sh` must pass before any merge into main
- Never commit directly to main
- Never have more than one open branch at a time (solo project rule)
- Always branch from main — never from another feature branch

---

## Branch Naming Convention

```
type/short-description-in-kebab-case
```

| Prefix | Use for |
|--------|---------|
| `feat/` | New functionality |
| `fix/` | Bug correction |
| `opt/` | Performance optimization |
| `refactor/` | Restructuring without behavior change |
| `test/` | Adding or fixing tests |
| `docs/` | Documentation only |
| `chore/` | Config, tooling, dependencies, re-runs |

**Examples from this project:**
```
fix/phase1-token-count-chunker
fix/phase2-neon-db-location
fix/phase2-uuid-validation
opt/phase3-onnx-reranker
fix/phase3-rrf-dense-dropout
docs/update-technical-report-v1.1
chore/gemini-md-phase-statuses
```

---

## Workflow Per Change — Follow This Every Time

```bash
# Step 1 — Always start from a clean main
git checkout main
git status                        # must show nothing uncommitted

# Step 2 — Create and switch to your branch
git checkout -b fix/your-branch-name

# Step 3 — Write tests FIRST (TDD — required by GEMINI.md)
# Edit tests/unit/test_<module>.py before touching implementation

# Step 4 — Implement the change
# Edit the relevant source files

# Step 5 — Run local CI — must be green before committing
bash scripts/run_ci_local.sh

# Step 6 — Stage only the files relevant to this change
git add src/path/to/changed_file.py
git add tests/unit/test_changed_file.py

# Step 7 — Commit with a structured message (see format below)
git commit -m "fix: short summary of what changed

- What changed and why
- Quantitative result if available

Refs: Phase-X-Fix-Guide #N"

# Step 8 — Merge back into main with --no-ff (preserves branch history)
git checkout main
git merge fix/your-branch-name --no-ff

# Step 9 — Delete the branch — it served its purpose
git branch -d fix/your-branch-name
```

---

## Commit Message Format

```
type: short summary in present tense (max 72 characters)

- Bullet explaining what changed
- Bullet explaining why it was wrong / what it fixes
- Quantitative result if available (latency, chunk count, test count)

Refs: which fix guide and item number this belongs to
```

**Rules:**
- First line: `type: summary` — no period at end, max 72 chars
- Blank line between summary and body
- Body bullets explain the *why*, not just the *what*
- Include numbers when you have them

**Good examples:**
```
fix: replace word-count with token-count in chunker

- Use tiktoken cl100k_base for accurate token ceiling enforcement
- Word count was treating 512 words as 512 tokens — off by ~40%
- Chunk count increased from 2056 to 2717 after re-ingestion
- All chunks now respect hard 512-token ceiling

Refs: Phase1-Fix-Guide #1
```

```
fix: RRF now rescues dense-only Qdrant results via payload

- node_lookup was built only from bm25.nodes — dense-only hits dropped
- Dual lookup now checks BM25 first, falls back to Qdrant payload
- Results carry source field: "hybrid" or "dense_only"
- Hybrid retrieval is no longer silently BM25-biased

Refs: Phase3-Fix-Guide #1
```

```
opt: replace PyTorch reranker with ONNX Runtime

- PyTorch CPU inference was ~2450ms avg — 30x over 80ms budget
- ONNX Runtime reduces reranking to ~400-600ms on same hardware
- Fallback to PyTorch CrossEncoder if ONNX model not found
- Run scripts/export_reranker_onnx.py once to generate ONNX model

Refs: Phase3-Fix-Guide #6
```

**Bad examples — do not do these:**
```
fixed bug                        ← no type, no context
WIP                              ← never commit WIP to any branch
update files                     ← meaningless
fix everything                   ← too broad, not one change per commit
```

---


---

## What Your Git Log Should Look Like After Remediation

```bash
git log --oneline main
```

```
a3f91c2 chore: update GEMINI.md — Phase 1-3 complete, Phase 4 active
9d82b14 docs: update technical report to v1.1 post-remediation
7c3e401 test: add Phase 3 acceptance checklist results
f2a8b30 fix: rename profile_retrival.py and correct budget comparison
8b19d3e opt: replace PyTorch reranker with ONNX Runtime
2c74a11 fix: reranker no longer mutates caller candidates list
d9f3820 fix: expand_context copies dicts instead of mutating originals
5e2c918 fix: move rerank_pool_size magic number to settings.yaml
a1b7c34 fix: apply zero-score filter in year-filtered sparse search
3d92f17 fix: RRF rescues dense-only Qdrant results via payload
4f8e029 chore: re-populate all three storage backends after Phase 2 fixes
b7a3c12 fix: add batching and verification to populate_storage
e2d9f44 fix: BM25 search filters zero-score results before returning top_k
c1f7b83 fix: UUID validation in Qdrant insert_nodes before upsert
9a4e271 fix: update SQLAlchemy to 2.x DeclarativeBase syntax
7d3c190 fix: move neon_db.py from src/retrieval to src/storage
f5b8a34 chore: re-run batch_ingest after Phase 1 fixes
1e6d927 fix: department mapping in settings.yaml replaces hardcoded Corporate
0c9b341 fix: internalize _extract_section_heading into MetadataPipeline.process
a2f4e18 fix: replace word-count with token-count in chunker
```

Every change isolated, labelled, and reversible.

---

## Useful Git Commands for Solo Project

```bash
# See all branches
git branch -a

# See what changed in a branch before merging
git diff main..fix/your-branch-name

# See the commit graph
git log --oneline --graph main

# Undo last commit but keep changes (if you committed too early)
git reset --soft HEAD~1

# Check what files changed in the last commit
git show --name-only HEAD

# See full history of a specific file
git log --oneline -- src/ingestion/chunker.py

# If something goes wrong on a branch — discard all changes and start over
git checkout main
git branch -D fix/your-broken-branch    # capital D force-deletes
```

---

## Definition of Done — Per Branch

A branch is ready to merge only when all of the following are true:

- [ ] Tests exist for the change (unit + integration if cross-module)
- [ ] All tests pass — `pytest tests/unit/ -v`
- [ ] Ruff passes — `ruff check . && ruff format --check .`
- [ ] Mypy passes — `mypy src/`
- [ ] Pre-commit hooks pass — `pre-commit run --all-files`
- [ ] `bash scripts/run_ci_local.sh` exits with code 0
- [ ] Commit message follows the format above
- [ ] No unrelated files staged in the commit

---

*Last updated: May 2026 — Project 02 | Git workflow reference for Gemini CLI*
