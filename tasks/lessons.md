# Lessons

## 2026-10-05 — Model choice is a validated Enum, decided before benchmarking

**What happened:** at the start of phase 2, I began downloading and comparing embedding models
before the plan said how a model is chosen.

**Rule:**
- Every model-backed component (embedder, language detector, LLM) gets a `<Kind>Model`
  `StrEnum` that lists every option, deterministic stand-ins included (e.g. `HASHING`).
- The model is selected by an environment variable (`KRTR_IA_<KIND>_MODEL`) or a CLI option
  typed with that Enum, so an unknown name fails validation.
- A factory maps each member to its implementation. One or two members is enough.
- This goes into the plan first; downloads and benchmarks come after the plan is approved.

## 2026-10-05 — New data files must be checked against `.gitignore`

**What happened:** the evaluation set lived in `krtr/back/ia/matching/evaluation/data/`. The
repo's `.gitignore` rule `data/` matches a folder of that name anywhere, so the set was never
committed. Tests passed locally, where the files existed, and failed in a clean checkout.

**Rule:**
- Never name a source folder `data/`; that name is reserved for datasets at the repo root.
- After adding files that aren't Python (catalogs, JSON, SQL, text), run
  `git status --short --ignored <dir>` before proposing the commit, to catch files that git
  silently skips.
