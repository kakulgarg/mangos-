# Submission Checklist

IIT Mandi CCE — AI & Data Science capstone (Project #5). Three submission items,
each with its own rules.

---

## Built and ready

- [x] Real Agmarknet data — 25 monthly exports, 31,930 rows, 111 markets (`data/01_source/`)
- [x] End-to-end pipeline, one command (`src/run_pipeline.py`, ~20s)
- [x] GitHub repo structure + non-technical README with architecture diagram (`README.md`)
- [x] SQL script — schema + **seven** analytical queries incl. variety (`sql/`)
- [x] Analysis pipeline with cleaning documented (`src/`, `notebooks/`)
- [x] Data quality note, real numbers + computed verdicts (`notebooks/data_quality_note.md`)
- [x] Reconciliation log, 9 entries (`notebooks/reconciliation_log.md`)
- [x] Feature specification (`notebooks/feature_spec.md`)
- [x] Model card — explanatory OLS **and** forecaster, with failure analysis (`notebooks/model_card.md`)
- [x] **Next-month price forecaster** — baselines + LightGBM + ensemble + intervals (`src/forecast.py`)
- [x] Test suite, 9 pytest cases (`tests/`)
- [x] One-page decision memo — MD + **PDF (rendered from the MD)** (`memo/`)
- [x] AI Workflow Appendix, 6 documented errors incl. the synthetic→real pivot (`ai_appendix/`)
- [x] Limitations section (README, memo, model card)
- [x] Power BI extracts, **7 CSVs** incl. variety + forecast (`dashboard/data/`)
- [x] Power BI build guide (`dashboard/POWERBI_BUILD_GUIDE.md`)
- [x] Walkthrough script (`walkthrough_script.md`)

## You must do these (need your account / your voice)

- [ ] **Build the Power BI dashboard** — follow `POWERBI_BUILD_GUIDE.md` (all 7 extracts ready)
- [ ] **Test "Publish to web" with your IIT Mandi account** — do this first, not
      last. If unavailable, use the `.pbix` + PDF + screenshots fallback and tell
      your instructor why.
- [ ] **Record the walkthrough**, 5–10 min, your own voice (`walkthrough_script.md`)
- [ ] **Push to GitHub** (repo is initialised with a clean commit history)
- [ ] Add the dashboard and video links to `README.md` (two placeholders marked)

## The three submission items

**1. Drive folder** — upload the whole project folder as-is.
- [ ] Sharing set to "Anyone with the link can view"
- [ ] **Verified in an incognito window**

**2. Zoom/video link**, 5–10 minutes
- [ ] Publicly accessible
- [ ] **Verified in an incognito window**

**3. Report PDF** — `memo/decision_memo.pdf`

---

## Before you submit

Test all three links from a browser where you are **not signed into your Google
account**. This is the most common failure and it is entirely avoidable.

---

## Rubric self-rating

| Part | Level | Evidence |
|---|---|---|
| SQL | **Standout** | Window functions + CTEs; scope in one `scope` CTE; 7th query adds the variety dimension |
| Cleaning | **Standout** | Computed audit verdicts (missingness verdict flips to non-random on real data); tonnes→quintals guard; spikes retained with measured rationale |
| Exploration | **Standout** | Honestly reframed when the synthetic "Simpson's paradox" did not replicate (R8/M5); every figure claim data-driven |
| Model | **Standout** | Explanatory OLS with HAC robust SEs **and** a monthly forecaster; baseline ladder; walk-forward backtest; ML honestly ties persistence, ensemble adds intervals |
| Forecasting | **Standout** | Lag-feature LightGBM + persistence/seasonal-naive baselines + hybrid ensemble + quantile prediction intervals + feature importance |
| Dashboard | *Pending* | 7 extracts + guide ready; **depends on you building and publishing it** |
| Memo | **Standout** | Prioritised (when/where/which/next-month), trade-offs stated, storage qualifier makes it actionable; PDF auto-rendered from MD |
| AI appendix | **Standout** | Six real errors incl. discarding a synthetic-data finding and reporting that ML tied a naive baseline |
| Engineering | **Standout** | One-command pipeline, logging, pinned deps, 9 tests, packaged layout, clean git history |
| README + walkthrough | **Strong → Standout** | README leads with business impact + architecture diagram; **depends on the recording** |

**What stands between this and a full Standout across the board:** building and
publishing the dashboard, and recording the walkthrough. Both are yours to do; all
the data and scripts they need are in place.
