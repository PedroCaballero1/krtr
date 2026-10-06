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

## 2026-10-05 — An evaluation must offer what production offers

**What happened:** the LLM evaluation offered 3 product options; the live flow offers 7,
including two cards (credit and debit). "La de la tarjeta" looked like a clear answer in the
evaluation and was a guess in production. Live conversations showed it; the evaluation didn't.

**Rule:**
- Build evaluation cases from the real option lists the code produces, not hand-trimmed ones.
- Always follow an evaluation with a few real end-to-end conversations before reporting it.

## 2026-10-06 — Limits that bound latency are measured before they get a default

**What happened:** the plan for the LLM's conversation context set a default of 20 messages
from intuition. Measured, 20 short messages took 3.5 s per call against a 2.5 s timeout. The
LLM would have silently stopped helping on exactly the long conversations. The same change
also reworded every prompt, which moved the phase-3 baseline even on turns with no history.

**Rule:**
- A size limit that drives latency (context, batch, prompt) gets its default from a
  measurement on the real model, at the worst case (maximum-length inputs), never from a guess.
- A prompt change behind a new feature must leave the old path's prompt byte-identical (an
  optional section that renders empty), so the existing evaluation still holds.
