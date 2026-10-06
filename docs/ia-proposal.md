# Proposal — the `krtr/back/ia/` vertical

_Status: draft for review · 2026-10-02 · Covers goals G1, G8, G10–G14, G16, G17, G19, G20._

## 1. Core idea

Every customer message is driven towards a **deterministic answer**: a fixed action whose
result depends only on its validated inputs and the customer's own data. Anything
non-deterministic (LLMs, speech recognition) exists only to **get the conversation
there**: to understand the request and to collect the missing information.

This is the classic *intent + slot filling* pattern of task-oriented dialogue systems
(the approach behind Rasa CALM and Dialogflow CX): understanding is probabilistic, and
fulfilment is deterministic.

| Level | What it does | Examples | Cost / latency |
|---|---|---|---|
| **Deterministic** | Matches the message against known intents, executes an action once its intent and inputs are known | similarity against in-memory examples, if/else rules, SQL reads scoped to the customer, templates | ~free, ms |
| **Non-deterministic** | Asks for clarification, interprets the answer, extracts free-text inputs | LLM, speech to text | paid, 100s of ms to s |

G12 (route by difficulty to cut costs) follows directly: the cheapest path is the one
that reaches a deterministic action with no model call at all.

### 1.1 Three adjustments to the premise

1. **Not every conversation can end in a deterministic answer.** Handing the case to a
   human (G20) and closing the conversation (G13) are also valid endings. The engine
   therefore has **three terminal outcomes**: `RESOLVED`, `ESCALATED`, `CLOSED`.
2. **Clarification needs a limit.** "Always try to get enough information" without a cap
   ends up interrogating the customer, and it collides with the G13 rule on repetitive
   messages. Proposal: at most `max_clarification_turns` (default 3) per intent; after
   that, escalate.
3. **"An LLM writes the answer" can make a deterministic answer non-deterministic.** If the
   writer can add or change facts, the guarantee is lost. Proposal: a deterministic action
   returns **facts** (typed data plus a message key), and the writer only **phrases**
   them. A template writer is the default, because it costs nothing and fits G16. An LLM
   writer is optional; it receives only those facts, and a check rejects any number or ID
   in its output that is not among them.

## 2. Components

