# Intent catalog — labelled sources (phase 2, tracks D.1–D.2)

_2026-10-05 · For review. Labelled by Claude in session, in place of a separate LLM pipeline (task 2.5)._

## D.1 — Where the texts come from (offline)

| Source | Texts | How they were read |
|---|---|---|
| Call history (`call_transcripts`) | 6 distinct customer lines, all Spanish | `notebooks/eda/call_transcripts/causes.ipynb` (the 171,321 transcripts hold only 12 distinct lines) |
| `complaints` table (Neon) | 5 categories, 5 subcategories, 5 templated descriptions ("Queja relacionada con fees") | `SELECT category, subcategory, description, count(*) … GROUP BY` |

The complaint `description` is a template that just names the category, so it adds no
wording. In the live flow the text comes from the web page, not from these sources (Q2-C).

## D.2 — Labels

**Deterministic** means an action can answer the text from data held for that customer.
**Hard** means it needs a person or a capability the agent doesn't have. **Not an intent**
means the text only makes sense as a follow-up in a conversation.

| Text (source) | Label | Why |
|---|---|---|
| "Hola, buenos días. Quisiera saber cuál es mi saldo actual en mi cuenta de ahorros." (calls, 50%) | `account_balance` — deterministic | `products.current_balance` for the savings account |
| "Buenas tardes, necesito consultar el saldo de mi tarjeta de crédito." (calls, 50%) | `account_balance` — deterministic | Balance and `credit_limit` of the card |
| "¿Y eso cuánto tiempo tarda?" (calls, 15%) | Not an intent | Refers to something said earlier; the clarifier handles it (phase 3) |
| "Muy bien, ¿hay algo más que deba saber?" (calls) | Not an intent | Open follow-up; nothing to look up |
| "Entiendo, muchas gracias." / "Perfecto, eso es lo que necesitaba." (calls) | Not an intent — **candidate** `goodbye` | A fixed reply would close the case politely; it needs a new action, so it is not part of this phase |
| Status of an existing complaint (`complaints.status`; three in four are still active) | `complaint_status` — deterministic | Status, category and date of one of the customer's complaints |
| Cargo no reconocido (Transactions) | Hard | Needs a dispute investigation |
| Cobro indebido (Fees) | Hard | Needs a review and possibly a refund |
| Problema con app (Technical) | Hard | Technical support |
| Atención en sucursal (Branch) | Hard | Service complaint about a branch |
| Calidad de servicio (Service) | Hard | Service complaint |

**What this means for the catalog:**
- Only `account_balance` and `complaint_status` get example phrases.
- The hard texts and the follow-ups go into the evaluation set as `none` messages. They must
  never match either intent: a complaint about an unknown charge must not get a balance
  reply, nor a complaint-status one.

**Candidates for later phases:**
- `goodbye`, a deterministic polite close;
- `file_complaint`, which hands the case over with its category (G20). The 5 hard themes
  are exactly its categories.
