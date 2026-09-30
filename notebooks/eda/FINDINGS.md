# Business opportunities across everything analysed so far

_Last updated: 2026-09-26 · Sections 1-5 cover the first two hypotheses under `notebooks/eda/`: [delinquency](delinquency_hypothesis/FINDINGS.md) and [compensations / complaints](compensations_hypothesis/FINDINGS.md). A third hypothesis, [physical places / branches](physical_places_hypothesis/FINDINGS.md), has its own graded opportunities in its findings file and is summarised in section 7._

**How to read this.** Every number below comes from an executed notebook; the *Source* column says which. Nothing is
extrapolated beyond what the notebooks show. Where the data cannot answer something, it says so. Opportunities are graded:

| Grade | Meaning |
|---|---|
| **A** | The situation is measured in the data and an action follows directly. The *benefit* of the action is still untested. |
| **B** | Conditional: it depends on confirming that the data reflects reality (see the warning below). |
| **Prerequisite** | Not a saving by itself; without it the other opportunities cannot be measured or built. |

> **Read this first.** In every dataset we found signs that it was generated independently of business behaviour (for example
> `days_past_due` takes only 7 values and the delinquency rate is a flat ~15% in every segment; complaint stage durations are
> uniform; 13 distinct survey comments; the complaint's affected product never belongs to the complainant). Findings about
> **size and structure** are facts about these files. Findings about **relationships** (who pays, what satisfies) should not be
> assumed to transfer to production until they are reproduced on real operational data.

---

## 1. Summary

| # | Opportunity | Grade | What the data supports | What it cannot tell us |
|---|---|:---:|---|---|
| **O1** | Work the delinquent list in **balance order** (no model needed) | A | The money is concentrated: the top 10% of delinquent customers hold ~77% of the delinquent balance in each currency, mostly mortgages | How much cash a prioritised list would bring in (no payment data) |
| **O2** | **Repair contact data**, above all Mexico | A | Half of delinquent customers are Mexican, none has a dialable mobile as recorded, and they hold 92% of the USD delinquent balance | Whether the numbers are recoverable, and how much contact changes payment |
| **O3** | Use **deposit accounts** as a channel for delinquent customers | B (low priority) | 71.5% of delinquent customers have an Active deposit account | Whether the funds can be used, and it covers only 8-9% of the balance |
| **O4** | **Speed up the early stages of complaints** (assignment, first response, escalations) | B | Real gaps in the queue and no differentiation by priority; but the early stages are only ~10% of time to resolution | Whether the queue is real, and any agent's effect on resolution |
| **O5** | **Clear the complaint backlog** | B | 74.9% of complaints are in an active status | Whether that backlog is real: the resolved share is ~25% at every complaint age |
| **O6** | **Standardise and test compensation policy** | B | 1.17 M raw units granted with no visible rule and no measured satisfaction or retention difference | The currency of the spend, or what would happen if it changed |
| **O0** | **Fix the data foundations** (links, payments ledger, status history, valid NPS) | Prerequisite | Each missing link is measured below | n/a |

**Not supported by the data** (do not build a business case on these): a time-to-payment model, payment recency as a delinquency
signal, compensation or speed as levers for satisfaction, NPS, the SLA flag, agent rankings, and the survey comments. See section 4.

---

## 2. The opportunities and their evidence

### O1. Work the delinquent list in balance order (grade A)

*Context:* the earlier hypothesis was to predict who pays soon. That is not supported (section 4). What the data does support is a
plain prioritisation by exposure.

| Evidence | Value | Source |
|---|---|---|
| Delinquent credit products / customers | 18,765 products; 17,650 customers (20.8% of credit customers) | `products.ipynb`, `cutomers.ipynb` |
| Delinquent customers with at least one `Active` delinquent product | 15,089 | `products.ipynb` |
| Top 10% of delinquent customers hold (share of delinquent balance, per currency) | ARS 77.5%, COP 77.1%, USD 77.1% (top 20%: 86.8% / 86.5% / 86.7%) | `cutomers.ipynb` 6b |
| Why: mortgages are 9.2% of delinquent products but hold | ARS 75.4%, COP 75.2%, USD 76.2% of the delinquent balance | `cutomers.ipynb` 6b |
| Delinquent balance at the exchange rates implied by the transactions file (350 ARS/USD, 4,000 COP/USD) | ~181.8 M USD-equivalent, ~153.9 M of it on `Active` products | `transactions.ipynb` 3 |
| Arithmetic: 1% of the Active delinquent balance | ~1.5 M USD-equivalent | derived from the line above |

*What a work list would target:* mortgage holders first. *Caveats:* the balance is the **total** on the product, not the overdue
amount (the data has no overdue amount); the exchange rates are an assumption read off the data, not market rates; and the
concentration is in balance, not in who will pay.

*How to prove it:* run the balance-ordered list for a period against a comparable untouched group and measure cash collected. That
also produces the payment timing data the file lacks.

### O2. Repair contact data, above all Mexico (grade A)

| Evidence | Value | Source |
|---|---|---|
| Delinquent customers by country (Argentina / Colombia / Mexico) | 3,494 / 5,339 / **8,817** (Mexico = 50%) | `cutomers.ipynb` 6c |
| Delinquent customers with a mobile on file that carries a valid prefix for their country | Argentina 3,373, Colombia 5,183, **Mexico 0** (all 8,544 Mexican mobiles on file carry +54, Argentina's code) | `cutomers.ipynb` 2, 6c |
| Delinquent customers with a usable mobile **or** an unshared email | Argentina 98.2%, Colombia 98.4%, **Mexico 43.1%** (overall 70.7%) | `cutomers.ipynb` 6c |
| Emails shared by more than one customer | 79,930 customers on 24,203 shared addresses, up to 31 per address; only 45.4% of delinquent customers have an unshared email | `cutomers.ipynb` 2, 6c |
| Money behind the Mexican gap | Mexican customers hold only USD products: **93.9 M of the 102.0 M USD delinquent balance (92.0%)** | `cutomers.ipynb` 6c |

So the gap in reachability is concentrated where about half of the delinquent exposure sits. *Caveats:* a wrong prefix does
not prove the rest of the number is right, and the data has no record of contact outcomes, so what better contact data would
change in payments is unknown.

### O3. Use deposit accounts as a channel for delinquent customers (grade B, low priority)

| Evidence | Value | Source |
|---|---|---|
| Delinquent customers with an `Active` savings or checking account | 12,625 of 17,650 (71.5%) | `cutomers.ipynb` 6d |
| Customer-currency pairs where the same-currency deposit covers the whole delinquent balance | ARS 1,564 of 3,170; COP 2,420 of 4,826; USD 4,707 of 9,752 | `cutomers.ipynb` 6d |
| Share of the delinquent balance in those covered cases | ARS 0.96 bn of 11.4 bn (8.4%); COP 17.6 bn of 188.9 bn (9.3%); USD 8.7 M of 102.0 M (8.5%) | `cutomers.ipynb` 6d |

Roughly half of the pairs are fully covered, but they are the small exposures (~8-9% of the balance). Whether these funds are
available or may be used is a legal and product question the data cannot answer, hence grade B and low priority.

### O4. Speed up the early stages of complaints (grade B)

| Evidence | Value | Source |
|---|---|---|
| `Open` complaints with no agent assigned | 20,125 | `complaints.ipynb` 4 |
| `Escalated` complaints with no first response | 3,321 | `complaints.ipynb` 4 |
| Complaints that never had an agent (any status) | 23,115 | `complaints.ipynb` 4 |
| Median hours to assignment / to first response; median days to resolution | 12 / 38 / 16 | `complaints.ipynb` 4 |
| The process does not differentiate by priority | Critical 15.5 days vs Low 15.7 (mean, resolved cases) | `complaints.ipynb` 4 |
| `Regulator` channel (1.07% of complaints) | resolved in 16.4 days on average (178 cases), no faster than others | `complaints.ipynb` 3, 4 |
| **Upper bound of what automating the early stages could save** | the wait before the first response is **~10%** of the time to resolution | `complaints.ipynb` 4 |

An agentic workflow that only triages, assigns and sends the first response can therefore shorten resolution by **at most
about a tenth** if the rest of the process is unchanged; the remaining ~90% is resolution work, whose improvement this data
cannot evaluate. *Caveats:* the complaint file has no free text, no effort or cost per case, and its link to interactions is empty, so
an agent's quality cannot be tested on it; and section O5 explains why the queue itself may not be real.

### O5. Clear the complaint backlog (grade B, conditional on validation)

| Evidence | Value | Source |
|---|---|---|
| Complaints in an active status (Open, In Process, Escalated) | 50,269 of 67,095 (74.9%) | `complaints.ipynb` 4 |
| Of those, older than one year | 33,413 | `complaints.ipynb` 4 |
| **Warning sign:** share of complaints in a terminal status, by age | ~25% at every age (25.4% for the last 30 days; 24.9% for over two years) | `complaints.ipynb` 4 |

At face value this is the largest operational opening in the data. But in a real queue older complaints are far more likely to
be resolved, and here they are not. Either the real backlog is enormous or the statuses do not reflect a real queue. **This must be
confirmed with the system owners before the backlog is used to justify anything.**

### O6. Standardise and test compensation policy (grade B)

| Evidence | Value | Source |
|---|---|---|
| Compensation granted | 4,641 grants; 28.8% of Resolved and Closed complaints; **1,174,810 raw units** over three years (mean 253, range 10-500) | `complaints.ipynb` 5 |
| **Unit unknown** | the file has a currency only for the claimed amount, not for the compensation | `complaints.ipynb` 5 |
| No visible rule | 27-31% granted for every category, priority, case type and resolution text (including the text saying "compensation granted"); the amount does not follow the claim (median 10% of the claim, Spearman 0.03; 62 grants exceed it) | `complaints.ipynb` 5 |
| Not related to time to resolution | 27-30% granted in every resolution-time band; mean amount 247-260 | `complaints.ipynb` 5 |
| No measured satisfaction difference (complaint ratings) | 3.00 with vs 3.02 without (+/-0.13; 690 vs 1,684 ratings) | `complaints.ipynb` 6 |
| No measured satisfaction difference (surveys, CSAT 1-4, customer level) | 2.77 with vs 2.76 without (2,655 vs 28,451 customers) | `satisfaction_surveys.ipynb` 6 |
| No difference in customer status today | 14.2% not `Active` with vs 14.2% without compensation (cross-sectional) | `complaints.ipynb` 8 |

Grants look arbitrary, and the spend has no measurable association with satisfaction or status in this data. That justifies two
things: **writing explicit rules** and **a controlled test** of tighter or different compensation. It does **not** prove that
compensation has no value: the evidence is observational, the data looks generated, and the unit of the spend is unknown, so its
money value cannot be stated.

### O0. Fix the data foundations (prerequisite)

Each missing link blocks a hypothesis. All are measured facts:

| Gap | Evidence | Blocks | Source |
|---|---|---|---|
| No obligation-level payments ledger | `Payment` appears on all eight product types (170,603 of 263,827 products with payments are not credit products); amounts 50-2,000 USD-equivalent whatever the balance; 18.8% of payments predate the product's opening | Any time-to-payment work | `transactions.ipynb` 4; `transactions_history.ipynb` 6 |
| No repeated `days_past_due` snapshots | One row per product at a single date; only 7 distinct values | Delinquency episodes, roll rates | `products.ipynb` 4 |
| Survey-to-complaint link missing | `origin_interaction_id` is empty on every complaint | Testing satisfaction against resolution time per case | `complaints.ipynb` 2; `satisfaction_surveys.ipynb` 6 |
| Complaint not tied to its customer's products | 0% of affected products belong to the complaining customer | Product-level complaint analysis | `complaints.ipynb` 8 |
| No status history, effort or cost per complaint | One status per complaint; no handling-time field | Sizing any workflow saving | `complaints.ipynb` 2, 4 |
| Satisfaction barely measured | 3.7% of complaints rated; NPS on a 2-7 scale (no Promoter possible, implied NPS -74.5) | Any satisfaction claim | `complaints.ipynb` 6; `satisfaction_surveys.ipynb` 2 |
| No survey denominator | Only answered surveys are present | A real response rate | `satisfaction_surveys.ipynb` 2 |
| No free text | 5 description and 5 resolution sentences; 13 survey comments | Evaluating a text-based agent | `complaints.ipynb` 2; `satisfaction_surveys.ipynb` 5 |

---

## 3. Suggested order

1. **O2 now** (repair Mexican contact data and shared emails): the gap is measured and the fix is checkable.
2. **O1 as an experiment** (balance-ordered work list against a control), together with O2. It also creates the first real payment-timing data.
3. **Confirm O5 with the system owners.** The answer decides whether O4 and the workflow case exist at all.
4. **O0 in parallel:** the ledger, status history, effort data and survey links, so that O4 and O6 can be measured.
5. **O6 as a controlled test** once compensation currency and policy are known.
6. **O3** last, only if legal and product rules allow it.

---

## 4. What the data does not support

| Idea | Why not | Source |
|---|---|---|
| A **time-to-payment model** | There is no payment target and no signal: delinquency is ~15% in every segment of every product and customer attribute, unrelated to June behaviour, and unrelated to payment recency or payments after the implied delinquency start | `products.ipynb`; `cutomers.ipynb` 5; `transactions.ipynb` 5; `transactions_history.ipynb` 4-5 |
| Using **days since last payment** to derive delinquency | Median 222-253 days at every `days_past_due` level; payments arrive at random (5.5% of gaps within 25-35 days vs 5.3% expected at random) | `transactions_history.ipynb` 3-4 |
| Ranking **customers by credit score or income** to find who is delinquent | Delinquent share is 20-22% in every score band and income quintile (overall 20.8%) | `cutomers.ipynb` 5 |
| **Speed or compensation as levers for satisfaction** | No relationship at complaint, customer or agent level (rho about -0.03 to -0.01, with 212,759 surveys), but only inside 1-30 days among resolved complaints: none was resolved in under a day, so the effect of fast resolution is unobserved | `complaints.ipynb` 6; `satisfaction_surveys.ipynb` 6 |
| **Ranking agents** | Spread of agents' average results equals chance (resolution days 2.44 vs 2.42; CSAT 0.06 vs 0.06) | `complaints.ipynb` 7; `satisfaction_surveys.ipynb` 4 |
| Quoting **NPS** | Scale is 2-7; no Promoter exists | `satisfaction_surveys.ipynb` 2 |
| Treating **`Premium` / `Plus` as a value tier** (more products, larger limits or balances) | Products per user, credit limit and balance are the same in every segment; only the credit score differs (section 6) | `segment_profile.ipynb` 5-6 |
| Using the **SLA flag** as a KPI | ~20% breached for every priority, time to resolution and status | `complaints.ipynb` 4 |
| Using the **survey comments** as evidence | 13 distinct texts; customers who wrote "I waited too long" rate waiting time 3.0 of 5, the same as those who wrote "excellent attention" | `satisfaction_surveys.ipynb` 5 |
| The **repeat-complainer flag** | Flagged and unflagged customers have the same average number of complaints (1.44 vs 1.45) | `complaints.ipynb` 7 |

---

## 5. What is still unknown

- Whether prioritising by balance (O1) or better contact data (O2) changes cash collected.
- Whether the complaint queue (O5) is real, and therefore how large O4 is.
- The currency and policy behind compensation (O6).
- Any cost or effort figure: none of the datasets contains one, so **no monetary saving is stated anywhere in this document**. The
  amounts quoted are exposures (delinquent balance, compensation granted), not savings.

---

## 6. Customer segment profile (descriptive statistics)

Built from `customers.csv` and `products.csv` in [segment_profile.ipynb](segment_profile.ipynb) (summary exported to
[segment_profile_summary.csv](segment_profile_summary.csv)). A product belongs to the segment of its owner.

| | Basic | Plus | Premium | Student | All |
|---|---:|---:|---:|---:|---:|
| Customers | 89,756 | 37,547 | 15,207 | 7,490 | 150,000 |
| **Products per user**, all customers (mean / median) | 2.67 / 2 | 2.68 / 3 | 2.64 / 2 | 2.67 / 2 | 2.67 / 2 |
| Products per user, customers with at least one product (mean) | 2.87 | 2.88 | 2.84 | 2.87 | 2.87 |
| **Credit limit** per credit product, USD-eq (mean / median) | 38,038 / 30,581 | 37,934 / 30,507 | 37,620 / 30,430 | 38,876 / 31,294 | 38,011 / 30,588 |
| **Current balance** per product, USD-eq (mean / median) | 5,610 / 2,437 | 5,559 / 2,434 | 5,655 / 2,416 | 5,538 / 2,473 | 5,598 / 2,436 |
| **Credit score** (mean / median / std) | 599.5 / 600 / 40.0 | 699.2 / 699 / 39.8 | 797.4 / 799 / 36.7 | 649.0 / 649 / 40.0 | 647.1 / 631 / 76.9 |
| Credit score missing | 15.0% | 15.2% | 14.4% | 15.1% | 15.0% |

The notebook also has the full statistics (count, standard deviation, min, max), balances split into credit products (debt)
and deposit accounts (assets), totals per customer, breakdowns by product type and 95% intervals for each mean.

**Reading.**

- **Only the credit score separates the segments**: Basic 599.5, Student 649.0, Plus 699.2, Premium 797.4, with a standard
  deviation of about 40 inside each (intervals of +/-0.3 to +/-1.0 points).
- **Everything else is the same in every segment**, within the 95% intervals: products per user (2.64-2.68), credit limit
  (mean 37,620-38,876; intervals +/-234 to +/-830), current balance (mean 5,538-5,655), and the product mix (about 76% cards,
  15% personal loans, 9% mortgages). The Plus median of 3 products against 2 elsewhere only reflects means sitting at the
  edge between two whole numbers.
- So in this data the segment behaves as a **credit-score band**, not as a wealth or engagement tier.

**Definitions and caveats.**

- Amounts are **USD-equivalent at the rates implied by the transactions file** (350 ARS/USD, 4,000 COP/USD), an assumption
  read off the data, not a market rate.
- The credit limit exists only on credit products (cards, personal loans, mortgages). 6,655 of the 131,972 have none and are left out.
- Products per user counts every product (all types and statuses), with the 10,422 customers who own no product counted as 0
  in the "all customers" row.
- Means sit far above medians for limits and balances (for example a balance mean of 5.6 k against a median of 2.4 k) because
  mortgages are much larger than cards; medians describe a typical product better.

---

## 7. Physical places (branches): summary

Full evidence in [physical_places_hypothesis/FINDINGS.md](physical_places_hypothesis/FINDINGS.md), from
[branches.ipynb](physical_places_hypothesis/branches.ipynb). No branch stands out: transactions, products opened, complaints and
delinquency per branch vary as much as chance predicts and do not follow branch type, capacity, city, status or age.

| # | Opportunity | Grade | Evidence |
|---|---|:---:|---|
| **P1** | Repair location and link data | Prerequisite | 167 of 350 coordinates are placeholders; all 175 Mexican branches carry the wrong phone prefix; 5 of 150,000 customers link to a branch |
| **B1** | Validate and, if real, rebalance branch density | B | Customers per branch range 290 (Córdoba) to 869 (Rosario), 3.0x; customers do not use their city's branch in this data |
| **B2** | Reallocate or standardise ATM and teller capacity | B | 2-8 ATMs per branch with flat demand: 0.39-1.71 transactions per ATM per day (relative only) |
| **B3** | Clarify the 14 `Temporarily Closed` branches | A (verify status) | Same activity as open branches; 15,967 products opened there, 13,574 `Active` |
| **B4** | Reassess the branch as an acquisition channel | B | Teller channel is 3.0% of transactions; the Branch opens 50.0% of products |

Not supported: ranking branches, branch-type strategy, opening-hours optimisation, underwriting or collections by branch, geospatial analysis.

**AI-agent lens (preliminary).** There is no sign of an ATM availability or teller capacity problem: failure rates are the same in every
channel and load per ATM and per teller window is far below capacity at every hour and day. Human-handled jobs visible in the last
12 months total 92,098 (teller transactions 41,999, products opened at a branch 25,122, call-center complaints 11,321, others
19,656), about 1,535 staff hours per minute of average handling time. Handling time and labour cost are not in any file, so no
saving can be ranked in money yet. See sections 7-8 of the physical places findings.
