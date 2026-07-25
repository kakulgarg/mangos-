# Repository Review — DeHaat Mandi Price Watch

**Reviewer:** Senior ML Engineer / Architect review
**Date:** 22 July 2026
**Scope:** Full repository read. No code modified. Pipeline re-executed in an isolated copy to verify reproducibility claims.
**Verdict headline:** Excellent *reasoning artefact*, currently a **broken pipeline** — the committed results and the committed data are from two different datasets.

---

## 0. Executive summary — read this first

This project has, by some distance, the best **analytical writing** I have seen in a capstone of this size. The reconciliation log, the model card, the feature spec, and the Simpson's-paradox narrative are genuinely at industry standard. The documented judgement (overriding `DUPLICATE_RULE`, refusing to winsorise spikes, catching that test-error-below-train-error is a warning not a win, adding blocked CV) is exactly what distinguishes a "Standout" from a "Solid".

But there is one issue that outweighs everything else:

> **The pipeline no longer reproduces its own results.** Every headline number in the README, memo, model card and dashboard was generated from the scaffold's **synthetic sample data** (8 fictional mandis: Nashik, Pune, Nagpur, Solapur, Kolhapur, Ahmednagar, Aurangabad, Latur; 6,142 rows; Jan 2024–Jun 2026). The `data/raw/` folder now contains **real Agmarknet data for June 2026 only** — 1,592 rows, 93 markets. Running the documented reproduce commands today produces **190 rows, one month, 7 different mandis**, and every claim in the repository collapses.

I verified this by copying the repo and running it:

```
load_db.py   -> daily_prices: 190 rows, 2026-06-01..2026-06-30, 7 mandis
clean.py     -> daily_prices_clean: 190 rows (overwrites the 6,142-row table)
build_extracts.py -> market_summary.csv: 0 ROWS (silent bug, see §6.2)
              -> "SELL months flagged: []"  "Best month: ['Jun']"
parse_agmarknet.py -> "No Agmarknet exports found in data/raw" (orphaned, see §6.1)
```

A professor who runs `python load_db.py && python clean.py` — and at IIT Mandi someone will — sees the entire project evaporate in fifteen seconds. Everything else in this review is secondary to fixing that.

The good news: this is a **data-acquisition and wiring problem, not an analysis problem**. The reasoning, the code structure, and the documentation all transfer. Roughly 6–10 hours of focused work converts this from "will be caught out" to "top of the batch".

---

## 1. Overall understanding of the project

**Business question.** DeHaat's advisory team supports FPOs whose onion farmers ask two questions each season: *when* should we sell, and *in which mandi*? The project turns public Agmarknet price data into a defensible selling-window recommendation a field agent can carry to a farmer.

**Analytical answer as currently written.** Timing dominates location. Selling in August rather than February is worth ~₹1,118/quintal; the best-vs-worst market spread is ~₹289/quintal (gross of transport). Therefore: plan around an August sale, treat Jul–Oct as the acceptable window, and only travel to Pune/Nashik if transport costs less than the premium — and only advise this at all if the farmer has storage.

**The intellectual centrepiece** is a Simpson's-paradox finding: pooled across the year, arrivals and price are strongly negatively correlated (r = −0.719, "textbook supply and demand"); within any single month they move *together* (mean r = +0.337). Month alone explains 77.7% of arrivals variance, so raw `arrivals` is largely a restatement of the calendar. The fix — decompose arrivals into its month-mean (redundant) and its deviation (`arrivals_dev`, genuinely new) — drops VIF from 5.70 to 1.27 and makes the coefficient stable and quotable. This is a real, well-told, well-evidenced insight and it is the single strongest thing in the project.

**Deliverables present:** SQLite schema + 6 analytical SQL queries, a 7-script Python pipeline, 9 figures, cleaning audit JSON, model artefacts, 5 Power BI extracts + a 264-line build guide, a 2-page decision memo (MD + PDF), an AI workflow appendix with 4 documented AI errors, a reconciliation log, a data-quality note, a feature spec, a model card, a walkthrough script, and a submission checklist.

**Deliverables missing:** the real dataset, the built dashboard, the recorded walkthrough, and any version control.

---

## 2. How the project works

### 2.1 Intended architecture

```
Agmarknet monthly CSV exports
        │
        ▼  parse_agmarknet.py      (block-structured CSV → flat table;
        │                           variety aggregation weighted by arrivals;
        │                           mandi_id assigned by coverage rank)
        ▼  data/raw/daily_prices.csv + mandis.csv
        │
        ▼  load_db.py              (column-alias normalisation, format-detecting
        │                           date parser, scope filters from config,
        │                           3 sanity checks) → SQLite: mandis, daily_prices
        │                                              ("as sourced", nothing cleaned)
        ├──► run_sql.py            (splits sql/analysis.sql on `-- Qn.` markers,
        │                           runs 6 queries → outputs/q1..q6 CSVs)
        │
        ▼  clean.py                (C1 duplicates → C2 impossible → C3 units →
        │                           C4 gaps → C5 outliers → derived features)
        │                          → daily_prices_clean + cleaning_audit.json
        │
        ├──► eda.py                (6 figures, each with one printed claim
        │                           → eda_findings.md)
        │
        ├──► model.py              (OLS: modal_price ~ arrivals_dev + C(m) +
        │                           C(mandi_id); chronological split; VIF;
        │                           blocked expanding-window CV; failure analysis;
        │                           3 figures) → model_results.json, coefficients
        │
        └──► build_extracts.py     (5 denormalised CSVs → dashboard/data/)
                                   → Power BI (not yet built)
             make_memo_pdf.py      (reportlab → memo/decision_memo.pdf)
```

