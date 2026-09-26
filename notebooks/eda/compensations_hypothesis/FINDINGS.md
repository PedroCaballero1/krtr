# Findings log: agentic complaint workflow, compensation and satisfaction

> **Business opportunities across all hypotheses, graded by evidence:** see [../FINDINGS.md](../FINDINGS.md).

_Last updated: 2026-09-26 · Datasets covered so far: `complaints` and `satisfaction_surveys` (both 2023-06-17 to 2026-06-17, 1,097 daily files each)_

Every number here comes from the executed notebooks [complaints.ipynb](complaints.ipynb) and [satisfaction_surveys.ipynb](satisfaction_surveys.ipynb). When a new dataset is
analysed (interactions, customer outcomes...), add a row to the status table and a section below.

---

## TL;DR

| Question | Answer today |
|---|---|
| Is there an opportunity for an agentic workflow that resolves complaints better and faster? | **Plausible, not demonstrated.** At face value the queue is large, slow and undifferentiated, but the data cannot confirm the queue is real, cannot size the benefit, and has no text to evaluate an agent on. |
| How much compensation is granted? | **4,641 grants** (6.9% of complaints; 28.8% of resolved/closed), **1,174,810 raw units** in total (mean 253, range 10-500). No currency on compensation. |
| How satisfied are customers? | Mean **3.02 / 5**, but only **3.7% of complaints are rated** (only `Closed` cases), and scores are uniform (~20% each). |
| Are compensation and satisfaction related to time-to-resolution? | **No.** Satisfaction, compensation rate and compensation amount are all flat across resolution-time bands; compensation does not raise satisfaction. |
| Do the 212,759 satisfaction surveys change that? | **No.** With ~85x more ratings (212,759 vs 2,484) the result holds at customer and agent level (rho -0.02 and -0.01), so sample size was not the reason. Surveys cannot be linked to complaints at the interaction level. |
| Next step? | Confirm with the system owners whether the ~75% active backlog is real; instrument time-in-state, effort and CSAT; then pilot on new complaints against a control. |

**Business idea being tested:** an agentic workflow (triage, routing, first response, resolution support) could solve
complaints better and faster; and compensation / satisfaction should be quantified against time-to-resolution.

---

## 1. Status by dataset

| Dataset | Notebook | Rows | Verdict |
|---|---|---|---|
| `complaints` (all history) | [complaints.ipynb](complaints.ipynb) | 67,095 complaints, 54,145 customers, 1,200 agents | Baseline measured; opportunity plausible but unconfirmed; no relationship between time, compensation and satisfaction |
| `satisfaction_surveys` (all history) | [satisfaction_surveys.ipynb](satisfaction_surveys.ipynb) | 212,759 surveys, 113,640 customers, 1,090 agents | Scores unrelated to anything observable; no link key to complaints; NPS invalid; adds a baseline and pilot sensitivity |

---

## 2. Baseline: volume, backlog and speed

![Complaints per month](figures/complaints_monthly_volume.png)

| Metric | Value |
|---|---:|
| Complaints (3 years) | 67,095 |
| Per full month (median) | 1,874 (flat, no trend) |
| **Active backlog** (Open + In Process + Escalated) | **50,269 (74.9%)** |
| ...of which older than 1 year | 33,413 |
| `Open` with no agent assigned | 20,125 |
| `Escalated` with no first response | 3,321 |
| Complaints that never had an agent | 23,115 |
| Median hours to assignment / first response | 12 / 38 |
| Median days to resolution (resolved cases) | 16 |
| Share of resolution time spent waiting for the first response | ~10% |

The process does not differentiate cases: **Critical takes as long as Low** (15.5 vs 15.7 days), a `Regulator`
complaint takes as long as any other, and resolution time is unrelated to category, channel or case type. Agents
are interchangeable: the spread of their average resolution time (2.44 days) equals what chance gives with identical agents (2.42).

### Can we trust the backlog?

![Share in a terminal status by complaint age](figures/complaints_terminal_share_by_age.png)

The share of complaints that are resolved, closed or rejected is ~25% **at every age**, last month's complaints
as much as those from 2023. In a real queue, older complaints are far more likely to be resolved. So either the real backlog is
enormous, or statuses were assigned at random. **This decides whether the opportunity is real** and must be confirmed with the owners.

---

## 3. Compensation granted

| | |
|---|---:|
| Grants | 4,641 (6.9% of complaints; 28.8% of Resolved + Closed) |
| Total granted (raw units, no currency) | 1,174,810 |
| Mean / median per grant | 253 / 253 (range 10-500) |
| Median grant as a share of the claimed amount | 10% (only 1,453 grants have a claim; 62 exceed it) |

