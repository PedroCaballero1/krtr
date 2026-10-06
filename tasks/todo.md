# Phase 3 — a local LLM for the doubtful turns, and handing over to a person

_Source: `docs/ia-proposal.md` §7, phase 3 · 2026-10-05 · Status: **implemented, pending your review**_

**Goal:** an LLM resolves only what the deterministic path can't:
- free-form replies to a pending question;
- details the rules can't extract;
- the yes/no confirmation before closing on an aggressive or off-topic message.

It never answers the customer's question; it returns options it was offered, or nothing.
Requests the agent can't answer go straight to a person.

**Decided (2026-10-05):**
- **A local Hugging Face model,** not a hosted API: no per-token cost, and the conversation
  stays in-house.
- **Branch:** `implement-agents-phase3`, from `master` (`ecbcf64`).
- **Escalating `unsupported` requests (item 4)** is part of this phase.

**Runtime: `onnxruntime-genai`.**
- It has Python 3.14 wheels for macOS arm64 and Linux x86_64. It runs Qwen models in ONNX
  format on CPU, and constrains generation to a JSON schema (LLGuidance), so the output always
  parses.
- `llama-cpp-python` was ruled out: it ships no wheels, so it would have to be compiled
  locally, in CI and in the Modal image.

**Rule for every model (`tasks/lessons.md`):** an Enum listing the deterministic option too,
chosen by environment variable or CLI option, validated, built by a factory.

## Tasks

- [x] **3.1 `LlmModel` Enum and selection** — `reasoning/llm/models.py`:
  - members:
    - `NONE`: no LLM, the current template clarifier (deterministic); used by the tests and
      as the fallback;
    - `QWEN2_5_1_5B_INSTRUCT`: Qwen2.5-1.5B-Instruct, int4, CPU, from Hugging Face.
  - each member is mapped to its spec: deterministic or not, the Hugging Face repo, and the
    folder inside it;
  - selection: `KRTR_IA_LLM_MODEL` and `--llm-model`, added to `IaModelsConfig`, with the same
    precedence and validation as phase 2.
- [x] **3.2 Weights and runtime:**
  - `uv add onnxruntime-genai`;
  - the weights are downloaded once into `.krtr/models/` (`KRTR_IA_MODEL_CACHE`) with
    `huggingface_hub`, which is already installed through fastembed;
  - **first step of the phase:** confirm which Hugging Face repo publishes a CPU int4 ONNX
    build of Qwen2.5-1.5B-Instruct that `onnxruntime-genai` loads. If none does, convert it
    once with `onnxruntime_genai`'s model builder; that is an offline step, so the runtime
    never needs torch.
- [x] **3.3 `LlmClient` interface** — `reasoning/llm/base.py`:
  `complete(prompt, schema: type[BaseModel], max_tokens, timeout) -> BaseModel`.
  - The local client (`reasoning/llm/onnx/`) is imported only when that model is selected, so
    `none` never loads it.
  - A timeout or runtime error raises `LlmUnavailable`; callers then fall back to the
    deterministic path. A provider failure never blocks a conversation.
- [x] **3.4 `LlmClarifier`** (implements `Clarifier`; chain: rules first, then the LLM).
  - `interpret`:
    - when the template clarifier can't read a reply ("la de la tarjeta, no la otra"), the
      LLM chooses among the **options that were offered**;
    - the schema is a `Literal` of those options plus `"none"`, so it can't return anything
      else;
    - `"none"` repeats the question.
  - `ask`: unchanged; questions are still written from templates.
- [x] **3.5 Details the rules can't extract** — for a closed slot (product type), the LLM
  picks one Enum value or `"none"`. For a free slot (complaint ID), its answer is accepted
  only if it **appears literally in the customer's text**, so it can't invent an ID.
- [x] **3.6 Confirming guard flags before closing (G13):**
  - an `aggressive` or `off_topic` flag goes to the LLM with a yes/no schema;
  - only a "yes" applies the closure protocol, with new templates `closed_aggressive` and
    `closed_off_topic` in ES and PT;
  - with `NONE`, flags still only flag, as today.
- [x] **3.7 Handing over `unsupported` requests (G20, item 4 — deterministic, no LLM)** — a
  message that doesn't match an intent and whose best label is `unsupported` is `ESCALATED`
  with a new reason, `UNSUPPORTED_REQUEST`, and a template ("te comunico con un asesor…").
  There is no "rephrase" first and no 3-question wait.
- [x] **3.8 Engine:**
  - a new `LLM` timing step;
  - `TurnDetails.llm_used`, for the events log;
  - the factory builds the selected `LlmClient` and the clarifier chain.
- [x] **3.9 Clarifier evaluation** — `evaluation/messages/<language>/replies.tsv`, one line per
  case: question kind, options offered, free-form reply, expected answer (an option or
  `none`). Plus the existing guard and `none` messages, for the confirmation.
  `krtr back ia evaluate-llm [--llm-model]` reports, per language:
  - how many answers are right;
  - **answers outside the offered options (must be 0)**;
  - false closures;
  - latency at p50 and p95.
- [x] **3.10 Tests:**
  - a fake `LlmClient` covers the clarifier, extraction, confirmation and fallback (timeout,
    error, `none`);
  - escalating `unsupported` is deterministic and tested on its own;
  - the real-model tests are skipped when the weights aren't downloaded, as with MiniLM;
  - coverage of 85% or more, and lint clean.
