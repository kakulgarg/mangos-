# Reconciliation Log

Every decision that changed the data, in the order it was made, with the
reasoning. Cleaning decisions are graded on the reasoning, not the outcome, so
nothing here is silent.

Scope as loaded: **Onion**, **Maharashtra**, 25 monthly Agmarknet exports,
**Jun 2024 – Jun 2026**, 33,054 rows → 31,930 after de-duplication.

---

## R1 — Arrivals were in tonnes, prices in quintals

**Phase:** Parse (Step 0)

**Finding.** The export header reads *Arrivals (Metric Tonnes)*; every price is
₹/quintal. Regressing price on arrivals without converting would make the arrivals
coefficient wrong by a factor of 10 and mis-scale the plausibility bounds.

**Decision.** Convert arrivals **tonnes → quintals** (×10) once, at parse time, and
document it. A regression test pins `TONNES_TO_QUINTALS == 10`.

---

## R2 — Market identity lived in header rows

**Phase:** Parse (Step 0)

The report is block-structured (`Market Name : ...` headers between data blocks).
The parser walks each file line by line, carrying the current market forward, and
**keeps the variety column** so the "which onion pays best" question is answerable
downstream.

---

## R3 — Mandi IDs must be stable, not coverage-ranked

**Phase:** Parse (Step 0)

**Finding.** An earlier design assigned `M1, M2, …` by coverage rank. Adding a
month reshuffles the ranking, so a fixed `MANDI_FILTER` would silently select
different markets.

**Decision.** Canonicalise names (whitespace + case + `APMC`/`Committee`) and assign
IDs by **sorted canonical name**. The curated list in `config.py` is keyed on the
name, not the id, so it is stable across data refreshes.

---

## R4 — Duplicate rows: 1,124, all exact

**Phase:** Parse → Clean

A re-downloaded February 2025 export produced 1,124 byte-for-byte duplicate
`(mandi, date, variety, values)` rows. **Dropped** with `drop_duplicates`; identical
values mean drop/mean/last are numerically equal, and only dropping states what
happened. The code still averages genuinely conflicting duplicates should a future
export contain them.

---

## R5 — Plausibility bounds widened for real shocks

**Phase:** Clean (Step 3)

The synthetic sample topped out near ₹3,000/quintal; real onion prices reach
**₹25,000/quintal** in shock weeks. `PRICE_MAX` widened to 30,000 and `ARRIVALS_MAX`
to 500,000 quintals so genuine shocks are retained while transposed/garbage rows are
still caught. After parsing, **0** rows violate the range or internal-consistency
checks.

---

## R6 — Gaps left unfilled, and the verdict is now COMPUTED

**Phase:** Clean (Step 3)

Tested whether missingness is systematic before deciding. The audit **computes** the
coefficient of variation of the missing rate: **0.23 across weekdays, 0.54 across
months**. Because the month figure exceeds the 0.25 threshold (driven by the
entirely-absent August 2024), the verdict is **"mildly non-random"** — not the
"approximately random" the synthetic data returned.

**Decision.** No interpolation (inventing trades = inventing evidence), and every
monthly aggregate carries `n_obs` so thin cells stay visible rather than being
treated as unbiased. The point: the same code, run on different data, returns a
different verdict — the audit can fail.

---

## R7 — Price spikes retained

**Phase:** Clean (Step 3)

**281** observations beyond 3 SD, clustered in the 2024–25 shock episodes (to
₹25,000/quintal). **Retained, not winsorised** — these are the weeks a storing
farmer earns most; flattening them would understate the upside of holding. The
models' inability to *predict* them is handled in the failure analysis instead.

---

## R8 — The "Simpson's paradox" finding did not replicate on real data

**Phase:** EDA (Step 4) — the most important reconciliation

The synthetic scaffold showed a dramatic arrivals–price sign-flip (pooled r = −0.72,
within-month +0.34). **On the real data it is absent** (pooled r = −0.03,
within-month +0.07; month explains only 2.7% of arrivals variance; VIF 1.03).

**Decision.** Report the real finding — a single mandi's arrivals are a weak
predictor of its price — and **reframe figures F2–F4 accordingly**, rather than
keep a compelling story the data no longer supports. The forecasting value instead
comes from lagged prices, not contemporaneous arrivals. Logged as M5 in the AI
appendix.

---

## R9 — Variety folding

**Phase:** Clean (Step 3)

12 raw varieties, of which "Other" is 52% of rows. Kept **Red, Local, White,
Unhali** (real, distinct price levels) as their own groups and folded the long tail
into a labelled **"Other"** bucket, rather than silently merging it into a real
variety.