Compensation looks **arbitrary**: 27-31% are granted whatever the resolution text (including the one that says
"compensation granted"), category, priority or case type; the amount does not follow the claim (Spearman 0.03). The
`Regulator` channel is the only outlier (36.5% on 181 cases, barely beyond noise). Compensated customers are not
less likely to be inactive today (14.2% not `Active` in both groups; a cross-sectional check only).

**The unit is unknown.** Compensation has no currency column, and the amounts are 10-500 in every claim currency.

---

## 4. Satisfaction, and relations with time-to-resolution

![Satisfaction and compensation rate by time to resolution](figures/complaints_satisfaction_and_compensation_by_resolution_time.png)

| Check | Result |
|---|---|
| Ratings | 2,484 (3.7% of complaints, 95% of `Closed`, none on `Resolved`) |
| Mean rating | 3.02 +/- 0.06; scores 1-5 hold ~20% each |
| Satisfaction, fastest (0-5 d) vs slowest (25-30 d) band | 3.11 vs 2.96 (0.15 drift, within +/-0.14 noise per band) |
| Spearman: days to resolution vs satisfaction | -0.03 |
| Compensated vs not | 3.00 vs 3.02 (+/-0.13) |
| SLA breached vs not | 2.99 vs 3.02 (+/-0.14) |
| Compensation rate by resolution-time band | 27-30% in every band; mean amount 247-260 |

The sample resolves differences of about 0.13 rating points, so a quarter-point effect would have shown. This is
evidence of **no relationship**, not lack of data: faster resolution does not raise satisfaction, compensation does not
raise satisfaction, and slower cases are not compensated more. We cannot claim that speeding up resolution would improve
satisfaction, or that compensation buys goodwill.

---

## 5. Satisfaction surveys (212,759 surveys)

The survey file is per **interaction** and much larger than the complaint ratings (which cover 3.7% of complaints).

### 5a. Structure: three surveys, three scales

![Score distribution by survey type](figures/surveys_score_distribution_by_type.png)

| Type | Share of surveys | Scale | Mean |
|---|---:|---|---:|
| CSAT | 60% | 1-4 | 2.77 |
| NPS | 30% | **2-7** | 5.31 |
| CES | 10% | 1-4 | 2.77 |

The NPS cannot be a real NPS: the scale stops at 7, so **no Promoter exists** and the implied NPS (-74.5, 74.5% Detractors
of categorised surveys) is an artefact of the scale. The three follow-up questions are uniform 1-5 and independent of the
score; a comment is written on ~47% of surveys at every score; sentiment is a function of the score band; there are only 13
distinct comments.

### 5b. Scores are driven by nothing

![Mean CSAT per quarter](figures/surveys_csat_by_quarter.png)

CSAT is 2.77 (of 4) in every channel, quarter (2.75-2.78), segment, country and customer status. The spread of agents'
average scores equals chance (0.06 vs 0.06, identical agents). Rank correlations with follow-up answers, response time and
campaign response rate are ~0.

### 5c. Themes in the comments

![Themes in negative comments](figures/surveys_negative_comment_themes.png)

30% of surveys carry a negative comment: **waiting time 40%, problem not resolved 40%, unclear explanation 20%**. At face value,
half of the dissatisfaction is about speed and half about resolution. But customers who wrote "I waited too long" rate
"was the waiting time acceptable?" **3.0 of 5, the same as those who wrote "excellent attention"**, so the comments carry
nothing beyond the score band and are weak evidence.

### 5d. Link to complaints: none at interaction level

`origin_interaction_id` is empty in complaints, so there is no key. What the shared customers and agents show:

| Check | Result |
|---|---|
| Survey customers who also complain | 41,059 (36%, as in the base) |
| Survey agents that are also complaint agents | 1,090 of 1,090 |
| Same agent handled a complaint and a survey within 30 days after it | 0.12% (chance: 0.08%) |
| CSAT, customers with vs without complaints | 2.76 vs 2.77 |
| CSAT, customers with vs without a compensation (31,106 customers) | 2.77 vs 2.76 |
| Customer level: mean resolution days vs mean CSAT (8,408 customers) | rho -0.02 |
| Agent level: mean resolution days vs mean CSAT (1,084 agents) | rho -0.01 |

With this sample, **sample size was not the reason** satisfaction looked unrelated to time and compensation in the
complaint ratings. The one thing not testable is the individual interaction, because the datasets are not linked at that level.

### 5e. Baseline and pilot sensitivity

~5,900 surveys per month; mean CSAT 2.77; 31% score 1-2 and 11% score 4; 30% carry a negative comment. Smallest CSAT
difference a pilot could detect (80% power, 95% confidence, CSAT sd 0.69): **0.19** with 200 surveys per group, 0.12 with 500,
0.09 with 1,000, **0.04 with 5,000**, 0.02 with 20,000.

---

## 6. Data quality register