- [x] **3.11 Docs:** README (`--llm-model`, `evaluate-llm`), `.env.example`, the proposal,
  and the web guide (6.2: the Qwen weights in the image, plus its memory).

## Open questions

- **Q3-A — Model size:**
  - 1.5B is the proposal: better Spanish and Portuguese.
  - If its p95 latency on CPU goes over the budget (Q3-C), the fallback is
    `QWEN2_5_0_5B_INSTRUCT` (cheaper and faster, but weaker), as a second Enum member.
  - The 3.9 evaluation decides.
- **Q3-B — Modal resources:**
  - 1.5B in int4 is about 1 GB on disk and around 2 GB of memory;
  - the `web` function (`max_containers=1`) would need more memory, which uses up the credits
    faster (D17).
- **Q3-C — Latency budget:** proposal 2.5 s per LLM call, after which the deterministic answer
  is used. Only doubtful turns pay this; the fast path stays at a few ms.
- **Q3-D — Out of scope:** the case summary (G17) waits for the cases table (web task 4.8).

## Review (phase 3)

**Result:**
- `LlmModel` Enum: `none` (deterministic) and `qwen2_5_1_5b_instruct`, selected with
  `KRTR_IA_LLM_MODEL` / `--llm-model`.
- The runtime is `onnxruntime-genai`, pinned `>=0.15.2,<0.16`: 0.16 and later don't load on
  macOS 14, because of a libc++ symbol. The Linux wheels for 0.15.2 exist.
- The weights are the official `Qwen/Qwen2.5-1.5B-Instruct`, converted locally to int4 ONNX
  (952 MB). No community build was trusted.
- Tests: 656 passed, 3 skipped, 98% coverage on `krtr/back/ia/`. Lint is clean, and the
  code rules hold.

**Final measurements** (`evaluate-llm`; each call about 1.1–1.4 s, p95 under 1.4 s, so within
the 2.5 s budget):

| Task | ES | PT |
|---|---|---|
| Choose an option (free-form reply) | 8/11, 1 false answer | 9/11, 0 false |
| Extract an ID | 3/3, 0 false | 3/3, 0 false |
| Confirm a guard flag | 32/42, 1 false confirmation | 32/42, 0 false |

**What measuring changed (beyond the plan):**
- **Schemas forbid extra keys.** Without that, the model wrote a `"reason"` field, ran out of
  tokens and left the JSON unfinished.
- **Guard confirmation classifies instead of asking yes/no** (`banking` / `abusive` /
  `off_topic`; when in doubt, `banking`). False confirmations went from 17 and 15 to 1 and 0.
  It is conservative: about 9 of 12 off-topic messages are classified `banking`. They still get
  no answer, and are escalated after 3 questions instead of closed.
- **A closure needs two independent signals:** the matcher's flag and the LLM's category.
- **Every LLM slot value passes a deterministic check:**
  - an ID must match the action's own rule (`validate_slot`);
  - a closed option must be singled out by the reply: its label shares strictly more word
    stems with the reply than any other option's (`_is_grounded`).

  "La de la tarjeta" fits credit and debit cards alike, so it is asked again; the LLM's pick
  would have been a guess.
- **The LLM no longer fills slots in the first message.** Measured, it picked a product for
  "¿Cuál es mi saldo?", which names none. It only reads replies to a question.
- **A reply matching the pending question's own intent is an answer, not a new request.**
  Before, "la de la tarjeta…" restarted the balance intent and never reached the LLM.
- **With a question pending, the reply is read before `unsupported` escalates it.** Before,
  "a de crédito" was escalated as a loan request.

**Q3-A — model size:** 1.5B stays. The errors left are on the safe side: "none", then the
question again. The one false choice left in ES is "quiero un préstamo"; in the agent it is
escalated as `unsupported` before the LLM runs. 0.5B was not needed.

**Q3-C — latency budget:** 2.5 s holds, with no timeouts. A doubtful turn costs about 1.3–1.5 s;
the fast path stays at a few ms.

**Open:**
- **Q3-B:** the Modal memory (the build is about 1 GB, plus the runtime).
- **A one-off crash at process exit** (`libc++abi … recursive_mutex lock failed`), seen once and
  not reproduced in 4 later runs. It is in onnxruntime-genai's teardown.
- **The LLM evaluation set is small** (11 + 3 replies per language). Grow it before trusting the
  rates.

---

# Phase 4 — voice to text (G8, G10)

_Status: **outline, to be planned after phase 3**_

**Goal:** a voice note is transcribed and goes through the same text pipeline. The reply is
always text (G8).

