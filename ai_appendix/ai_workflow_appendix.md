# AI Workflow Appendix

AI (Claude) was used throughout as a pair programmer and reviewer. This
appendix records what it contributed, where it was confidently wrong, and how
the verification bar was set.

> **Note on the two phases.** The pipeline was first developed on the scaffold's
> **synthetic sample data**, then rebuilt on the **real 25-month Agmarknet
> dataset**. Entries M1–M4 below describe the synthetic-phase process and quote
> figures from that data; **M5 records what changed when the real data replaced
> it** — including a headline finding that did not survive. Every number in the
> rest of the repository is from the real data.

---

## Prompt log

| # | Phase | Prompt (summary) | What the AI produced | Used as-is / edited / rejected |
|---|---|---|---|---|
| 1 | Setup | Read the capstone scaffold, analyse the guidelines for Project 5, propose a build order | Correct reading of the 7 deliverables and the Solid/Strong/Standout gaps; flagged that sample data does not satisfy the data requirement | Used as-is |
| 2 | SQL | Build a loader that handles both the sample schema and raw Agmarknet column names | Column-alias mapping incl. the real `Modal_x0020_Price` and `Model Price` typo | Used as-is |
| 3 | SQL | Write the six analytical queries, parameterised so an 11th mandi needs no rewrite | `scope`/`base` CTE pattern; all six queries | Edited — `LAG()` nested inside `MAX()` failed (see M2) |
| 4 | Clean | Handle 62 duplicate reporting days | Suggested averaging them | **Rejected** — see M1 |
| 5 | Clean | Decide whether to interpolate the 15.8% missing mandi-days | Recommended leaving gaps; proposed testing missingness by weekday and month first | Used, after running the test |
| 6 | EDA | Explore the arrivals-price relationship | Found the pooled correlation, then flagged that it reverses within month | Used — this became the project's central finding |
| 7 | Model | Set up train/test split | Chronological split, with an explicit warning against `shuffle=True` | Used as-is |
| 8 | Model | Evaluate the model | Reported test error 47.6% *below* train error and flagged it as a warning rather than a win | Used — led to adding blocked CV |
| 9 | Dashboard | Build Power BI extracts and a build guide | Five denormalised CSVs, DAX-free; guide incl. the month-sort trap | Edited — recommendation labels rewritten (see M3) |
| 10 | Memo | Draft the one-page decision memo | Draft with findings, uncertainty, limitations | Edited for length and to add the storage qualifier |

---

## What the AI contributed

AI wrote most of the boilerplate — the loader's column-alias mapping, the CTE
scaffolding for the SQL, matplotlib formatting, the Power BI guide structure.
That is a genuine time saving on work that is tedious rather than difficult.

Its more valuable contribution was **catching two of its own errors by
running the code**. The date-parsing bug (M1) and the misleading test score
(M2) were both surfaced by execution and diagnostics, not by reading. That is
the actual argument for AI-assisted analysis: not that the first draft is
right, but that the loop from hypothesis to falsification is much shorter.

Where it was weakest was **defaults that are correct in general and wrong
here** — averaging duplicates, trimming outliers, splitting randomly. Each is
standard practice. Each would have been wrong for this specific question.

---

## One moment it was confidently wrong

### M1 — Date parsing that silently moved a third of the calendar

**What happened.** The loader was written with `dayfirst=True`, on the
reasonable ground that Agmarknet publishes DD/MM/YYYY. The file in hand is
ISO (YYYY-MM-DD). Under day-first parsing, `2026-01-08` is read as **1 August
2026** instead of 8 January.

Nothing about this fails loudly. Every row parses. No exception, no null, no
change in row count. Only dates with a day-of-month of 12 or lower are
ambiguous, so roughly a third of the calendar gets relabelled into the wrong
month while the rest stays correct.

**Why it was the worst possible bug for this project.** The entire
deliverable is a claim about *which months pay more*. A partially scrambled
calendar produces a confident, fully-evidenced, wrong selling window — and
every downstream check still passes.

**How I caught it.** A scope filter for `2024-01-01 .. 2026-06-30` dropped
243 rows. The source file's own span is exactly that range, so a correct
parse should have dropped none. Inspecting the dropped rows showed parsed
dates running into December 2026 — dates that do not exist in the file.

The tell was not the code. It was **a number that had no business being
non-zero.**

**What I did instead.** Replaced the assumption with detection: match the ISO
pattern explicitly and parse accordingly, falling back to day-first only for
slash/dot formats where ambiguity is real. Logged as R1 in the reconciliation
log.

**Wider lesson.** AI will confidently supply a plausible convention for a
data source it has seen described. It cannot check that convention against
the file in front of it unless asked. Any AI-written parsing step needs a
sanity check whose expected value is known in advance.

---

## Other corrections worth recording

### M2 — A test score that looked excellent and was not

The first evaluation returned **MAPE 4.8%, with test error 47.6% *lower* than
training error**. It would have been easy to report that as a strong result.

Test error below training error is a warning, not a win. The final 20% of the
timeline is December 2025 – June 2026: the low-price half of the year, with
no August, no October, and neither shock episode. Test price SD was ₹275
against ₹431 in training. The model had been scored on the easy half.