| Issue | Evidence | Impact |
|---|---|---|
| No free text | 5 distinct descriptions, 5 distinct resolution sentences | An agent's understanding or writing cannot be evaluated |
| `origin_interaction_id` empty | 100% missing | Cannot link complaints to the interaction that caused them |
| Terminal share independent of age | ~25% at every age band | Backlog may not be real |
| `sla_breached` unrelated to times | ~20% for every priority, resolution time and status | Cannot measure SLA performance |
| Uniform stage durations | assignment 1-24 h, first response 3-72 h, resolution 1-30 d | Looks generated, not measured |
| Affected product never belongs to the complainant | 0% ownership match (44,570 complaints name a product) | Complaints not connected to the customer's products |
| Complaints before the product opened | 18.7% | Chronology inconsistent |
| Category unrelated to product type | Same product-type mix for every category | Category cannot be validated |
| `is_repeat_complainer` does not match behaviour | Flagged and unflagged customers have the same mean complaints (1.44 vs 1.45) | Flag unusable |
| Dates after the snapshot | resolution 211, first response 70, closing 46, assignment 31 | Future events |
| Resolved before first response | 492 | Inconsistent order |
| Resolution days without a resolution date | 737 | Incomplete rows |
| No currency on compensation | column absent | Compensation cannot be converted |
| Partition / `process_date` follow a business day | 08:00 cut-over here (06:00 in transactions), all but 1 row | Convention, not a defect |
| surveys | Scales differ by type; NPS scale is 2-7 | No Promoter possible; implied NPS -74.5 | NPS unusable |
| surveys | Follow-up questions uniform 1-5 and independent of the main score | ~0 rank correlation | Questions carry no information |
| surveys | Only 13 distinct comments; sentiment set by score band | 5,079 rows with sentiment but no comment; 5,018 comments without sentiment | Text is not real feedback |
| surveys | Comment themes inconsistent with structured answers | "waited too long" rates wait question 3.0 = same as "excellent attention" | Comments unreliable as evidence |
| surveys | `survey_date` is 0-2 days after `process_date` | `survey_date` = send time + `response_time_hours` for 86% of rows | `process_date` is the send day; responses run past the last partition |
| surveys | No link to complaints | `origin_interaction_id` empty; same-agent match within 30 days 0.12% (chance 0.08%) | Interaction-level analysis impossible |

---

## 7. Assumptions and caveats

- **Descriptive only:** no model. Differences are judged against 95% intervals.
- **"Today"** is the latest `creation_date` (2026-06-18 07:56); the file has no snapshot date.
- **Backlog** = `Open` + `In Process` + `Escalated`; `Rejected` is treated as terminal.
- **Compensation units** are raw, with no FX applied, because its currency is unknown.
- **Retention proxy** uses `customers.csv` status at an unknown date, so it is cross-sectional only.

---

## 8. Next steps

1. **Validate the backlog** with the system owners (if real, that alone is the opportunity).
2. **Instrument the process** for 1-2 months: status-history events (time in state, re-openings), agent effort/touches, and satisfaction for *all* resolved cases.
3. **Obtain** real complaint text and resolution notes, the linked interactions, compensation currency and policy, and customer outcomes after resolution (retention, later complaints).
4. **Pilot** an agent-assisted triage / first-response step on new complaints against a control group, measuring time to first response, time to resolution and satisfaction (CSAT differences of ~0.04 are detectable with 5,000 surveys per group).
5. **Fix the survey linkage**: a survey-to-interaction-to-complaint key (`origin_interaction_id` or a `complaint_id` on surveys), the survey denominator (interactions surveyed vs answered), a valid 0-10 NPS scale and real comments.

### Checklist for each new dataset

- [ ] Does it add a way to measure effort or cost per case?
- [ ] Does it add complaint text or interaction content?
- [ ] Does it join on `customer_id` / `complaint_id` / `origin_interaction_id`, and how much is lost?
- [ ] Does it show a relationship between speed, compensation and satisfaction, or is it flat again?

---

## 9. Reproduce

| Notebook | What it contains |
|---|---|
| [satisfaction_surveys.ipynb](satisfaction_surveys.ipynb) | Survey structure and scales, NPS and sentiment checks, timestamps, score drivers (channel, quarter, agent, customer), comment themes, link to complaints (customer, agent, time window, customer- and agent-level), baseline and pilot sensitivity, conclusions |
| [complaints.ipynb](complaints.ipynb) | Load (memory measured), structure and consistency checks, volume and mix, backlog and speed, compensation, satisfaction, agents and repeat complainers, joins with customers and products, baseline table, conclusions |

Data lives in `data/complaints/` and `data/satisfaction_surveys/` at the repo root (git-ignored). Both are small (17 MB and 44 MB), so they are loaded whole (~230 MB and ~260 MB of process memory).
Charts in `figures/` are exported from the executed notebook; re-export them if it changes.
