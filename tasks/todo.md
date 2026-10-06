# Phase 2 — the real embedder, the catalog and the thresholds

_Source: `docs/ia-proposal.md` §7, phase 2 · 2026-10-05 · Status: **implemented, pending your review**_

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