- [ ] **4.1 `SpeechToTextModel` Enum:**
  - `NONE`: voice disabled; the agent asks the customer to type, which is deterministic;
  - a local Whisper model from Hugging Face. Candidates: Whisper small or base through
    `onnxruntime-genai` (it supports Whisper, so it reuses phase 3's runtime) or
    `faster-whisper` (CTranslate2).

  Selected by `KRTR_IA_STT_MODEL` and `--stt-model`, validated.
- [ ] **4.2 Audio intake** — decode WebM/Opus and MP4/AAC (≤ 60 s, ≤ 2 MB, as the web
  contract sets) into 16 kHz mono. Check the magic bytes, and never store the audio.
- [ ] **4.3 `SpeechToText` interface** — returns the transcript, its language and a
  confidence. Low confidence asks the customer to repeat or type; the detected language
  feeds the language policy.
- [ ] **4.4 Engine and CLI** — a `SPEECH` timing step; `krtr back ia ask --audio <file>`;
  stored messages keep the transcript, never the audio.
- [ ] **4.5 Evaluation** — word error rate and intent accuracy on ES and PT recordings. **Open:
  there are no recordings in the data; they have to be recorded or sourced.**
- [ ] **4.6 Wiring** — into `/api/chat/voice` (web task 4.9), and the model weights in the
  Modal image.

---

# Phase 2 — the real embedder, the catalog and the thresholds

_Source: `docs/ia-proposal.md` §7, phase 2 · 2026-10-05 · Status: **merged into `master` (#14, v1.8.0)**_

**Goal:** replace the lexical stand-in with a local multilingual model, fill the catalog with
phrases from the data, and set the thresholds from measurements, for each model and language.
The engine does not change; only what plugs into `Embedder` and `MatchThresholds` does.

**Rule for every model (`tasks/lessons.md`):**
- A model is a member of a `StrEnum` that lists every option, deterministic ones included.
- It is chosen by an environment variable or a CLI option typed with that Enum, so an
  unknown name fails validation.
- A factory maps each member to its implementation.

**Branch:** `implement-ia-phase-2`, from `master` (`407932b`).

## Tasks

- [x] **2.1 Model registry** — `matching/models.py`:
  - `EmbeddingModel` StrEnum:
    - `HASHING` — the deterministic trigram embedder of phase 1: offline, used in tests;
    - `MULTILINGUAL_MINILM` — `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
      (220 MB, 384 dimensions, run through ONNX).
  - Each member is mapped to its traits: deterministic or not, its download name, and its
    dimensions.
  - `language/models.py`: `LanguageDetectorModel` StrEnum with `PY3LANGID` (deterministic,
    the only one), selected the same way, so every model the agent uses is listed in an Enum.
- [x] **2.2 Selection by environment or CLI** — `IaModelsConfig` (pydantic):
  - reads `KRTR_IA_EMBEDDING_MODEL` and `KRTR_IA_LANGUAGE_MODEL`;
  - validates them against the Enums, so an unknown value fails at startup and names the
    accepted values;
  - CLI: `--embedding-model` and `--language-model` on `ask`, `chat` and `evaluate`, typed
    with the Enums. The CLI option wins over the environment variable, which wins over the
    default.
  - Factories `build_embedder(EmbeddingModel)` and `build_language_detector(...)`; `build_engine`
    takes the config instead of instances.
- [x] **2.3 ONNX embedder** — `matching/onnx/` (`FastEmbedEmbedder`):
  - built on `fastembed` (ONNX runtime, about 20 MB, no PyTorch), added with `uv add fastembed`;
  - imported only when the multilingual model is selected, so tests and `--embedding-model
    hashing` never load it;
  - the model is downloaded once to `.krtr/models/` (git-ignored).
- [x] **2.4 Thresholds per model and language** — `matching/thresholds.json`, keyed by model
  then language.
  - The matcher receives the turn's language: the language step already runs before matching.
  - A missing (model, language) pair fails when the engine is built, not mid-conversation.
  - The hashing values from phase 1 move into this file unchanged.
- [x] **2.5 Catalog content (tracks D.1–D.3)** — done by me in this session, in place of a
  separate LLM pipeline, and reviewed by you:
  - **D.1:** extract the distinct texts, offline, from Neon (Q2-C):
    - the customer lines of the call history (6, from the EDA);
    - the complaint `description`, category and subcategory texts.

    In the live flow, the text comes from the web page instead.
  - **D.2:** label each text as an existing intent, a new deterministic one, or hard
    (escalate), in a review table `docs/ia-intents.md`. A **new** intent needs a new action,
    which is out of this phase unless you choose one.
  - **D.3:** direct ES → pt-BR translation of the lines, plus 10–20 phrases per intent and
    language, in `exemplars/<language>/<label>.txt`.
- [x] **2.6 Evaluation set (D.4)** — `matching/evaluation/<language>/<label>.txt`, one
  message per line, never reused as catalog phrases, plus `none.txt` for messages outside
  the catalog. Reviewed by you.
- [x] **2.7 `krtr back ia evaluate`:**
  - scores the evaluation set with the selected model;
  - reports, per language, how many messages land on each outcome (right match, wrong match,
    ambiguous, no match) and the embedding latency;
  - sweeps `accept`, `reject` and `margin`, and proposes the values with **zero wrong
    matches** and the most right ones.

  I set `thresholds.json` from that report. A wrong match answers the wrong question, so it
  costs more than one extra clarification.
- [x] **2.8 Tests:**
  - the Enum validation from the environment and from the CLI;
  - the factories, including that `hashing` never imports `fastembed`;
  - threshold loading, including a missing pair;
  - the sweep, on fixed scores;
  - the CLI options.
  - One test runs the real model on a few ES / PT phrases, marked to be skipped when the
    model isn't downloaded.
- [x] **2.9 Verification and docs** — coverage of 85% or more; lint; README (model options,
  `evaluate`); a review section here.

- [x] **2.10 Broad off-topic coverage** (requested 2026-10-05) —
  `exemplars/<language>/off_topic.txt` in ES and PT, covering many categories: sports,
  weather, cooking, health, politics, religion, entertainment, travel, studies and homework,
  technology, other companies, small talk, jokes, questions about the bot itself, attempts to
  change its instructions, illegal or sexual requests, and financial advice outside the bank.
  - Off-topic phrases must never swallow a banking request the catalog doesn't cover yet (for
    example "quiero un préstamo"). The evaluation set includes those, and the `guard`
    threshold is set so they don't flag.
  - A flag still does not close the conversation by itself; that needs the LLM's
    confirmation (phase 3).
- [x] **2.11 Repetition by meaning, anywhere in the window** (requested 2026-10-05):
  - Before: only identical texts counted, though not necessarily back to back (3 within the
    last 10 messages).
  - Now: a message counts as a repeat when its embedding is at least `repeat` similar to an
    earlier message in the window, so a paraphrase of an earlier question counts too.
  - The engine embeds once, before the guardrails, and the state keeps the window's vectors.
    Option numbers are still excluded.
  - `repeat` lives in `thresholds.json` per model and language. The evaluation measures it
    with pairs that must count (paraphrases) and pairs that must not (the same request for
    another product, which is a new question).

## Decisions (2026-10-05)

- **Q2-A — Default embedding model:** `multilingual_minilm`. `hashing` is for offline use and
  the tests.
- **Q2-B — Second ML model:** none. MiniLM only.
- **Q2-C — Where the texts come from:**
  - **offline** (building the catalog and the evaluation set): read from Neon;
  - **online** (live conversations): the customer's text comes straight from the web page,
    and nothing is read from the data.
- **Q2-D — Production image:** the MiniLM weights are built into the Modal image (web task
  6.2), so cold starts never download them. Noted in the web guide.

## Review (phase 2)

**Result:**
- Models are chosen from Enums, by CLI or environment:
  - `EmbeddingModel`: `multilingual_minilm` (default) and `hashing` (deterministic);
  - `LanguageDetectorModel`: `py3langid`.
- MiniLM runs through ONNX (`fastembed`) in about 2.5 ms per message.
- Tests: 601 passed, 3 skipped, 99% coverage on `krtr/back/ia/`. Lint is clean, and no
  function goes over 40 lines.

**What the measurements changed (beyond the plan):**
- **A new rival label, `unsupported`.** Banking requests the agent can't answer scored as high
  as real ones ("Me cobraron algo que no reconozco" scored 0.72 against `account_balance`;
  "Saldo de mi tarjeta de crédito" scored 0.71). A match now needs a lead over every guard
  label too. Guard recall went from 4 of 16 (ES) and 8 of 16 (PT) to 11 and 12 of 16, with
  zero false flags.
- **Identifiers stripped before embedding.** "¿Cómo va mi reclamo PQR-104233?" went from 0.55
  to a clear match.
- **Repetition by request.** With MiniLM, the same balance request for another product is
  more similar (0.72–0.74) than a real rewording (0.60–0.67). A similarity threshold alone
  would close legitimate conversations. Now, the same intent with the same details, anywhere
  in the window, counts as a repeat; a near-identical text still counts too.
- **The threshold search was rewritten twice.** A joint search on 51 messages gave arbitrary
  picks (an `accept` of 0.30, a margin of 0). The final rules are explicit, each with a 0.03
  safety gap:
  - `margin` comes from the non-catalog messages within reach of a match;
  - `accept` keeps every right match that clears that margin;
  - `reject` never sends a catalog message to "rephrase".

**Final measurements (MiniLM):**

| | ES | PT |
|---|---|---|
| Catalog messages answered directly | 17 of 18 | 17 of 18 |
| Wrong matches | 0 | 0 |
| Guard flags | 11 of 16, 0 false | 12 of 16, 0 false |
| Repeats caught | 2 of 5, 0 false out of 1,200+ negative pairs | 3 of 5, 0 false |

The hashing thresholds were re-measured with the same rules.

**Open:**
- **Guard flags only flag.** Closing on them, and escalating `unsupported` straight to a
  person, waits for phase 3.
- **The catalog and the evaluation set are small.** Growing them is the cheapest way to raise
  coverage and confidence.
- **Candidate intents** `goodbye` and `file_complaint` (`docs/ia-intents.md`).
- **Q-A:** the `complaint_id` format.

---

# Phase 1 — `krtr/back/ia/` deterministic core

_Source: `docs/ia-proposal.md` §7, phase 1 · 2026-10-02 · Status: **merged into `master` (#13, v1.7.0)**_

**Goal:** an end-to-end conversation engine with **no model calls at all**. A message
goes through the guardrails and the intent matcher (with a fake embedder in tests), then
either a deterministic action or a deterministic clarification, and comes back as a
template reply in ES or PT. Phase 2 plugs in the real local embedder and the catalog; phase
3 plugs in the LLM. Neither of them changes the engine.

**Branch:** `implement-ai-agents`, updated with `origin/web-develop`, which holds the
merged `web-develop-security` work (PR #10). `master` does not have it yet.

**Applies to every task:** `CLAUDE.md` rules (docstrings, 40-line limit, enums instead of
literals, `config.py` / `artifacts.py` per subpackage, `logging` only, tests mirror the tree
1:1, ≥85% coverage, behaviour-level assertions).

## Change to the proposal

The matcher's **decision rule** (threshold + margin → `MATCHED` / `AMBIGUOUS` /
`NO_MATCH`) and the **catalog loader** move into phase 1. They are pure logic and can be
tested with a fake embedder that returns fixed vectors. Phase 2 is then only: choosing the
model, writing the examples, and setting the thresholds from the evaluation set.
`docs/ia-proposal.md` §7 is updated to match.

## Tasks

- [x] **1.1 Shared contracts** — `ia/config.py` (`IaConfig`: `max_clarification_turns`,
  `repetition_limit`) and `ia/artifacts.py` (`UserTurn`, `AgentReply`, `CustomerContext`,
  `ConversationState`, `TurnOutcome`). Reuse `InterfaceLanguage` from
  `back/security/oidc/artifacts.py` instead of a second language enum.
- [x] **1.2 Deterministic contracts** — `deterministic/intents.py` (`Intent`),
  `deterministic/base.py` (`DeterministicAction[SlotsT]`), `deterministic/registry.py`
  (`ActionRegistry`: fails fast on a duplicate or unregistered intent), and
  `deterministic/artifacts.py` (`ActionOutcome`, `MessageKey`).
- [x] **1.3 Slot extraction** — `deterministic/slot_extraction.py`: product type from ES / PT
  keywords → `ProductType` enum; complaint ID by regex (format pending, Q-A below).
- [x] **1.4 Two actions, reading through protocols with fakes:**
  - `ACCOUNT_BALANCE`, slot `product_type`. The most common request in the call history,
    and it matches the `products` columns `current_balance`, `credit_limit`, `currency`.
    "What's my balance?" with no product → the engine asks which one. Several products
    of the same type → all of them.
  - `COMPLAINT_STATUS`, slot `complaint_id`. "Doesn't exist" and "belongs to someone
    else" give the same outcome.
  - Readers: `CustomerProductsReader` and `CustomerComplaintsReader` protocols, always
    filtered by `CustomerContext.customer_id`. Neon implementations are out of scope (see
    below).
- [x] **1.5 Matching** — `matching/base.py` (`Embedder` ABC); `matching/labels.py`
  (`GuardLabel`); `matching/catalog.py` (`ExemplarCatalog` from
  `exemplars/<language>/<label>.txt`, one phrase per line; fails fast on an unknown
  label or too few examples); `matching/matcher.py`
  (cosine top-k, threshold + margin rule); `matching/config.py` (`MatchThresholds`);
  `matching/artifacts.py` (`MatchResult`). Uses `numpy`, added as a direct dependency
  with `uv add numpy` (it is only transitive today).
- [x] **1.6 Guardrails** — `guardrails/policy.py` (`GuardrailPolicy`): a message repeated
  `repetition_limit` times (normalised exact match in phase 1; similarity in phase 2) →
  `CLOSED`. A guard-label match only flags; closing on it waits for the LLM's
  confirmation (phase 3).
- [x] **1.7 Resolution + deterministic clarifier** — `reasoning/artifacts.py`
  (`Resolution` discriminated union) and `reasoning/clarifier.py` (`Clarifier` ABC +
  `TemplateClarifier`). It handles:
  - a missing slot → ask, listing its options;
  - `AMBIGUOUS` → offer the top 2–3 candidates;
  - `NO_MATCH` → ask the customer to rephrase;
  - a reply to a pending question → resolved by option number or name;
  - over `max_clarification_turns` → `ESCALATED`.
- [x] **1.8 Template writer** — `writing/base.py` (`ResponseWriter`) and
  `writing/templates/` (`TemplateResponseWriter` + `es.json` / `pt-BR.json`, keyed by
  `MessageKey`; fails fast if a key is missing in either language).
- [x] **1.9 Engine** — `engine/store.py` (`ConversationStateStore` protocol +
  `InMemoryConversationStateStore`) and `engine/engine.py` (`ConversationEngine.handle`:
  guardrails → match → slots → action or clarification → writer → save state). Its
  logs tell the turn step by step.
- [x] **1.10 Tests** — `tests/back/ia/...` mirroring the tree, with a `fakes.py` (fixed
  vectors, in-memory readers). Required scenarios:
  - clear match → balance reply in ES and PT;
  - no product given → question → reply "2" → balance;
  - ambiguous → choice;
  - clarification limit → escalated;
  - repetition → closed;
  - someone else's complaint ID → same reply as a missing one;
  - catalog / template validation failures.
- [x] **1.11 CLI to try the engine** — `krtr/cli/back/ia/handler.py`, registered under
  `krtr back ia`. Two commands:
  - `ask "<text>" --language es|pt-BR` runs one turn;
  - `chat --language ...` keeps the conversation state across turns, so the
    clarification flow can be tried.

  Both run on in-memory sample products and complaints and a deterministic stub
  embedder, so no network or model is needed. They are tested at
  `tests/cli/back/ia/test_handler.py`.
- [x] **1.12 Verification** — `pytest` with coverage ≥85% on `krtr/back/ia/`; ruff, flake8
  and black clean; a review section added at the end of this file.
- [x] **1.13 Language detection per conversation (G14)** — new sub-vertical
  `krtr/back/ia/language/`. The reply language becomes a property of the conversation,
  not a fixed input:
  - `base.py` — `LanguageDetector` interface, returning a `LanguageGuess` (language +
    confidence).
  - `py3langid_detector.py` — `Py3LangidLanguageDetector`, limited to ES and PT, offline.
    Added with `uv add py3langid`. Lingua was tried first and dropped:
    - its wheel is about 170 MB;
    - on the same phrases it was only 70–77% sure of plain Spanish sentences;
    - it was 88% sure that "PQR-104233" is Portuguese.

    py3langid is 4.4 MB, needs only numpy, and was above 92% on every full sentence.
  - `config.py` — `LanguageConfig`: minimum words and minimum confidence for a message to
    count.
  - `policy.py` — `ConversationLanguagePolicy`:
    - the caller's language (web selector or `--language`) is only the starting hint;
    - a message long and clear enough sets the conversation's language, saved in
      `ConversationState.language`;
    - short or unclear messages ("1", "saldo", "PQR-104233") never change it;
    - a later clear message in the other language switches it (the customer changed
      language).
  - `AgentReply.language` reports the language the reply was written in.
  - Tests: the policy with a fake detector; the py3langid detector on real ES / PT
    sentences; the engine switching language mid-conversation; the CLI.

- [x] **1.14 Latency per response (G16)** — the engine times every turn, in total and per
  step: language, guardrails, embedding, matching, resolution, action, writing.
  - Timing lives in `krtr/back/ia/timing.py` (`StepTimer`, with an injectable clock so tests
    are exact).
  - The result is returned as `AgentReply.timings` (`TurnTimings`), so the web chat endpoint
    can store it in the `chat_response_received` event (G21).
  - It is logged as one line per turn.
  - The CLI shows the total next to the outcome; `--verbose` shows the steps.
  - The engine records no events itself; the web layer does (it owns `EventRecorder`).

- [x] **1.15 Turn metadata for the events log (G21)** — `AgentReply.details`
  (`TurnDetails`): the intent resolved or asked about, the match kind and the guard flags.
  Together with `outcome`, `language` and `timings`, it is everything the web chat endpoint
  needs for the `chat_response_received` event, without the reply text.
  - **Decided (2026-10-05):** metadata goes to `events`; message and reply text go to a
    messages table (Q5).

- [x] **1.16 `messages` table (decided 2026-10-05)** — the text of every message and reply.
  The contract is in `docs/ia-proposal.md` §9 and `docs/guia-web-seguridad_modal.md` §3.6.
  - **Columns:** `message_id`, `incident_id`, `customer_id`, `sender`, `content`,
    `language`, `outcome`, `sent_at`.
  - **Encrypted:** `content` with AES-256-GCM, using its own key `KRTR_MESSAGES_KEY`.
  - **Retention:** 3 months; `purge.sql`, run by the daily `purge_events` job.
  - **Index:** on `(incident_id, customer_id)`, explicitly requested.
  - **To build:**
    - `krtr/database/queries/messages/`: `table.sql`, `insert_one.sql`,
      `select_by_case.sql`, `purge.sql`;
    - a `MessageStore` in `krtr/back/ia/`;
    - the grants to `krtr_app` in both Neon branches.
  - **Done:**
    - the 5 SQL files under `krtr/database/queries/messages/` (`query.sql` too, which the
      column-order test requires);
    - `CryptoEnvironmentVariable.MESSAGES_KEY`, and `.env.example`;
    - `krtr/back/ia/messages/`: `NeonMessageStore` (encrypts on write, decrypts on read,
      `purge_expired`) and `InMemoryMessageStore`;
    - the engine stores the customer's message and the agent's reply every turn, timed as
      the `persistence` step.
  - **Still to do, by you (Neon):**
    - `uv run krtr database neon create-schema messages` in the main branch and in `dev`;
    - then `GRANT SELECT, INSERT, DELETE ON messages TO krtr_app`;
    - generate `KRTR_MESSAGES_KEY` in `.env`.
  - **Still to wire:**
    - `NeonMessageStore` into the served app, once the chat endpoint exists (web task 4.9);
    - `purge_expired` into the daily job (tasks 4.10 / 6.5).
  - **Still open:** where the case summary lives (G17). Proposed: the cases table (web
    task 4.8).

## Out of scope for phase 1

- **Neon readers for products and complaints.** `products/table.sql` exists; a
  complaints table does not, and its `table.sql` needs your column documentation.
- **Wiring into `/api/chat/messages`.** It depends on task 4.9 (the chat endpoints)
  of the web guide.
- **The real embedder, the example phrases, and the thresholds** (phase 2).
- **The LLM** (phase 3).
- **The messages table** — its contract is decided (task 1.16, below); implementing it is a
  separate step.
- **A persistent conversation state.**
- **Recording `chat_response_received`.** It belongs to the web chat endpoint (task 4.9).

## Parallel track — intent discovery from the call history (feeds phase 2)

**What the EDA already shows** (`notebooks/eda/call_transcripts/causes.ipynb`): the
171,321 transcripts contain **only 12 distinct lines of dialogue** (6 by the customer) and
546 distinct conversations, all in Spanish.

- **Every call opens with a balance request:** savings account or credit card.
- **The only follow-up questions** are "how long does it take?" and "anything else I
  should know?".
- **`main_topics` is not visible in the text.** 17% of calls are labelled `Queja`, yet
  none of them contains a complaint.
- **`detected_intents` has a single value** (`consulta_general`).

**Consequence:** running an LLM over 171k calls would cost money and rediscover these
two intents. The same work done properly is a few dozen strings:

- [ ] **D.1 Deduplicate the sources.** The distinct customer lines from the transcripts,
  the 5 complaint `description` values, and the complaint category / subcategory pairs
  (`Cargo no reconocido`, `Cobro indebido`, `Problema con app`, `Atención en sucursal`,
  `Calidad de servicio`).
- [ ] **D.2 LLM labelling of those distinct texts** into intent candidates. Each one is
  marked **deterministic** or **hard**. The split is a design rule, not a pattern in the
  data (the data is uniform): an intent is deterministic only if an action can answer it
  from data we hold for that customer. Example: a balance is deterministic; "a charge I
  don't recognise" needs investigation → hard / escalate.
- [ ] **D.3 Translate to PT** — LLM direct translation ES → pt-BR of the distinct customer
  lines, one-to-one. That gives the PT catalog the same coverage as ES.
- [ ] **D.4 Evaluation messages** — a separate set, never reused as catalog examples, so
  the thresholds aren't set on the examples themselves. With only 6 distinct customer
  lines, a few paraphrases per intent (reviewed by you) are still needed here. Otherwise
  the evaluation measures nothing.

## Open items

- **Q-A: the `complaint_id` format,** for its regex.
- **Q-B ✅ resolved: plain text,** one file per label and language, one phrase per line.
  It is the cheapest format for an LLM to read and write: no braces, quotes or repeated
  keys, so no wasted tokens. It also needs no parser beyond `splitlines()` and no new
  dependency. The label is the file name, validated against `Intent` / `GuardLabel`.

## Review

**Result.**
- `krtr/back/ia/` and `krtr back ia ask|chat` are implemented as planned.
- 77 new tests, 99% coverage on `krtr/back/ia/` and `krtr/cli/back/ia/`.
- Full suite: 510 passed, 3 skipped.
- ruff, flake8 and black are clean.
- No function over 40 lines, no nested functions, and every function and class has a
  docstring (checked with a script).

**Deviations from the plan.**
- **`numpy` added** with `uv add numpy`, as planned.
- **Coverage measured with a temporary dependency** (`uv run --with pytest-cov`); the
  repository has no coverage tool.
- **`HashingEmbedder` (character trigrams) stands in for the real model.** Its scores are
  lexical, so the default `margin` is 0.05 to suit it. Example: "Quiero saber el saldo
  de…" shares words with "Quiero saber el estado de mi queja". Phase 2 resets every
  threshold for the real model.
- **`SlotName` enum added,** so slot names are not repeated as literals.
- **`demo.py` added:** sample data and engine for one demo customer, used by the CLI.
- **Language enum reused:** `InterfaceLanguage` from `back/security/oidc/artifacts.py`.

**Still open.**
- **Q-A:** the `complaint_id` format. `DEFAULT_COMPLAINT_ID_PATTERN` is provisional
  (`deterministic/config.py`).
- **Seed phrases:** only the 2 balance lines come from the call history (translated to PT).
  The complaint and guard phrases were written by hand; tracks D.1–D.4 replace them.
- **The clarifier lists all 7 product types,** not only the ones the customer holds.

---

# Conversation context for the LLM

_2026-10-06 · Status: **implemented, pending your review**_

**Problem:** every LLM task (`choose_option`, `extract_value`, `confirm_guard` in
`reasoning/llm/tasks.py`) sees only the current message. A reply such as "the other one" or
"same as before" can't be read without the conversation.

**Decided (2026-10-06):**
- **The whole case, capped:** every earlier message of the incident, customer and agent,
  oldest first, within the limits of `HistoryConfig`. The plan's "20 messages" turned out too
  big; see the review below.
- **All three tasks** get the history. Each task still decides on the **last** message only;
  the history is context.

**Design:**
- **Source: `MessageStore.list_case`.** It already stores every message, encrypted. During a
  turn it holds the earlier messages, because the current one is stored at the end of the
  turn. History is loaded **only when an LLM task actually runs**, so clear turns (≈3 ms)
  keep no extra DB read. Plaintext is never copied into `ConversationState`, so encryption
  at rest still holds.
- **Plumbing:** `LlmTasks` stays free of I/O. Its methods take a `ConversationTranscript`;
  callers load it.

## Tasks

- [x] **C.1 `ConversationTranscript`:** a pydantic contract in a new
  `reasoning/llm/artifacts.py`. It holds a list of (sender, text) and has:
  - `render()`: `Customer: …` / `Agent: …` lines, or "(no earlier messages)";
  - `customer_texts()`: the customer's messages only.
  - The role labels are mapped from `MessageSender`, with no literals.
- [x] **C.2 `ConversationHistory`:** in a new `reasoning/llm/history.py`, built with a
  `MessageStore` and the cap. `load(state) -> ConversationTranscript` reads
  `list_case(state.customer_id, state.incident_id)` and keeps the newest N.
- [x] **C.3 Config:** add `history_messages_kept: int = Field(default=20, ge=0)` to the LLM
  config (`reasoning/llm/config.py`), loaded the same way as the existing fields.
- [x] **C.4 Prompts:** add a `{conversation}` block to the three `.txt` templates, with the
  instruction "decide/classify only the last reply; earlier messages are context". In
  `confirm_guard`, a flagged reply that follows a banking problem stays `banking`.
- [x] **C.5 `LlmTasks`:** `choose_option`, `extract_value`, `fill_slot` and `confirm_guard`
  take the transcript and render it into the prompt.
- [x] **C.6 Grounding (needs your OK):** the LLM's answer is checked against the current
  reply **plus the customer's earlier messages, never the agent's**. The agent's questions
  list every option label, so counting them would ground any answer.
  - Trade-off: "the card" after an earlier "my credit card" now resolves to credit. Today it
    is rejected.
  - Alternative: keep grounding on the current reply only. That is safest, but for closed
    slots the history then cannot change the outcome; it only helps `CHOOSE_INTENT`.
- [x] **C.7 `LlmClarifier`:** receives `ConversationHistory` and loads the transcript once,
  inside `_read_with_llm`, so only when the template clarifier would repeat the question.
- [x] **C.8 Guard confirmation:**
  - `GuardConfirmer.confirm_guard` gains `state`, which `GuardrailPolicy.check_flags`
    already has.
  - A new `LlmGuardConfirmer` in `reasoning/llm/guard.py` (tasks + history) implements it,
    loading the transcript once per flagged turn, not once per flag.
- [x] **C.9 Wiring:** `engine/factory.py` builds one `ConversationHistory` from the engine's
  `messages` store and passes it to both consumers.
- [x] **C.10 Tests** (mirrored under `tests/back/ia/`, ≥85% coverage):
  - transcript rendering, order, cap and empty case;
  - the history excludes the current message;
  - no history read on a turn without the LLM;
  - the prompt contains the history;
  - grounding accepts earlier customer text and rejects agent-only text;
  - the guard loads once with two flags;
  - an engine test where "la otra" is resolved through history.
- [x] **C.11 Evaluation (lesson: an evaluation must offer what production offers):**
  - add an optional 6th field `history` to `replies.tsv`;
  - add ES and PT-BR cases that need context, using the real option lists, plus cases where
    history must **not** change the answer;
  - run the evaluation before and after; zero wrong answers must hold.
- [x] **C.12 Latency check on the real model:**
  - p50/p95 with 0, 10 and 20 messages of history, against the 2.5 s timeout;
  - adjust the default cap if 20 doesn't fit;
  - finish with a few real end-to-end conversations in `krtr back ia`.

**Risks:**
- **Prompt injection through earlier messages:** contained. The output is still
  schema-constrained to the offered options and checked by grounding and the actions' rules.
- **Longer prompts on CPU:** measured in C.12.

## Review (2026-10-06)

**Changes from the plan:**
- **Character limits (requested mid-task):** `HistoryConfig` caps the transcript three ways.
  Each message is cut to 300 characters, marked ` […]`. The whole transcript holds at most
  1,000 characters and the newest 10 messages; past that, the oldest go. A customer who keeps
  sending 2,000-character messages can't push the prompt past the timeout.
- **SLA revised to 4 s (requested mid-task):** the LLM timeout per call went from 2.5 s to
  3.5 s, leaving ~0.5 s for the rest of the turn. Docs were updated: the README, the story
  HTML, `docs/goals.md` (G16, with the original 1 s kept visible), both web guides and the
  `timing.py` docstring. The phase-3 records above still say 2.5 s, because they record what
  was measured then.
- **The plan's defaults were wrong, measured:** each character of history adds about 1.1 ms
  to a call. 20 short messages took 3.5 s and a flooded case 4.2 s, so both would have timed
  out. With 1,200 characters, p95 was 2.8 s and the slowest call 3.1 s; the default is 1,000.
- **Prompts:** the context is an optional section that is empty when there are no earlier
  messages. A first version reworded every template; it changed the baseline, and two PT
  banking messages were falsely confirmed as aggressive. With the section, turns without
  history get the exact prompts measured in phase 3. The results on the old cases match it:
  - choose: ES 8/11 with 1 false, PT 9/11 with 0 false;
  - guard confirmations: ES 1 false, PT 0 false.
- **Grounding (C.6):** messages narrow the options in turn: the reply first, then earlier
  customer messages from newest to oldest. Pooling them all would have tied "la de crédito"
  against an earlier "débito" and rejected an answer that is accepted today.
- **Guard confirmation:** the protocol is now `confirm_first(state, labels, …)`, one history
  read per flagged turn.

**Evaluation** (`evaluate-llm`, 22 new cases with history, 11 per language):

| Task | ES | PT |
|---|---|---|
| Choose an option | 12/17, 1 false (the old "quiero un préstamo") | 12/17, 0 false |
| Extract an ID | 5/5, 0 false | 4/5, 0 false |
| Confirm a guard flag | 34/45, 2 false | 33/45, 1 false |

- **Context helps:** "la de la tarjeta" after "mi tarjeta de crédito" (ES), "no, la de débito"
  over an earlier credit card, and an ID the customer gave earlier (ES).
- **Context doesn't help yet**, but these come back `none`, so the question is asked again:
  "la que usé ayer", "lo que te acabo de contar", and the PT "já te passei".
- **New false confirmations:** "son unos ladrones, unos inútiles" (and the PT version) after a
  banking complaint is confirmed as aggressive. Measured: the model confirms it with or
  without the history, so it is an existing miss, not a regression. Both cases stay in the
  evaluation as misses.
- **Latency:** p50 1.2–1.5 s, p95 under 1.8 s, 0 unavailable.

**End-to-end** (`krtr back ia chat`, real Qwen):
- ES, credit card mentioned, then "¿Cuál es mi saldo?" → "la de la tarjeta": credit card
  balance, 1.99 s.
- ES, the same without the earlier mention: asked again, 1.89 s.
- PT, ID given, then the complaint request → "já te passei…": asked again, 1.50 s (the known
  miss).

**Tests:** 895 passed, 3 skipped. Coverage of the new modules is 98–100%. black, ruff and
flake8 are clean; no function is over 40 lines.

**Still open:**
- **The SLA is per turn, but the timeout is per call.** A turn with two guard flags and then
  a clarifier reply makes 3 calls (worst case ~10 s). See "Possible improvements" in the
  session summary.
- **Latency was measured on a laptop CPU only.** Modal's CPU may be slower; measure there
  before raising `HistoryConfig`.