The method was right — chronological splitting is correct here and I would
defend it. But **a correct method landing on an unrepresentative window still
produces a false claim.** Adding blocked time-series cross-validation gave
the honest figure: **7.7% average, 19.8% on the shock fold**, roughly 7×
worse. Quoting 4.8% would have overstated the model by about 40% and
concealed its only serious weakness.

### M3 — Advice that was not actionable

The dashboard's first recommendation layer labelled the cheap months
**"AVOID"**. That is not advice a farmer can act on: onions harvested in
February must be sold or stored, and the month cannot be skipped. Relabelled
to describe available actions — *SELL NOW / GOOD TO SELL / HOLD IF YOU CAN /
STORE OR SELL LOCAL*.

A small wording change, but it is the difference between a dashboard that
judges the farmer's situation and one that tells them what to do about it.

### M4 — SQL that read correctly and did not run

`MAX(JULIANDAY(...) - JULIANDAY(LAG(...) OVER (...)))` in Q6. SQLite rejects
a window function nested inside an aggregate. It reads as valid SQL and only
fails on execution — which is precisely why every query was run rather than
reviewed.

---

## Judgment note: where I trusted AI, and where I did not

The bar moved with the **cost of being wrong**, and a farmer's income sits
downstream of every number here.

**Trusted directly:** boilerplate with immediate feedback — matplotlib
formatting, CTE scaffolding, file I/O, the Power BI guide's UI steps. Wrong
output is obvious and cheap.

**Verified before accepting:** anything that changed a number a farmer would
act on.

- Every SQL query was **executed** and its row counts reconciled, not read.
- The extensibility claim in Q6 was **tested** by injecting a 3-mandi filter
  and re-running all six queries, rather than asserted in a comment.
- Every cleaning rule was **checked against the data before adopting it.**
  This is what caught M1: inspecting the duplicates showed all 62 pairs were
  byte-identical, which made averaging the wrong rule. AI's suggestion was
  standard practice and standard practice was wrong here.
- The model's headline metric was **stress-tested** by asking whether the
  test period was representative. It was not.

**Where I set the bar deliberately higher than usual.** Three AI suggestions
were each individually reasonable and each wrong for this problem:

1. Average the duplicate reporting days *(they were exact copies — averaging
   would have inflated the observation counts the memo's credibility rests
   on)*
2. Winsorise the outliers *(measured: it would have pulled August's seasonal
   index from 143.8 to 138.1, understating the peak and underselling the
   value of holding)*
3. Report the single-split test score *(it was 40% too optimistic)*

The pattern is consistent. **AI defaults are correct on average and wrong at
the margins — and the margins are where the decision lives.** Every one of
these would have produced a cleaner-looking, more confident, worse analysis.

The one thing I would not delegate at any confidence level is **deciding what
question the data can honestly answer.** Deciding that the recommendation should
lead with timing rather than supply — and, later, that a finding built on
synthetic data had to be discarded when the real data contradicted it (M5) — was
a judgement about what could responsibly be told to a farmer, not a statistical
result.

---

## M5 — A "central finding" that did not survive the real data

**The most important correction in the project, found *after* the first appendix
was written.**

The pipeline was first built and tuned on the scaffold's **synthetic** sample. On
that data the headline insight was a textbook **Simpson's paradox**: the
arrivals–price correlation flipped sign once season was controlled for (pooled
r = −0.72, within-month +0.34), and the whole feature specification was built
around decomposing arrivals to fix a VIF of 5.7.

When the **real** 25-month Agmarknet dataset (33,054 rows, 111 markets) replaced
the sample, **the finding evaporated**: pooled r = −0.03, within-month +0.07,
month explains 2.7% of arrivals variance, VIF 1.03. There was no paradox and no
collinearity — a single mandi's own arrivals simply carry almost no signal for its
price, because the price is set by state/national supply and the reference market.

**What I did.** Rather than keep a compelling narrative the data no longer
supported, I reframed EDA figures F2–F4 to the honest real-data reading, rebuilt
the recommendation around **timing, market, and variety** (which the real data
*does* support strongly), and pivoted the predictive work to a **lag-based monthly
forecaster**, where the real signal (0.86 monthly autocorrelation) actually lives.

**Wider lesson.** A model built on placeholder data will confidently produce
placeholder findings. The pipeline, the reasoning, and the code transferred to real
data unchanged — but the *specific numbers and the central story did not*, and
checking that was the difference between an honest submission and a polished wrong
one. Every headline number in this repository is now regenerated from the real
exports by `run_pipeline.py`.

---

## M6 — LightGBM lost to a naive baseline, and I reported it

The forecaster was expected to be the showpiece. In walk-forward backtesting,
LightGBM (MAPE 16.8%) **lost to naive persistence** (14.1%) — monthly onion prices
are close to a random walk, and trees cannot extrapolate to shock-driven levels.

Two honest responses instead of hiding it: (1) model the month-over-month *change*
so the trees can reach new levels, and (2) blend with persistence. The hybrid
ensemble then **edges** the baseline (₹168 vs ₹169) and adds a calibrated
prediction interval the baseline cannot give. The mature result — "ML ties a strong
baseline but is more informative" — is stated plainly rather than dressed up as a
win.
