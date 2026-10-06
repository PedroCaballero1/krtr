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