**Configuration-driven design.** `src/config.py` holds every scope decision — commodity, state, mandi list, date range, price field, rolling window, test fraction, cleaning rules, plausibility bounds. The stated contract is that adding an 11th mandi or a second commodity is a change to that file alone. That contract is **honoured in the Python** and **broken in the SQL** (§6.6).

### 2.2 Data flow, layer by layer

| Layer | Store | Grain | Mutability |
|---|---|---|---|
| Source | `data/agmarknet_source/*.csv` | market × date × variety | immutable |
| Raw flat | `data/raw/daily_prices.csv` | market × date | regenerated by parse |
| As-sourced | SQLite `daily_prices` | mandi × date | dropped/recreated per load |
| Clean | SQLite `daily_prices_clean` + CSV | mandi × date + 10 derived cols | replaced per clean run |
| Serving | `outputs/`, `dashboard/data/` | varies | replaced per run |

The **as-sourced / cleaned separation** is a genuinely good architectural decision and is worth calling out explicitly in the presentation: the database holds the data exactly as it arrived, every judgement call happens in one auditable step, and each is logged to `cleaning_audit.json` with before/after counts. That is how a real data team works.

### 2.3 ML pipeline

- **Target:** `modal_price` (₹/quintal), justified over min/max and over `avg(min,max)`.
- **Features:** `C(month)` 12 levels, `C(mandi_id)` 8 levels, `arrivals_dev` continuous.
- **Model:** single OLS via `statsmodels.formula.api` (brief specifies one model).
- **Split:** chronological at the 80th percentile of dates. `arrivals_dev`'s month-means are computed on **train only** and mapped onto test — correct leakage handling, and rare to see done properly at this level.
- **Evaluation:** single split (MAE ₹54, MAPE 4.8%) explicitly labelled *misleading*, plus 5-fold blocked expanding-window CV (MAE ₹117, MAPE 7.7%, worst fold 19.8%) presented as the honest figure.
- **Diagnostics:** VIF, month/market error decomposition, bias on top-5% vs bottom-50% of prices, residual-vs-actual shrinkage plot.

---

## 3. Current implementation quality

### Rating: **6.0 / 10 as it stands** — but **8.5 / 10 for the thinking**, and **9+ / 10 reachable** with the fixes in §15.

The gap between those two numbers is the whole story of this review.

| Dimension | Score | Comment |
|---|---|---|
| Business framing | **9/10** | Clear question, quantified answer, actionable qualifier (storage), transport caveat. Better than most industry memos. |
| Analytical reasoning | **9/10** | Simpson's paradox finding is genuine and correctly diagnosed. Feature spec written before fitting. |
| Documentation quality | **9/10** | Reconciliation log, model card, data-quality note are exemplary. |
| Intellectual honesty | **8/10** | Excellent within each document; undermined by README/memo claiming "Agmarknet" for synthetic numbers (§5.1). |
| Code structure | **7/10** | Clean modular scripts, sensible separation, heavy explanatory docstrings. Not a package; no tests; `print` instead of `logging`. |
| **Reproducibility** | **2/10** | **Pipeline does not reproduce its own outputs. This is the critical defect.** |
| Data foundation | **3/10** | One month of real data vs a 2.5-year claim. |
| SQL craft | **8/10** | Window functions, CTEs, `ROWS` vs `RANGE` justified, per-mandi-first averaging in Q2. Scope duplicated across 6 queries. |
| Testing / CI | **0/10** | No tests, no CI, no assertions, no schema validation. |
| Version control | **0/10** | **There is no `.git` directory.** No history, no commits, no branches. |
| ML methodology | **6/10** | Correct split and leakage handling; but single OLS with no baseline comparison, no prediction intervals, no residual autocorrelation check. |
| Dashboard | **4/10** | Extracts + a strong build guide exist; the dashboard itself does not. |

---

## 4. Missing features

### 4.1 Blocking (submission fails or is heavily marked down without these)

1. **Real multi-year Agmarknet data.** The scaffold states explicitly that sample data does not satisfy the data requirement, and your own `SUBMISSION_CHECKLIST.md` lists this as outstanding. You need ~30 monthly exports (Jan 2024 – Jun 2026) to support every claim currently in the repo.
2. **Version control.** No git repository exists. A GitHub repo is an explicit deliverable, and commit history is itself evidence of process.
3. **The Power BI dashboard.** Guide and extracts are ready; the artefact is not.
4. **The recorded walkthrough.** Script is ready; the recording is not.
5. **A single reproducible entrypoint** (`make all` / `run_pipeline.py`) that runs the 7 steps in order and fails loudly on any inconsistency.

### 4.2 High-value additions

6. **Automated data-contract validation** — Pandera or Great Expectations schema on the raw and clean frames (dtypes, ranges, key uniqueness, non-null). This converts your prose data-quality claims into executable, re-runnable checks. Very few capstones do this; it reads as production engineering.
7. **A unit test suite** — at minimum: date-parser (the M1 bug — write the regression test that would have caught it), Agmarknet block-parser on a fixture, variety aggregation weights, `arrivals_dev` computed train-only, duplicate resolution branches.
8. **Baseline model comparison** (§9.1).
9. **Prediction intervals**, not point estimates, on the recommendation layer.
10. **Mandi name canonicalisation** (`SHRI.SIDDHESHWAR  APMC`, `AGRICULTURE PRODUCE MARKET COMITEE CHANDWAD` — real Agmarknet names are uppercase, double-spaced and misspelled; the same market can appear under variant names across months and will silently split into two markets).
11. **A `data/README.md`** documenting provenance, download procedure, and the Agmarknet query parameters used — so the dataset is reconstructible by a third party.
12. **`LICENSE`** and **`CITATION.cff`**.

---

## 5. Code quality issues

### 5.1 Correctness / honesty (fix first)

