# Model Card — Onion Price, Maharashtra

Two models, each with a clear job:

| | Explanatory model | Forecaster |
|---|---|---|
| **Question** | *Why* is the price what it is? | *What* will next month's price be? |
| **Method** | OLS, HAC robust SEs | persistence + seasonal-naive + LightGBM → hybrid ensemble |
| **Grain** | daily, mandi-day | monthly, mandi-month |
| **Target** | `modal_price` (₹/qtl) | month-over-month change in `modal_price` |
| **Reported figure** | month & market effects in ₹ | walk-forward MAE ₹168 / 13.9% |

Data: 14 curated Maharashtra markets, Jun 2024 – Jun 2026 (24 months; Aug 2024
absent from the source).

---

## Part A — Explanatory model (the "why")

**Specification:** `modal_price ~ arrivals_dev + C(month) + C(mandi)`, fitted with
Newey–West **HAC standard errors** (`maxlags=5`) because daily prices within a
mandi are strongly autocorrelated and classical SEs would be far too narrow.

### It is a weak *daily* predictor — and that is the point

| Evaluation | MAE | MAPE | R² |
|---|---|---|---|
| Train (2024-06 → 2026-02) | ₹718 | 44.7% | 0.245 |
| Test (chronological 20%) | ₹444 | 44.5% | −1.84 |

Month and market explain only about **25% of daily price variance**. Onion prices
swing far more day-to-day than a static seasonal curve can track, and the test
R² is negative because the held-out window (Feb–Jun 2026) is both low-priced and
sits at a level the training coefficients over-shoot. **This is not a failure to
hide — it is the reason a lag-based forecaster is needed** (Part B): the decision
is monthly, and at monthly grain the price is far more predictable.

### What the model is good for: the seasonal and market effects

Even with low daily R², the coefficients recover a clean, farmer-checkable shape:

- **Month effects** peak in **Sep–Nov** and trough in **Apr–May** — a swing of
  about **₹1,500/quintal** between the best and worst month (see
  `outputs/figures/m2_month_coefficients.png`, with HAC confidence intervals).
- **Market effects**: the Nashik belt (Lasalgaon, Pimpalgaon) sits **12–16%**
  above the state average, Chhatrapati Sambhajinagar **27%** below — a spread of
  **₹756/quintal**, gross of transport.
- **`arrivals_dev`** (arrivals minus that month's mean): coefficient
  **−0.036 ₹/quintal** per extra quintal. Statistically detectable but
  **economically negligible** — 1,000 extra quintals moves price ~₹36 against a
  seasonal swing of ₹1,500. A single mandi's own arrivals barely matter (see
  EDA F2–F4); price is set by the wider market.

### What changed from the earlier (synthetic) analysis

The scaffold's synthetic data showed a dramatic "Simpson's paradox" sign-flip in
the arrivals–price relationship. **On real Agmarknet data that effect does not
exist** (pooled r ≈ −0.03, within-month r ≈ +0.07; VIF 1.03). We report the real
finding — arrivals is a weak predictor — rather than a story the data no longer
supports. This is documented as M5 in the AI appendix.

---

## Part B — Forecaster (the "what next month")

### Why monthly, per mandi

Daily prices are dominated by shocks, but the farmer's decision is monthly, and a
market's **monthly** price correlates **0.86 with the previous month's**. That
persistence is real, forecastable signal.

### A baseline ladder, so the ML model must earn its place

Walk-forward backtest (train on all months strictly before the test month, roll
forward; 196 mandi-months evaluated):

| Model | MAE | RMSE | MAPE | Bias |
|---|---|---|---|---|
| **persistence** (next = this month) | ₹169 | ₹227 | 14.1% | +25 |
| seasonal_naive (next = same month last year) | ₹1,044 | ₹1,423 | 91.7% | −1,012 |
| lightgbm (lag features, models the change) | ₹199 | ₹253 | 16.8% | +35 |
| **ensemble** (0.6·persistence + 0.4·lightgbm) | **₹168** | **₹221** | **13.9%** | +29 |

**Honest reading.** Persistence is a very strong baseline — monthly onion prices
are close to a random walk. LightGBM alone does *not* beat it; the hybrid
**ensemble edges it** (₹168 vs ₹169) and, more importantly, comes with a
**calibrated prediction interval** persistence cannot provide. Seasonal-naive is
poor here because year-over-year prices swing wildly with shocks, so "same month
last year" is a bad guide.

Two design choices earned the ensemble its result:
1. **Differencing** — LightGBM predicts the month-over-month *change*, then adds
   it to last month. A level-target tree cannot predict a price higher than
   anything in training, so it underestimates shock months; differencing fixes
   this.
2. **Conservative trees** — the monthly panel is only ~300 rows, so shallow leaves
   (`num_leaves=7`), a high min-leaf count, and a slow learning rate keep variance
   down.

### What drives the forecast (interpretability)

Gain-based feature importance (LightGBM), so the forecast is explainable rather
than a black box: **recent lags (lag-1, lag-3, roll-3) and the month-over-month
change dominate, followed by the seasonal month terms.** Permutation importance
agrees. Full table in `outputs/forecast_feature_importance.csv` and
`outputs/figures/fc2_feature_importance.png`.

### Prediction intervals

Next-month price per mandi is reported with a **10th–90th percentile band** from
LightGBM quantile models, so the dashboard never implies false precision. For
**July 2026** the top-ranked market is **Pimpalgaon Baswant at ₹1,788/quintal
(₹1,555–1,884)**.

---

## Where both models break

**Neither can see a supply shock.** The two 2024–25 shock episodes (prices to
₹25,000/quintal) have no corresponding variable in the dataset — no weather, no
MSP, no export policy. Every model under-predicts the peak, always in the same
direction: **the real peak will be higher than predicted, never lower.** This is a
missing-data problem, not a modelling one; the fix is external data (§ below), not
a fancier algorithm.

**The seasonal pattern rests on ~2 observations per month, and August 2024 is
missing.** There is no statistical way, with this data, to separate "November is
reliably the peak" from "two unusual Novembers."

## What data would fix this

1. **District rainfall/temperature (IMD, daily, free)** — the direct driver of
   supply shocks. Highest-value single addition.
2. **Sowing acreage by district and season** — months of advance warning of a
   glut or shortfall.
3. **Dated MSP and export-policy changes** — onion export bans move prices within
   days and are invisible here.
4. **Cold-storage capacity by district** — determines whether holding is possible.
5. **Transport cost** — turns the gross ₹756/quintal market premium into a net one.
6. **More years** — 5–7 would separate the seasonal pattern from unusual years.

## How this should be used

**Appropriate:** planning a typical selling window (Sep–Nov); comparing markets and
varieties on their usual level; a next-month price *range* per market.
**Not appropriate:** predicting next week's price; calling the top of an active
shock; any use where the farmer cannot absorb being wrong by ₹150–400/quintal.

**One line for a field agent:** *In a normal month the next-month price is within
about ₹170/quintal (14%), and the pattern says sell Sep–Nov, prefer the Nashik
belt, and Red onion pays a premium. In a shock year every number here is too low,
never too high.*
