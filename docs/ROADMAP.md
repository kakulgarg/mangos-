# Revised Roadmap — Mandi Price Watch (real data + varieties + forecasting)

**Supersedes §16 of `REPO_REVIEW.md`.** Reflects the real Agmarknet dataset and the scope you confirmed on 25 Jul 2026.

---

## Confirmed scope

| Decision | Choice | Consequence |
|---|---|---|
| **Data** | Real Agmarknet (33,054 rows, 24 months Jun 2024–Jun 2026, 111 markets, 12 varieties) | Drop all synthetic numbers; re-run everything |
| **Forecasting** | ML forecaster with lag features | New model; **paired with** a seasonal-naive baseline + SHAP for interpretability |
| **Varieties** | Per-variety where meaningful (Red/Local/White/Unhali separate; "Other" labelled) | Keep `variety` as a dimension through parse → DB → dashboard |
| **Mandi scope** | Curated high-coverage subset (~10–15) | Load all 111 into DB; recommend on the reliable subset only |

### The three-model design (why this is defensible, not over-engineered)

1. **Explanatory OLS** (existing) — answers *"why is the price what it is?"* Keeps the Simpson's-paradox story, the month/mandi coefficients in ₹. This is your interpretability anchor.
2. **Seasonal-naive baseline** (new, ~1 hr) — *"next month = this mandi's historical average for that month, adjusted to the recent level."* The honest benchmark every forecast must beat.
3. **ML forecaster — LightGBM on lag features** (new) — *"what will next month's price be, per mandi and variety?"* Made explainable with SHAP so a field agent hears *"this forecast is driven mostly by last month's price and the August seasonal lift,"* not a black box.

The dashboard answers all your questions: best mandi, best month, average price, **best variety** by month/mandi, and **next-month forecast** per mandi with a "which mandi pays most next month" ranking.

---

## Data issues to handle (found in your real files)

- **August 2024 missing** — a genuine gap; forecaster's 12-month lag must tolerate it (leave, don't fabricate).
- **Duplicate February 2025 file** — de-duplicate on load.
- **"Other" = 48% of rows** — label explicitly; don't silently merge it into a real variety.
- **Mandi name noise** — real names are uppercase, double-spaced, misspelled (`COMITEE`), variant across months → **canonicalise** or markets split.
- **Arrivals are Metric Tonnes** — convert to quintals (×10) or the price/arrivals coefficient is 10× wrong.
- **Modal up to ₹25,000/qtl** — real shocks; keep, but widen plausibility bounds and flag.

---

## 🔴 HIGH — foundation; nothing works without these

| # | Task | Effort |
|---|---|---|
| H1 | Restructure `data/` → `01_source / 02_interim / 03_processed`; drop 25 real CSVs into source | 20 m |
| H2 | Fix parser: repoint to source dir, de-dup Feb 2025, **keep `variety`**, convert arrivals t→qtl | 1.5 h |
| H3 | **Mandi canonicalisation** + key `MANDI_FILTER` on names, not rank IDs (fixes B3) | 1 h |
| H4 | Curated subset selection via coverage threshold; load all 111 to DB, recommend on subset | 45 m |
| H5 | Widen plausibility bounds for real shocks; make cleaning verdicts *computed*, not hardcoded (Q5) | 45 m |
| H6 | Add `variety` dimension through DB schema + all 6 SQL queries + extracts | 1.5 h |
| H7 | Re-run explanatory pipeline (load→clean→sql→eda→model) on real data | 1 h |
| H8 | **Build seasonal-naive baseline + walk-forward backtest harness** | 2 h |
| H9 | **Build LightGBM lag-feature forecaster** (lag-1m, lag-12m, rolling, arrivals lags; per mandi×variety) | 3–4 h |
| H10 | **SHAP / feature-importance** on the forecaster for the interpretability layer | 1 h |
| H11 | Regenerate all figures, JSON, extracts; **update every number** in README/memo/model card | 3 h |
| H12 | Fix B1 (`market_summary` 0-rows), B6 (hardcoded MAPE → read from JSON), B4, B5 | 1 h |
| H13 | `git init` + structured commits + push to GitHub | 1 h |
| H14 | Single entrypoint (`run_pipeline.py` / `make all`) that runs all steps, fails loudly | 45 m |
| H15 | **Build Power BI dashboard** (best mandi / best month / avg price / variety / next-month forecast); verify Publish-to-web early | 4 h |
| H16 | Record walkthrough | 2 h |

*≈ 30–34 h — the core excellent submission.*

## 🟡 MEDIUM — moves it to best-in-batch

| # | Task | Effort |
|---|---|---|
| M1 | Baseline ladder comparison table (naive vs OLS vs LightGBM) reported honestly | 1 h |
| M2 | Proper forecast **prediction intervals** on the dashboard (not a hardcoded ±band) | 1.5 h |
| M3 | HAC/cluster-robust SEs + Durbin–Watson on the OLS | 45 m |
| M4 | Leave-one-year-out seasonal stability test | 1 h |
| M5 | `logging` throughout (replaces `print`) | 1 h |
| M6 | `tests/` (~10 pytest cases): parser, dates, variety weights, canonicalisation, forecaster leakage | 3 h |
| M7 | Architecture (Mermaid) diagram + results-provenance table in README | 1 h |
| M8 | Package the code (`src/mandi_watch/`, `pyproject.toml`) | 1 h |
| M9 | Fix doc inconsistencies (IIT Jodhpur→Mandi, mandi counts, de-duplicate reasoning) | 45 m |
| M10 | Log-target OLS variant for the shrinkage/peak bias | 1 h |
| M11 | Regenerate memo PDF from Markdown, not hardcoded strings | 1 h |

*≈ 13–15 h.*

## 🟢 LOW — differentiators if time allows

| # | Task | Effort |
|---|---|---|
| L1 | Join IMD district rainfall (could partly *close* the shock-blindness limitation) | 4–6 h |
| L2 | Quantile forecast (τ=0.9) — "how high could next month go if I hold?" | 2 h |
| L3 | Cumulative season-to-date arrivals feature (best shock proxy from existing data) | 1 h |
| L4 | GitHub Actions CI (ruff + pytest + smoke run) | 1.5 h |
| L5 | Pandera/Great Expectations data contracts | 2 h |
| L6 | Field-agent one-page "sell card" mock (print/mobile) | 1.5 h |
| L7 | Figure footers (data span + generation date); repo hygiene (LICENSE, CHANGELOG, pinned reqs) | 1 h |

---

## Suggested order of execution

1. **H1–H7** first — get real data flowing through the existing explanatory pipeline. This alone makes the project honest.
2. **H8–H10** — the forecasting layer (your headline new feature).
3. **H11–H14** — regenerate docs, wire the entrypoint, put it under version control.
4. **H15–H16** — dashboard + recording (the graded artefacts).
5. Then MEDIUM, then LOW as time permits.

**Awaiting your approval before writing any code.** Tell me if this scope and ordering look right, or what to adjust.