**Q1 — Stale committed state (CRITICAL).**
`daily_prices` (190 rows, real, June 2026) and `daily_prices_clean` (6,142 rows, synthetic, 2024–2026) coexist in `mandi.db` describing **different worlds**. `data/processed/daily_prices_clean.csv` shows `M1 = Nashik`; `data/raw/mandis.csv` says `M1 = Pune(Manjri) APMC`. Two datasets, one repository, no marker distinguishing them.

**Q2 — README and memo overclaim provenance.**
`README.md` states *Source: Agmarknet (Government of India)*, *6,204 sourced → 6,142 analysed*. The memo footer says *"6,142 daily price records … Agmarknet"*. Those numbers are from synthetic data. Only `notebooks/data_quality_note.md` §3.7 admits this — buried at the bottom of the seventh document. If a professor finds the disclosure *after* reading the confident README, the honesty framing that is this project's greatest strength inverts into its greatest liability. **Either regenerate on real data, or put the disclosure in the first paragraph of the README.**

**Q3 — Arrivals unit mismatch will corrupt the headline coefficient.**
The Agmarknet header reads `Arrivals (Metric Tonnes)`. The model card, memo, README and SQL comments all interpret the coefficient in **quintals** ("₹21/quintal per 1,000 extra quintals"; SQL labels `avg_daily_arrivals` as `qtl/day`). 1 tonne = 10 quintals, so on real data the plain-language reading is **wrong by a factor of 10**. `config.ARRIVALS_MAX = 200000` is likewise calibrated for the synthetic scale. Add an explicit unit constant and a conversion step in `parse_agmarknet.py`.

**Q4 — Hardcoded model metrics in the serving layer.**
`build_extracts.e4_recommendation` hardcodes `model_mape_normal_pct = 7.7` and `model_mape_shock_pct = 19.8`, and derives `price_range_low/high` from the literal `0.077`. After a re-run on real data these become silent lies printed on a dashboard a field agent reads. Read them from `outputs/model_results.json`.

**Q5 — A computed-looking verdict that is a constant.**
`clean.assess_gaps` computes `by_dow` and `by_month` missing rates, then logs `missingness_verdict="approximately random; monthly means unbiased"` **unconditionally**. On the real June-2026 data the by-weekday missing rate ranges 0.000–0.571 — clearly *not* random — and the audit still asserts randomness. The same pattern appears in `check_units` (suspects are computed and reported, but no threshold decision is encoded). An audit line that cannot fail is not an audit line. Make the verdict a function of the statistic, with a documented threshold.

**Q6 — No guard against NaN predictions in the main evaluation path.**
`blocked_cv` correctly filters `pr.notna()`. `fit_and_evaluate` does not. If the test period contains a mandi or month level absent from train, `model.predict` returns NaN and every metric silently becomes NaN. Add an explicit unseen-level check that raises.

### 5.2 Structure / standards (your project instructions ask for these)

- **`print` everywhere instead of `logging`.** All seven scripts. Your own coding standard says logging. A `src/logging_config.py` with a single `get_logger()` and `%(asctime)s %(name)s %(levelname)s` format is a 30-minute change that visibly raises the professionalism of every console transcript in your demo.
- **Not a package.** `import config as C` only resolves because you `cd src` first. Move to `src/mandi_watch/` with `__init__.py`, use `from mandi_watch import config`, install with `pip install -e .`. Removes the fragile cwd dependency.
- **No type hints** in `clean.py`, `model.py`, `eda.py`, `build_extracts.py`, `load_db.py` (only `parse_agmarknet.py` has partial hints). Standard asks for them.
- **No exception handling** on file I/O, SQLite connections, or missing columns. `sqlite3.connect` is never wrapped in a context manager; `clean.py` leaks the connection on any exception before `con.close()`.
- **Module-level mutable global state** — `AUDIT = {}` in `clean.py`, `RESULTS = {}` in `model.py`, `FINDINGS = []` in `eda.py`. Works for a script, blocks testability and parallel use. Return values instead.
- **No `if __name__` guard issue** — that part is fine and consistently done.
- **Bare `except Exception: continue`** in `model.blocked_cv` swallows genuine errors and silently reduces the fold count. At minimum log the exception.
- **`requirements.txt` is unpinned** (`pandas>=2.0`). For a reproducibility-focused project, pin exact versions (`pandas==2.2.3`) and add a `python_requires`. Consider `uv`/`pip-tools` lockfile.
- **Repo hygiene:** two `.zip` archives and a stray CSV sit in the project parent; `data/processed/mandi.db` is gitignored but `daily_prices_clean.csv` (a derived artefact) is committed — inconsistent policy.
- **`SUBMISSION_CHECKLIST.md` says "IIT Jodhpur account".** This is an IIT Mandi capstone. Small, but it is exactly the kind of thing an evaluator notices.
- **README says 8 mandis; `config.MANDI_FILTER` has 7.** Already inconsistent.

### 5.3 Code smells

- 62 lines of docstring for a 15-line function (`clean.resolve_duplicates`). The reasoning is excellent — but it belongs in `reconciliation_log.md` (where it already is, near-verbatim), with a two-line docstring plus a cross-reference. Right now the same paragraphs exist in three places and will drift out of sync.
- `run_sql.split_queries` regex `Q[1-9]` breaks at Q10.
- Output filename construction in `run_sql.py` line 77 is an unreadable chained expression producing filenames like `q4_year-on-year_comparison_per_mandi-month.csv` (hyphens in filenames from prose descriptions).
- `MONTHS` list duplicated in `model.py`, `build_extracts.py`, and as a `CASE` block in SQL. Put it in `config.py`.
- The `scope`/`base` CTE is copy-pasted six times across `analysis.sql` (~35 lines × 6). Deliberate and documented ("each query independently runnable"), but it means changing the date range requires 12 edits — directly contradicting the extensibility claim the same file makes.
- `make_memo_pdf.py` hardcodes every number of the memo as literal strings in `reportlab` calls. The memo cannot be regenerated from results; it must be hand-edited in Python.

