# Data Quality Note

**Dataset:** Onion, Maharashtra, 25 monthly Agmarknet exports.
**Grain:** mandi × date × variety. **Rows as sourced:** 33,054 → **31,930** after
dropping exact duplicates (96.6% retained). **Curated for recommendations:** 14
high-coverage markets (of 111 loaded).

What was wrong with the data, what was done about it, and what remains imperfect —
written so a reader can decide how far to trust the recommendation without reading
any code. Every verdict below is **computed** from a statistic in
`outputs/cleaning_audit.json`, not asserted.

---

## 1. What was wrong

### 1.1 Market names appear as header rows, not a column

The Agmarknet "Date Wise Prices" export is block-structured: each market's name is
a `Market Name : ...` header line, followed by its rows. A naive CSV read loses the
market identity entirely. The parser walks each file line by line, carrying the
current market forward (`src/parse_agmarknet.py`).

### 1.2 Arrivals are in tonnes; everything else is per quintal

The source header reads *Arrivals (Metric Tonnes)*, but prices are ₹/quintal.
Left unconverted, any arrivals coefficient would be **wrong by 10×**. Arrivals are
converted **tonnes → quintals** (×10) once, at parse time.

### 1.3 Duplicate rows — 1,124, all exact

25 exports include a re-downloaded February 2025 file. 1,124 `(mandi, date,
variety, values)` rows are **byte-for-byte identical** re-transmissions, dropped
with `drop_duplicates`. No conflicting duplicates exist; the code still averages
genuine conflicts should a future export contain them.

### 1.4 Inconsistent market spellings

Real names vary in case and whitespace across months (`Pune APMC` vs `Pune  APMC`).
Names are canonicalised (whitespace collapsed, title-cased, `APMC`/`Committee`
normalised) and IDs are assigned by **sorted canonical name** — stable when new
months are added, unlike a coverage-rank id.

### 1.5 Reporting gaps — and they are mildly non-random

Across the curated markets the mandi × day grid is **76.3%** populated; the longest
single gap is **34 days** and August 2024 is **absent from the source entirely**.
The missingness verdict is **computed**: the coefficient of variation of the
missing rate is 0.23 across weekdays and **0.54 across months** — above the 0.25
threshold, so the audit records missingness as **mildly non-random** (the Aug-2024
hole drives this). Consequence: monthly aggregates carry `n_obs` so thin cells stay
visible, and they are not treated as perfectly unbiased.

### 1.6 Price spikes — 281 observations beyond 3 SD

Concentrated in the 2024–25 shock episodes, reaching **₹25,000/quintal** against a
p99 of ₹5,000. **Retained, not winsorised** — the spikes are the signal a storing
farmer cares about, and the models' inability to predict them is reported honestly
rather than hidden by trimming.

---

## 2. What was done, and why

| # | Issue | Decision | Reasoning |
|---|---|---|---|
| Parse | arrivals unit | **tonnes → quintals** | prices are per-quintal; else 10× error |
| C1 | 1,124 exact dup rows | **drop exact** | re-downloaded month; identical values |
| C2 | impossible values | range + internal-consistency checks | 0 violations after parse |
| C3 | unit consistency | cross-market median ratio | verdict computed; no whole-market mismatch |
| C4 | 24% gaps (curated) | **leave — no interpolation** | inventing trades = inventing evidence; missingness carried with `n_obs` |
| C5 | 281 spikes | **retain — no winsorising** | the spikes are the signal, not noise |

The duplicate, gap, unit, and outlier verdicts are all emitted by the code from
the data, so an audit line can actually **fail** — e.g. C4 now reports *non-random*
on the real data, where the earlier synthetic run reported *random*.

---

## 3. What remains imperfect

Stated plainly, because the recommendation should be read against these.

1. **24 months, each calendar month observed ~2 times, and August 2024 missing.**
   The seasonal peak rests on few observations. *The single largest limitation.*
2. **Missingness is mildly non-random** (§1.5). Monthly means are carried with
   observation counts rather than treated as perfectly unbiased.
3. **The 2024–25 shocks are retained but unexplained.** The data records the spike;
   it contains nothing about *why*, so no model can anticipate a recurrence.
4. **Only modal price is analysed** for the headline; min/max feed a dispersion
   check but are otherwise unused. A high-grade lot realises closer to the max.
5. **Arrivals units assumed consistent within a market** — the cross-market test
   catches a whole market in the wrong unit, not a mid-series switch.
6. **No weather, MSP, or export data** — the dominant drivers of onion price shocks
   in India, and the reason the forecaster cannot see the weeks that matter most.
7. **"Other" is 52% of variety rows.** Per-variety findings are cleanest for Red,
   Local, White, and Unhali; "Other" is kept as its own labelled bucket, not merged
   into a real variety.