| Component | Responsibility | Deterministic? |
|---|---|---|
| `matching/` — **intent matcher** | Embed the message once and score it against an in-memory catalog of example phrases per intent (ES + PT). Return `MATCHED`, `AMBIGUOUS` (top candidates) or `NO_MATCH` (§3.1) | Yes, for a given model and catalog |
| `deterministic/` — **actions** | One class per supported intent: validate inputs, run if/else + scoped reads, return facts | Yes |
| `reasoning/` — **clarifier (LLM)** | Only when the matcher is not sure, or inputs are missing: ask a clarification question, interpret the reply, extract free-text inputs. It can only choose intents from the catalog | No |
| `guardrails/` — **hard rules** | G13 checks: repetition (similarity to the customer's earlier messages), aggressive / off-topic (example sets in the same catalog), someone else's data (enforced in the actions) | Mostly yes; the LLM confirms before closing |
| `speech/` — **speech to text** | Turn a voice note into text + detected language + confidence (G8, G10 phase 2) | No |
| `writing/` — **response writers** | Phrase an outcome or a clarification question in ES / PT (G14) | Template: yes · LLM: no |
| `engine/` — **conversation engine** | Run one turn through the pipeline; the only entry point the web calls | Yes (it orchestrates) |
| `llm/` — **LLM client** | Provider-agnostic access to models by tier; shared by the clarifier and the writer | — |

### 2.1 Turn pipeline

```
UserTurn (text | audio, incident_id, customer_id from the session, language)
  │
  ├─ audio? ──► SpeechToText ──► text            (low confidence → ask to repeat)
  ▼
Embedder.embed(text)                              ONE local embedding (ms, no network)
  ▼
Guardrails (deterministic)                        repeat of an earlier message N times → CLOSED
  │   aggressive / off-topic example match ──► flagged → the clarifier confirms → CLOSED
  ▼
IntentMatcher.match(vector)
  ├─ MATCHED(intent) ─► slots by regex ─► missing slots? ──► Clarifier
  ├─ AMBIGUOUS(top candidates) ───────────────────────────► Clarifier
  └─ NO_MATCH ────────────────────────────────────────────► Clarifier
                                                             │
Clarifier (LLM, structured output, intent ∈ catalog only) ◄──┘
  │
  ├─ RESOLVED(intent, slots) ─► ActionRegistry[intent].execute(context, slots) ─► facts
  ├─ NEEDS_CLARIFICATION(question, candidates, missing slots)   (attempts += 1; over the limit → ESCALATED)
  ├─ ESCALATED(reason) ─► human handoff + summary (G17, G20)
  └─ CLOSED(reason)    ─► closure protocol (G13)
  ▼
ResponseWriter(outcome, language) ─► AgentReply
  ▼
ConversationState saved (pending candidates, collected slots, attempts, summary)
```

**The fast path has no model call at all:** a message that matches clearly, with its
inputs found by regex, goes straight to the action and a template. The LLM is used only
to resolve doubt, and it can never answer the question itself: it either returns an
intent from the catalog plus its inputs, or a question for the customer.

**Clarification replies.** "The second one" or "the card" means nothing to the matcher
on its own. When the state has pending candidates, the reply goes to the clarifier with
those candidates in context. The matcher still runs first: if the reply alone matches
clearly (the customer simply rephrased), that result wins.

### 2.2 Slots: how "enough information" is defined

Each deterministic action declares its inputs as a pydantic model. **The schema is the
definition of "enough information":**

- The resolver proposes slot values.
- Pydantic validates them.
- Missing or invalid fields automatically become the clarification question.

No component decides on its own that the information is "sufficient".

## 3. Abstractions (sketch)

Signatures only; docstrings and `config.py` are omitted for brevity, and the real code
follows `CLAUDE.md`.

```python
# deterministic/intents.py
class Intent(StrEnum):
    """The requests krtr can answer deterministically; the matcher and clarifier may only output these."""

    COMPLAINT_STATUS = "complaint_status"   # illustrative — the real catalog is open question Q2
    ...


# deterministic/base.py
class DeterministicAction(ABC, Generic[SlotsT]):
    intent: ClassVar[Intent]
    slots_model: ClassVar[type[SlotsT]]          # pydantic model = the required information

    @abstractmethod
    def execute(self, context: CustomerContext, slots: SlotsT) -> ActionOutcome: ...


# deterministic/registry.py
class ActionRegistry:
    def get(self, intent: Intent) -> DeterministicAction: ...
    def slot_schema(self, intent: Intent) -> type[BaseModel]: ...   # the clarifier reads this


# matching/base.py
class Embedder(ABC):
    @abstractmethod
    def embed(self, texts: list[str]) -> EmbeddingMatrix: ...       # normalised rows


# matching/catalog.py — built once at startup, kept in memory
class ExemplarCatalog:
    @classmethod
    def load(cls, directory: Path, embedder: Embedder) -> "ExemplarCatalog": ...
    # fails fast: an unknown label, or a label with fewer than `min_exemplars` per language


# matching/matcher.py
class IntentMatcher:
    def __init__(self, catalog: ExemplarCatalog, thresholds: MatchThresholds) -> None: ...
    def match(self, vector: Embedding) -> MatchResult: ...
    # MatchResult.kind ∈ {MATCHED, AMBIGUOUS, NO_MATCH}; candidates sorted by score


# reasoning/clarifier.py
class Clarifier(ABC):
    @abstractmethod
    def clarify(self, state: ConversationState, text: str, match: MatchResult) -> Resolution: ...


# speech/base.py
class SpeechToText(ABC):
    @abstractmethod
    def transcribe(self, audio: AudioClip, language_hint: Language) -> Transcript: ...


# writing/base.py
class ResponseWriter(ABC):
    @abstractmethod
    def write(self, outcome: TurnOutcome, language: Language) -> str: ...


# llm/base.py
class LlmClient(ABC):
    @abstractmethod
    def complete_structured(
        self, tier: ModelTier, prompt: Prompt, schema: type[ModelT]
    ) -> ModelT: ...


# engine/engine.py
class ConversationEngine:
    def __init__(self, speech: SpeechToText, embedder: Embedder, guardrails: GuardrailPolicy,
                 matcher: IntentMatcher, clarifier: Clarifier, actions: ActionRegistry,
                 writer: ResponseWriter, states: ConversationStateStore) -> None: ...

    def handle(self, turn: UserTurn) -> AgentReply: ...
```

**Key contracts (`artifacts.py`):**

- **`MatchResult`**: `kind` (`MATCHED`, `AMBIGUOUS`, `NO_MATCH`) plus the top-k
  `(label, score)` candidates. Guard labels (aggressive, off-topic) live in the same
  catalog, as their own enum, so **one embedding is scored once** for intents and
  guardrails together.
- **`Resolution`** is a pydantic discriminated union on `kind: ResolutionKind`
  (`RESOLVED`, `NEEDS_CLARIFICATION`, `ESCALATED`, `CLOSED`).
  - `RESOLVED` carries `intent: Intent` plus raw slots, validated against the registry
    schema before execution.
  - `NEEDS_CLARIFICATION` carries the question, the candidates and the missing field
    names.
  - `ESCALATED` / `CLOSED` carry a reason enum.
- **`ActionOutcome`** carries `message_key` (enum) and `facts: BaseModel`. It never
  carries free text.
- **`CustomerContext`** holds the `customer_id` taken from the session. **It is the only
  way an action learns who the customer is**: no model output can set or override it
  (protection against reading another customer's data, G13).

### 3.1 Intent matching by similarity

**How it works.** One plain-text file per language and label
(`exemplars/es/account_balance.txt`, one phrase per line: the cheapest format for an LLM to
read or write) lists 10–20
example phrases per intent and per guard label. At startup they are embedded once and
kept in memory as a matrix: a few hundred to a few thousand rows, small enough to fit
easily. Each message is embedded once and compared by cosine similarity. An intent's
score is the score of its best-matching example.

**Decision rule.** With `s1` the best intent's score and `s2` the second-best intent's
score:

| Condition | Result | Next step |
|---|---|---|
| `s1 ≥ accept` and `s1 − s2 ≥ margin` | `MATCHED` | deterministic action (or ask for missing inputs) |
| `s1 < reject` | `NO_MATCH` | the clarifier decides: rephrase, outside the catalog → escalate, or off-topic |
| anything else | `AMBIGUOUS` | the clarifier asks the customer to choose between the top candidates |

**Phase 2 changes to the rule (2026-10-05, measured with `krtr back ia evaluate`):**

1. **The lead must hold over rivals, not only the second intent.** The guard labels
   (`aggressive`, `off_topic`, and the new `unsupported`) count as rivals. `unsupported` holds
   banking requests the agent can't answer (an unrecognised charge, a lost card, a loan):
   without it they scored as high as real balance requests.
2. **Identifiers are stripped before embedding** (`matching_text`): an ID such as "PQR-104233"
   only pulls the message away from the catalog. The slot extractors still read the original
   text.
3. **Thresholds are measured per model and language** (`thresholds.json`), with no wrong
   match, no false flag and no false repeat, and a 0.03 safety gap.
4. **Repetition** counts a message as a repeat in two cases, anywhere in the last 10
   messages:
   - its text is nearly identical to an earlier one;
   - it resolves to the same request (same intent, same details) as an earlier one, however
     it is worded.

   Similarity alone can't separate a rewording from the same question for another product.

**The margin is as important as the threshold.** Two close intents ("card blocked"
versus "card not working") can both score high; matching the first one without a clear
lead is exactly the wrong answer that clarification is meant to prevent.

**Why this fits the language constraint.** A multilingual sentence-embedding model maps
Spanish and Portuguese (and their mix) into the same space. The catalog is written in
both languages, so accuracy depends on our own examples, not on a vendor's language
coverage. It is also the most auditable option: a wrong match is fixed by adding or
editing an example, without touching code.

**Embedding model (decided: `multilingual_minilm`, the only ML model, Q2-A/B).** Run a small
multilingual model **locally, inside the app container**, rather than calling a hosted API. A hosted call would add a network round
trip to every message, while a local one takes milliseconds. Candidates to evaluate in
phase 1 include `paraphrase-multilingual-MiniLM-L12-v2` and `multilingual-e5-small`,
served through an ONNX runtime so the image does not need PyTorch. The model behind
`Embedder` can be swapped without changing anything else.

**Risks:**

1. **Similarity scores are not probabilities.** Their range depends on the model, so
   `accept`, `reject` and `margin` must be set from the evaluation set, separately for
   ES and PT. The evaluation messages must not be the catalog's own examples, or the
   results will look perfect.
2. **Negation and details are weak spots.** "I did *not* make this purchase" and "I made
   this purchase" can embed close together. Intents that differ only by a negation or a
   number need regex checks on their inputs, or must be split by the clarifier.
3. **Off-topic is not the same as low similarity.** A real banking question we do not
   cover also scores low. `NO_MATCH` therefore goes to the clarifier, which decides
   between rephrase, escalate and off-topic. A guard match only flags; **the
   conversation is closed only after the clarifier confirms**, because closing by
   mistake is costly.
4. **The deployment gets heavier.** The model weights go into the Modal image and load
   at startup, which adds to the cold start. This is acceptable under the demo mode
   (D17, always on), but it needs measuring.

## 4. Layout

```
krtr/back/ia/
  config.py              IaConfig: clarification limit, thresholds, model per tier, timeouts
  artifacts.py           UserTurn, AgentReply, ConversationState, CustomerContext
  engine/                ConversationEngine, ConversationStateStore (protocol)
  matching/              base.py (Embedder), catalog.py, matcher.py, config.py (MatchThresholds),
                         artifacts.py (MatchResult), labels.py (GuardLabel enum)
    exemplars/           <language>/<label>.txt — one phrase per line, per Intent and GuardLabel
    onnx/                OnnxEmbedder (local multilingual model)
  deterministic/         intents.py, base.py, registry.py, slot_extraction.py, actions/<intent>.py
  guardrails/            GuardrailPolicy: repetition, guard-label flags, closure protocol
  reasoning/             clarifier.py (Clarifier), artifacts.py (Resolution)
    llm/                 LlmClarifier
  speech/                base.py, <provider>/
  writing/               base.py, templates/ (ES + PT message catalog), llm/
  llm/                   base.py, ModelTier enum, <provider>/
krtr/back/web/chat/      AgentChatResponder(ChatResponder) → ConversationEngine.handle
tests/back/ia/...        1:1 mirror; every ABC gets a fake in a fakes.py
```

The web layer only knows `ChatResponder`; `create_served_app` builds the engine and
injects it, the same way `auth_services` is wired today.

## 5. How the goals map

| Goal | Where it lives |
|---|---|
| G1 recurring questions | `matching/exemplars/` + `deterministic/actions/`: the no-model fast path |
| G8 / G10 voice, phased | `speech/`; text-only first, the engine skips STT when `turn.audio` is None |
| G11 reasoning in text | Matching and the clarifier always work on text (voice is transcribed first) |
| G12 cost routing | Matcher first (free); LLM only on `AMBIGUOUS` / `NO_MATCH` / missing inputs |
| G13 hard rules | `guardrails/` (repetition by similarity, guard labels) + clarifier confirmation; `CLOSED` outcome |
| G14 ES / PT | Multilingual embedder + catalog per language + template catalog per language + `language/`: reply language detected per conversation (py3langid), the interface's language only as the starting hint |
| G16 latency | Fast path: local embedding + action + template, no network model call |
| G17 summary | `ConversationState.summary`, updated after each turn |
| G19 ambiguity | `AMBIGUOUS` result and missing inputs → `NEEDS_CLARIFICATION` |
| G20 human handoff | `ESCALATED`: clarification limit reached, outside the catalog, high-risk intent |

## 6. Testing

- **Deterministic actions:** plain unit tests, every branch; they are the business logic.
- **Matcher:** unit tests with a fake embedder (fixed vectors) for the decision rule:
  threshold, margin, and the boundary between `MATCHED` and `AMBIGUOUS`. Catalog loading
  must fail fast on unknown labels and on intents with too few examples.
- **Engine:** tests with fakes for every non-deterministic component, which make every
  path through the pipeline reproducible (including the clarification limit and the
  closure rules).
- **Evaluation set:** labelled ES + PT messages, *distinct from the catalog examples*,
  each mapped to its expected `MatchResult` / `Resolution`. Run from the CLI to set the
  thresholds and to catch regressions when examples change. It is not part of `pytest`,
  since the clarifier's results vary between runs.

## 7. Implementation phases

1. **Interfaces + engine + fakes + template writer + template clarifier + 2 actions +
   slot regexes + matcher decision rule and catalog loader** (with a fake embedder). Gives
   an end-to-end deterministic flow. Plan: `tasks/todo.md`.
2. **`OnnxEmbedder` + catalog content + the evaluation set.** Choose the model and set
   the thresholds per language. The catalog content comes from the intent discovery
   track in `tasks/todo.md` (deduplicated call history + complaints, labelled and
   paraphrased in ES / PT by an LLM, reviewed by us).
3. **`LlmClient` + `LlmClarifier`** with a local Hugging Face model (Qwen2.5-1.5B-Instruct
   through `onnxruntime-genai`, decided 2026-10-05): interpreting free-form replies,
   extracting free-text inputs, confirming guardrail closures, and handing `unsupported`
   requests to a person. Plan: `tasks/todo.md`.
4. **`SpeechToText`** (G10 phase 2): a local Whisper model chosen from a `SpeechToTextModel`
   Enum. Outline: `tasks/todo.md`.
5. **Optional `LlmResponseWriter`**, with the check that it adds no facts.

## 8. Open questions

- **Q1 — Embedding model:** do you agree with running it locally (ONNX inside the app
  container), and with comparing the two candidates in phase 2?
- **Q2 — Intent catalog:** which deterministic actions do we support first, and what are
  their required inputs? Each one also needs its example phrases in ES and PT. This
  defines the whole vertical.
- **Q3 — Clarification limit:** what value, and does escalating after it count as a
  handoff to a human (G20)?
- **Q4 — Writer:** templates by default with the LLM optional, or the LLM always?
- **Q5 — Persistence:** **decided (2026-10-05).** Contract in §9.
  - Each turn's metadata (outcome, intent, match kind, guard flags, language, timings) goes
    to `events` as `chat_response_received`, never the text.
  - The message and reply text go to a new `messages` table.
  - Still open: where `ConversationState` lives, and where the case summary (G17) lives
    (proposed: the cases table of web task 4.8).
- **Q6 — Providers:** LLM and speech-to-text vendors, each added as a sub-vertical under
  `llm/` and `speech/`.

> **Considered and dropped — Jev (TypeSafe AI).** A cheap, calibrated decision model
> that would have answered guardrails and intent in one call. Dropped because its
> primary language is English and its Spanish / Portuguese accuracy is not documented
> (G14 is a hard requirement). It could still return later behind the same matcher
> interface, if a measured evaluation in ES / PT shows it is reliable.

## 9. Persistence (decided 2026-10-05)

| What | Where | Why |
|---|---|---|
| Turn metadata: `outcome`, `language`, `timings`, and `details` (intent, match kind, guard flags) | `events`, as `chat_response_received`, written by the web chat endpoint (task 4.9) | Every response is audited with its latency (G16, G21), without storing what was said. |
| Message and reply text | New `messages` table | Replies carry balances and masked card numbers, and resuming a case needs its messages by case, which `events` cannot provide. |

**The `messages` table:**

| Column | Type | Meaning |
|---|---|---|
| `message_id` | `UUID` PK | Unique ID of the message, generated by the app. |
| `incident_id` | `VARCHAR(30)` | The case the message belongs to (G17). |
| `customer_id` | `VARCHAR(20)` | The case's customer; every read filters by `incident_id` + `customer_id`. |
| `sender` | `VARCHAR(10)` | Who wrote it: `customer` or `agent`. |
| `content` | `BYTEA` | The text, encrypted with AES-256-GCM (nonce + ciphertext), like `events.properties`. |
| `language` | `VARCHAR(5)` | `es` or `pt-BR`. |
| `outcome` | `VARCHAR(30)` | Agent messages only: how the turn ended. |
| `sent_at` | `TIMESTAMPTZ` | When it was sent, in UTC. |

- **Encrypted:** with its own key, `KRTR_MESSAGES_KEY`, kept apart from the events and tokens
  keys.
- **Retention:** 3 months, purged by the same daily job as `events`.
- **Index:** on `(incident_id, customer_id)`, explicitly requested, as an exception to the
  `CLAUDE.md` no-index rule.
- **Recorded in:** the web guide (`docs/guia-web-seguridad_modal.md` §3.6, 6.1 and 6.5).