### 5.4 Performance

Honestly: **there is no meaningful performance problem** at 6k rows, and I would not spend a minute on speed. The two things worth knowing (mention them in the viva as awareness, not as work done):

- `parse_agmarknet.aggregate_varieties` uses `groupby().apply()` with a Python function per group — O(n) Python calls. At 10k rows it is fine; at 5M rows (all-India, all-commodities) it would be the bottleneck. A vectorised `agg` with a pre-computed weight column is the fix.
- `check_vif` calls `variance_inflation_factor` in a loop, each call refitting an OLS — O(k²·n). With 20 dummy columns this is trivial; it scales badly in k.

---

## 6. Bugs found (verified by execution)

**B1 — `market_summary.csv` silently produces 0 rows on real data.** `build_extracts.e3_market` groups by `["mandi_id", "mandi_name", "district"]`. `parse_agmarknet` writes `district=None` for every market (Agmarknet's date-wise export has no district column). `pandas.groupby` drops NaN keys by default → **empty dataframe, no warning, empty CSV, broken dashboard page**. It works today only because the synthetic data had districts populated. Fix: `dropna=False`, or fill district from a mandi master, or drop it from the key.

**B2 — `parse_agmarknet.py` is orphaned from its own input.** It globs `cfg.RAW` (`data/raw/`) for `Date_wise*.csv`. The source export now lives in `data/agmarknet_source/`. Running it exits with *"No Agmarknet exports found"*. Worse, the reason someone moved it is real: `parse_agmarknet` **writes** `daily_prices.csv` into the same directory `load_db` globs for price files — so if you ever leave the Agmarknet export in `data/raw/`, `load_db` reads **both** the export and the parsed output and double-counts. Introduce a proper `data/01_source/ → data/02_interim/ → data/03_processed/` layering, or add explicit `SOURCE_DIR` to config.

**B3 — Surrogate `mandi_id` is assigned by row-count rank and is therefore unstable.** `parse_agmarknet` does `ids = {name: f"M{i+1}" for i, name in enumerate(coverage.index)}`. Add a second month of data and the ranking reshuffles, so `MANDI_FILTER = ["M1","M2","M3","M4","M7","M8","M10"]` silently selects **a different set of markets**. `config.py` warns about this in a comment ("RE-CHECK THIS LIST"), which is honest but is not a fix — and it directly falsifies the README's extensibility claim. **Key the filter on `mandi_name` (the natural key), or derive IDs from a stable hash of the canonicalised name.**

**B4 — `run_sql.split_queries` cannot see `Q10`+.** Regex is `Q[1-9]`. Change to `Q\d+`.

**B5 — `clean.assess_gaps` will crash on a single-observation mandi.** `gaps.max()` on an empty series returns NaN, and `int(NaN)` raises `ValueError`. Any mandi with exactly one report in scope kills the clean step.

**B6 — Hardcoded MAPE in the recommendation extract** (see Q4 above). Classed as a bug because it produces a *wrong number on a user-facing artefact*, not merely untidy code.

**B7 — Variety aggregation is internally inconsistent.** `min_price = min(all varieties)`, `max_price = max(all varieties)`, but `modal_price = arrivals-weighted mean`. The weighted modal can therefore be well inside a band that is now the union of all varieties' bands — and `clean.flag_impossible`'s `modal outside [min,max]` check becomes systematically weaker on multi-variety days. Defensible, but it should be stated in the reconciliation log; right now it isn't.

**B8 — `blocked_cv`'s `tr.month_num.nunique() < 12` guard silently yields zero folds** on any dataset shorter than a year. On the current real data, `model.py` produces no CV at all and reports nothing about it.

---

## 7. ML methodology issues

**M1 — No baseline.** The model is never compared against anything. Report at minimum: (a) global mean, (b) per-mandi mean, (c) per-(mandi, month) mean — that last one is the *actual competitor*, because a seasonal-mean lookup table is what a field agent would use without you. If OLS does not beat a mandi×month climatology, that is a finding worth reporting honestly, and the model card's framing makes it easy to report gracefully. **This is the single biggest methodological gap.**

**M2 — Residual autocorrelation is never tested.** Daily prices in a single mandi are strongly serially correlated. OLS standard errors, confidence intervals on `m2_month_coefficients.png`, and the p = 0.038 on `arrivals_dev` are all **too narrow** as a result. Run Durbin–Watson (already available in `model.summary()`, just not discussed) and refit with `cov_type="HAC"` (Newey–West) or cluster-robust SEs by mandi. This is a one-line change with a real methodological payoff and is exactly the kind of thing an econometrics-aware examiner probes.

**M3 — Heteroskedasticity acknowledged qualitatively, never tested.** §3.3 of the model card notes error rises with price level. That is textbook heteroskedasticity. Run Breusch–Pagan; consider modelling `log(modal_price)` so errors are multiplicative — which also makes MAPE the natural metric and directly addresses the "under-predicts peaks" shrinkage in §3.2.

**M4 — MAPE is the headline metric on a right-skewed target.** MAPE penalises over-prediction more than under-prediction and is unstable near low prices. Report MAE, RMSE, MAPE **and** sMAPE or MASE, and say which one you would optimise and why.

**M5 — 5 CV folds with `periods=n+1` from the 40th percentile is arbitrary.** Not wrong, but undefended. Either justify the 40% start and the 90-day test horizon agriculturally, or use `sklearn.model_selection.TimeSeriesSplit` and say why the parameters are what they are.

**M6 — Point predictions on a farmer-facing recommendation.** The dashboard emits `price_range_low/high` from a hardcoded ±7.7%. Real prediction intervals from `model.get_prediction().conf_int(obs=True)` cost one line and are strictly more honest. Given how much of this project's identity is "honest about uncertainty", this is a conspicuous miss.

**M7 — The model has no forecasting horizon.** It is an *explanatory* seasonal model presented in a decision context that implies prediction. The model card handles this well in prose ("appropriate: planning a typical window; not appropriate: predicting next week"). But no explicit statement of *what is known at decision time* exists. Formalise it: a farmer deciding in June knows month, mandi, and current arrivals — not August's arrivals. So `arrivals_dev` is **not available** for a forward-looking August recommendation. Right now the model quietly uses a contemporaneous feature to advise a decision made months earlier. Naming this explicitly would be a strong viva moment.

**M8 — No uncertainty on the seasonal recommendation itself.** The August coefficient rests on 3 Augusts, one containing a shock. The model card says this beautifully but never quantifies it — e.g. leave-one-year-out: does the August peak survive dropping 2025? That is a five-line experiment with a headline-worthy answer.

---

## 8. Data preprocessing issues

**P1 — Missingness verdict hardcoded** (§5.1 Q5). Compute it: a χ² test of missingness against weekday and month gives you a defensible, re-runnable verdict.

**P2 — No mandi name canonicalisation.** Real Agmarknet names are inconsistent across exports (case, punctuation, double spaces, typos like `COMITEE`). Without normalisation, the same market fragments across months. Add: uppercase → strip → collapse whitespace → strip `APMC` suffix → optional fuzzy match against a curated master list.

**P3 — Unit handling** (§5.1 Q3). Arrivals are tonnes in the source and treated as quintals throughout. Add `ARRIVALS_UNIT` to config and convert at parse time.

**P4 — `check_units` is a detector without a decision.** It flags a suspect ratio and returns `df` unchanged. Fine as a design choice, but the pipeline should at least *halt* on a suspect rather than logging and continuing.

**P5 — `min`/`max` prices are loaded, validated, and then never used.** The data-quality note admits this. Two cheap wins: (a) `(max − min)/modal` is a **price-dispersion / grade-spread feature** with real economic meaning; (b) `variety_spread_pct` is already computed in `parse_agmarknet` and then **thrown away** — it never reaches the database. Recover it.

**P6 — Rolling windows are row-based, not calendar-based.** `rolling(7)` over reported rows means "last 7 *reported* days", which the SQL comment defends thoughtfully. But with 15.8% missing, "7 reported days" can span 9 calendar days, and the span varies by mandi. The defence is good; add the actual calendar span as a diagnostic column so the reader can see it.

**P7 — `min_periods=1` on the rolling mean** means the first row's "7-day average" is a single observation. Downstream, `pct_vs_7d_trend` is then exactly 0 for every mandi's first day. Harmless here, but it should either be `min_periods=4` or the first rows should be flagged.

**P8 — No holiday/market-closure calendar.** Mandis close for festivals and bandhs. Treating those as "missing at random" is a modelling assumption that a state-specific holiday calendar would let you test properly, and would strengthen the C4 argument considerably.

---

## 9. Feature engineering opportunities

Ranked by expected value **given the constraint that the brief specifies one linear model** — so favour features that stay interpretable.

1. **`log(modal_price)` as target.** Makes the effects multiplicative ("August is 2.1× February") which is both more natural for prices and more robust to the peaks. Directly attacks the §3.2 shrinkage bias. *Highest value, lowest cost.*
2. **`mandi × month` interaction — tested, then rejected with evidence.** The feature spec rejects it a priori from F5's parallel curves. Fit it once, report the F-test, and reject it on a *test statistic* rather than a chart. Turns a judgement call into a demonstrated one.
3. **Lagged arrivals (`arrivals_dev` at t−7, t−14)** — available at decision time (unlike contemporaneous arrivals, §M7) and captures supply momentum.
4. **Cumulative season-to-date arrivals** — a proxy for total crop size, which is *the* variable that separates a shock August from an ordinary one. This is the highest-value engineered feature available from data you already have, and it partly answers the model card's "this is unfixable without external data".
5. **`days_since_last_report`** — a direct measure of thin evidence, per row.
6. **Grade-spread `(max − min)/modal`** and the recovered `variety_spread_pct` (P5).
7. **Price relative to the state-wide same-day mean** — separates "this mandi is expensive" from "everything is expensive today"; converts an absolute-price model into a basis model, which is closer to what an arbitrage decision actually needs.
8. **Fourier terms (sin/cos of day-of-year, 2–3 harmonics)** instead of 12 month dummies — 4–6 parameters instead of 11, a smooth curve, and a far better fit with only 2.5 years. Given that "each month is observed 2–3 times" is stated as the project's largest limitation, this is a *direct structural response* to it, and comparing the two parameterisations would be a genuinely impressive slide.
9. **`is_festival_window` / Diwali proximity** — onion demand is seasonal in a way the calendar month only partly captures.
10. **External joins** (rainfall, sowing acreage, export-policy dates) — already correctly identified in the model card §5 as the real fix. Even joining **one** of these — IMD district rainfall is free and downloadable — would move this project from "identifies the limitation" to "closes the limitation", which is the difference between an A and an A+.

---

## 10. Model improvement opportunities

Keep OLS as the headline model — the brief asks for one, and interpretability is the point. But:

1. **Add the baseline ladder** (§M1). Non-negotiable in my view.
2. **Robust standard errors** (HAC/clustered) — one line, fixes M2, and lets you defend the CIs on your own coefficient chart.
3. **Log-target variant** reported alongside, with a back-transform (Duan smearing) so ₹ figures remain honest.
4. **Prediction intervals** on the recommendation layer (§M6).
5. **Leave-one-year-out seasonal stability check** (§M8) — the single most persuasive robustness test available on this data.
6. **A regularised or hierarchical alternative as a *comparison*, not a replacement.** A partial-pooling model (mandi effects drawn from a common distribution) is the textbook right answer for 8 mandis with unequal coverage, and *saying so* — even if you don't fit it — demonstrates modelling maturity. If you do fit it, `statsmodels.MixedLM` with a random intercept by mandi is ~5 lines.
7. **Quantile regression at τ = 0.9** to model the *upside*. The whole memo says "the real peak will be higher than predicted". A 90th-percentile model literally answers "how high could August go?", which is the question a storing farmer actually has. This would be a standout addition and costs very little.
8. **A gradient-boosted comparison, clearly framed as a diagnostic not a deliverable** — if LightGBM beats OLS by 3%, that quantifies how much non-linearity you are leaving on the table; if it doesn't, it *validates the linear specification*, which is a strong and unusual thing to be able to say.
9. **`model.summary()` is written to disk and never interpreted.** Durbin–Watson, condition number, Jarque–Bera and Omnibus are all sitting in `model_summary.txt` unread. Pull three of them into the model card.

---

## 11. UI/UX improvements

**The dashboard does not exist yet** — this is the largest single scoring gap after the data. The build guide is genuinely strong (the month-sort trap warning, the DAX-free design, observation counts travelling with every aggregate). Build it exactly as written, then:

1. **Lead with the decision, not the chart.** The top-left card should read *"Sell in August — worth ₹1,118/quintal more than February"*, not a KPI number. The `recommendation.csv` extract already encodes SELL NOW / GOOD TO SELL / HOLD IF YOU CAN / STORE OR SELL LOCAL — that relabelling (documented as M3 in the AI appendix) is a real UX insight and should be visually prominent, not buried in a matrix.
2. **Show uncertainty visually.** A shaded band on the seasonal curve, not a footnote. Your project's identity is honesty about uncertainty; the dashboard should *look* like that.
3. **Surface the evidence flag.** `evidence = "Thin (<40 obs)"` exists in the extract — render thin cells greyed or hatched so a user cannot act on them by accident.
4. **The "honesty page" (Page 2) is a differentiator.** Very few students will put model error on the dashboard itself. Make it a deliberate design statement in the walkthrough: *"page 2 exists so a field agent can see when not to trust page 1."*
5. **Accessibility:** the orange `#c1440e` / grey `#4a5568` palette is good and colour-blind-safe. Keep it consistent between matplotlib figures and Power BI so the deck looks like one artefact.
6. **A mobile/print one-pager** — the actual consumption context is a field agent with a phone. Even a mock of a one-page "sell card" per mandi would show product thinking.
7. **Figure quality (matplotlib):** already above average — left-aligned bold titles that *state the claim* rather than describe the axes, `figure.dpi=130`, spines removed, alpha-graded scatter. Two fixes: `f1_seasonal_curve.png` annotations collide with the data (the "Feb trough" label sits on the line), and several figures have no source/date footer. Add a standard footer with data span + generation date to every figure — small touch, very professional.
8. **A warning about `f1_seasonal_curve.png` specifically:** the eight mandi curves are almost perfectly parallel and implausibly smooth. To anyone who has seen real Agmarknet data this is an immediate tell that the data is synthetic. Regenerating on real data fixes it; until then, that figure is a liability, not an asset.

---

## 12. Documentation improvements

The documentation is the strongest part of this project. Improvements are therefore mostly about **consistency and hierarchy**, not content.

1. **Fix the provenance claims** (§5.1 Q2) — the highest-priority documentation change in the repo.
2. **Add an architecture diagram to the README.** There is no visual of the pipeline anywhere. A Mermaid diagram (renders natively on GitHub) of source → parse → load → clean → EDA → model → extracts → dashboard, placed immediately after the headline. This is the single highest-impact-per-minute documentation change.
3. **Add a results-provenance table** — for each headline number, which script produced it, from which data, on which date. Kills the entire class of stale-number problems and reads as very senior.
4. **De-duplicate the reasoning.** The duplicate-resolution argument appears in `clean.py`'s docstring, `reconciliation_log.md` R5, and `data_quality_note.md` C1 in three near-identical versions. Pick the log as canonical; make the others one-line cross-references.
5. **Numbers appear in 7 documents and will drift.** Consider generating the numeric parts of the model card from `model_results.json` via a small Jinja template. If that is too much, add a `docs/NUMBERS.md` single source of truth and reference it.
6. **`make_memo_pdf.py` should render from `decision_memo.md`**, not from hardcoded reportlab strings, so the MD and PDF cannot diverge.
7. **Add "How to extend this to a new commodity" as a worked example** in the README — you claim extensibility; demonstrate it in five lines with actual output.
8. **Fix "IIT Jodhpur" → "IIT Mandi"** and the 8-vs-7 mandi count inconsistency.
9. **Add a `CHANGELOG.md`** — even three entries. It signals engineering discipline and costs nothing.
10. **The AI appendix is excellent** (four *real* errors, with the mechanism of detection, and the "wider lesson" framing on M1). Two additions: the judgment-note section appears truncated — finish it; and add M5 documenting the synthetic-vs-real data confusion found in this review. **An AI appendix that includes an error found after the AI appendix was written is far more credible than one that doesn't.**

---

## 13. Presentation improvements

You have a walkthrough script (6–7 min) with a good structure. Refinements:

1. **Open with the number, not the context.** *"A Maharashtra onion farmer who sells in February instead of August loses ₹1,118 per quintal. That's roughly half their revenue. Here's how I know, and here's where I'd stop trusting it."* Then the question.
2. **Make the Simpson's paradox the spine of the talk.** It is your best asset. Structure: here's the obvious answer (r = −0.719, supply and demand) → here's why it's wrong → here's what changed in the model → here's what a field agent can now say out loud. That arc is memorable and it demonstrates *analysis*, not *tooling*.
3. **Show one failure live.** Put `m3_residual_diagnostics.png` on screen and say *"the model under-predicts the top 5% of prices by ₹577/quintal — always in the same direction."* Volunteering a weakness before you're asked is the single most reliable way to be trusted in a viva.
4. **Have a "what I'd do next quarter" slide.** Rainfall join first, then acreage. Shows the project has a roadmap, not just an endpoint.
5. **Rehearse the three questions you will definitely be asked:**
   - *"Why linear regression and not XGBoost?"* → interpretability is the deliverable; a coefficient in ₹ is what a field agent can act on; and (if you do §10.8) *"I tested it — here's the gap."*
   - *"How do you know August is really the peak?"* → the honest answer is *"3 observations, one shocked, and here's the leave-one-year-out test."* Have the test.
   - *"Is your data real?"* → this must have a clean, confident answer. Right now it does not.
6. **Time-box ruthlessly.** 6 minutes for 5 documents' worth of content means ~40 seconds per major point. Script the transitions, not just the content.
7. **Slide design:** one claim per slide, stated as the title (mirror what you already do well in your matplotlib titles). No slide should be titled "EDA" or "Modelling".

---

## 14. Repository improvements

1. **`git init` today, and commit in logical increments** — not one "initial commit" with everything. Real history is evidence of process, and it is a graded signal. Write meaningful messages (Conventional Commits if you like).
2. **Restructure `data/` into numbered layers:** `data/01_source/` (immutable, read-only), `data/02_interim/`, `data/03_processed/`. Eliminates B2's glob collision by construction.
3. **Package the code:** `src/mandi_watch/` + `pyproject.toml` + `pip install -e .`.
4. **Add `Makefile` (or `run_pipeline.py`)** with `make data`, `make model`, `make dashboard`, `make all`, `make test`.
5. **Add `tests/`** with `pytest` and small CSV fixtures (§4.2.7). Even 8 tests changes how the repo reads.
6. **Add GitHub Actions CI** — lint (`ruff`) + `pytest` + a smoke run of the pipeline on a tiny fixture. A green badge in the README is disproportionately persuasive to an evaluator.
7. **Add `pre-commit`** with `ruff`, `black`, `nbstripout`, and a large-file guard.
8. **Move the zips and the stray root CSV out** of the project parent.
9. **Add `LICENSE` (MIT), `CITATION.cff`, and `.env.example`** if any paths become configurable.
10. **Add `docs/`** and consider GitHub Pages for the figures + memo — a public URL is easier for an evaluator than a Drive folder.
11. **Pin `requirements.txt` exactly**, and add `requirements-dev.txt`.
12. **Consider DVC or a simple `data/MANIFEST.md` with SHA-256 checksums** for each source export — gives a verifiable answer to "is this the data you actually used?"

---

## 15. What would impress IIT Mandi professors most

Ranked by impact per hour, based on what actually distinguishes submissions at this level.

**Tier 1 — the things that decide the grade**

1. **A pipeline that runs end-to-end on real data and reproduces every number in the README.** Nothing else matters as much. Right now a single command exposes the project; after this fix, the same command becomes your strongest evidence.
2. **The Simpson's paradox story, told from real data.** It is a real statistical insight, correctly diagnosed, that *changed the model specification*. Most capstones report metrics; this one reports a decision. That is graduate-level work — provided the correlation survives contact with real records (it may not, and the honest handling of that would itself be impressive).
3. **The honesty architecture** — reconciliation log, negative results recorded explicitly ("the check ran and found nothing"), config defaults overridden by evidence, the refusal to quote 4.8% MAPE when 7.7% is the honest number. Professors see confident wrong answers constantly. They rarely see a student volunteer that their own best-looking metric was misleading and explain why. **Make this the explicit theme of the presentation.**

**Tier 2 — the differentiators**

4. **Beating (or failing to beat) a mandi×month baseline, reported either way.** Demonstrates you know what a model is *for*.
5. **Robust standard errors + a stated autocorrelation diagnosis.** Signals real statistical training, not library usage.
6. **Tests + CI.** Almost no capstone has these. A green badge says "engineer", not "student".
7. **Joining one external dataset (IMD rainfall).** Moves you from *naming* the limitation to *closing* it. If August prices correlate with July rainfall in your data, that is a publishable-quality finding for a one-month project.
8. **Quantile regression for the upside** — answers the farmer's real question ("how high might it go if I hold?") rather than the analyst's.

**Tier 3 — polish that compounds**

9. Architecture diagram in the README.
10. The dashboard's page-2 honesty layer, presented as a deliberate design decision.
11. A CHANGELOG and clean commit history.
12. The AI appendix, extended with an error you found *after* writing it.

**What will lose marks, plainly:** synthetic data presented as Agmarknet; a pipeline that does not run; no git history; a dashboard that does not exist. All four are fixable this week.

---

## 16. Prioritised roadmap

### 🔴 HIGH — do these first; the submission is at risk without them

| # | Task | Effort | Why |
|---|---|---|---|
| H1 | **Download 30 monthly Agmarknet exports** (Jan 2024 – Jun 2026, Onion, Maharashtra) into `data/01_source/` | 2–3 h | Everything depends on this |
| H2 | **Fix B3** — key `MANDI_FILTER` on canonical `mandi_name`, not rank-derived IDs | 45 m | Without it, adding months silently changes which markets you analyse |
| H3 | **Fix B2** — separate source/interim/processed dirs; repoint `parse_agmarknet` | 30 m | Removes the glob collision and un-orphans the parser |
| H4 | **Fix P2/P3** — mandi name canonicalisation + tonnes→quintals conversion | 1 h | Otherwise markets fragment and the headline coefficient is 10× wrong |
| H5 | **Re-run the full pipeline on real data**; regenerate every figure, table and JSON | 1 h | The moment of truth |
| H6 | **Update every number in README, memo, model card, feature spec, data-quality note, EDA findings** to the real-data values | 2–3 h | Tedious, unavoidable, and where §12.5 (single source of truth) pays for itself |
| H7 | **Fix B1** (`market_summary` 0 rows), **B6** (hardcoded MAPE), **B4**, **B5** | 1 h | Silent wrongness on user-facing artefacts |
| H8 | **`git init` + structured commit history + push to GitHub** | 1 h | Graded deliverable, currently absent |
| H9 | **Build the Power BI dashboard** per the guide; verify "Publish to web" early | 3–4 h | Graded deliverable; the publish permission is the risk, test it first |
| H10 | **Record the walkthrough** | 2 h | Graded deliverable |
| H11 | **Add a single entrypoint** (`make all` / `run_pipeline.py`) that runs all 7 steps and fails loudly | 45 m | Turns "does it run?" from a risk into a demo |
| H12 | **Fix Q5** — compute the missingness verdict rather than asserting it | 30 m | An audit line that cannot fail undermines the audit's credibility |

*Estimated total: ~16–20 hours. This is the minimum viable excellent submission.*

### 🟡 MEDIUM — these are what move it from "very good" to "best in batch"

| # | Task | Effort | Why |
|---|---|---|---|
| M1 | **Baseline ladder** (global mean / mandi mean / mandi×month mean) vs the model | 1 h | Biggest methodological gap; likely viva question |
| M2 | **HAC or cluster-robust standard errors** + Durbin–Watson discussion | 45 m | Fixes over-narrow CIs; signals statistical maturity |
| M3 | **Prediction intervals** replacing the hardcoded ±7.7% band | 1 h | Consistent with the project's honesty identity |
| M4 | **Leave-one-year-out seasonal stability test** | 1 h | Directly quantifies the project's self-declared largest limitation |
| M5 | **`logging` throughout, replacing `print`** | 1 h | Your own coding standard; visible in every demo transcript |
| M6 | **`tests/` with ~8 pytest cases**, including the date-parser regression test for M1 | 2–3 h | Almost no capstone has tests |
| M7 | **Architecture diagram (Mermaid) in README** + results-provenance table | 1 h | Highest documentation impact per minute |
| M8 | **Package the code** (`src/mandi_watch/`, `pyproject.toml`) | 1 h | Removes the cwd dependency; reads as professional |
| M9 | **Fix documentation inconsistencies** (IIT Jodhpur→Mandi, 8 vs 7 mandis, de-duplicate reasoning) | 45 m | Cheap credibility |
| M10 | **Log-target model variant**, reported alongside | 1 h | Addresses the shrinkage bias structurally |
| M11 | **Recover `variety_spread_pct`** into the DB and use it | 45 m | Already computed and thrown away |
| M12 | **Regenerate the memo PDF from the Markdown** rather than hardcoded strings | 1 h | Prevents MD/PDF divergence |

*Estimated total: ~13–16 hours.*

### 🟢 LOW — do if time allows; each is a genuine differentiator but none is load-bearing

| # | Task | Effort | Why |
|---|---|---|---|
| L1 | **Join IMD district rainfall** | 4–6 h | Highest ceiling of anything on this list — could close the project's central limitation |
| L2 | **Quantile regression (τ=0.9)** for the holding-upside question | 2 h | Answers the farmer's real question |
| L3 | **Fourier seasonality vs 12 month dummies**, compared | 2 h | Structural response to the "2–3 observations per month" limitation |
| L4 | **GitHub Actions CI** (ruff + pytest + smoke run) | 1.5 h | Green badge, disproportionate persuasive value |
| L5 | **Gradient-boosted comparison as a diagnostic** | 2 h | Either quantifies the non-linearity gap or validates the linear spec |
| L6 | **Cumulative season-to-date arrivals feature** | 1 h | Best shock-proxy available from existing data |
| L7 | **Mixed-effects / partial-pooling model** as a comparison | 2 h | Textbook-correct for 8 unequal groups |
| L8 | **Pandera/Great Expectations data contracts** | 2 h | Converts prose data-quality claims into executable checks |
| L9 | **`pre-commit`, `LICENSE`, `CITATION.cff`, `CHANGELOG.md`**, pinned requirements | 1 h | Repo hygiene |
| L10 | **Data manifest with SHA-256 checksums** per source export | 45 m | Verifiable provenance |
| L11 | **Field-agent one-pager mock** (print/mobile "sell card") | 1.5 h | Product thinking |
| L12 | **Figure footers** (data span + generation date) on all 9 figures | 30 m | Small, very professional |

---

## 17. One thing I would push back on

The repository's greatest strength — the density and quality of the written reasoning — is also creating a risk. There are now **seven documents** carrying overlapping versions of the same arguments and the same numbers, plus docstrings that duplicate them a third time. On synthetic data that is merely redundant. After the real-data re-run it becomes a **consistency hazard**: you will update five of seven places and ship a contradiction, and a contradiction between your own documents damages the honesty framing far more than any single wrong number would.

Before H6, spend thirty minutes deciding which document is canonical for each claim, and make the others reference it. That decision will save more marks than any modelling improvement on this list.

---

*No code was modified in producing this review. Pipeline behaviour was verified by executing an isolated copy of the repository.*
