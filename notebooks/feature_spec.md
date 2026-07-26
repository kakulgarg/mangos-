# Feature Specification

Every feature in both models, and the EDA finding that put it there. Written from
the exploration on the **real** Agmarknet data, not reverse-engineered from a
result.

---

## The decision the EDA forced

The intended explanatory model was the obvious one:

```
price ~ arrivals + month + mandi
```

**On the real data, arrivals turns out to carry almost no independent signal.**
This is the single most important EDA finding, and it is the *opposite* of what
the synthetic scaffold data suggested.

### What F2–F4 found (real data)

| | Real Agmarknet | Synthetic scaffold (discarded) |
|---|---|---|
| Pooled corr(arrivals, price) | **−0.03** | −0.72 |
| Within-month mean corr | **+0.07** | +0.34 |
| Month → arrivals R² | **2.7%** | 77.7% |
| VIF of raw arrivals | **1.03** | 5.7 |

On real data there is **no Simpson's paradox and no collinearity problem** — just
a weak predictor. A single mandi's daily arrivals barely move its modal price
because the price is set by state/national supply and the reference market
(Lasalgaon), not by one market's truck count that day.

### Consequence for the explanatory model

Arrivals is kept only as `arrivals_dev` (deviation from the month's mean) so its
small effect is at least interpretable and free of the month confound, but it is
reported as **economically negligible** (−0.036 ₹/qtl; ₹36 per 1,000 quintals
against a ₹1,500 seasonal swing). The model is carried by **month** and **mandi**.

---

## Explanatory model — final feature set

| Feature | Type | Justified by | Reasoning |
|---|---|---|---|
| `month` | categorical (12) | **F1** | Price swings **2.5×** between May (₹992) and November (₹2,495). Season is the dominant driver. Categorical because the curve is not monotonic. |
| `mandi` | categorical (14) | **F5** | Markets differ in *level* by **₹756/qtl** (43%: Chh. Sambhajinagar → Lasalgaon) but share seasonal *timing*, so mandi enters as a level shift, no month×mandi interaction. |
| `arrivals_dev` | continuous | **F2–F4** | Weak but interpretable; the non-seasonal part of arrivals. VIF 1.03. |

**Deliberately excluded:** raw `arrivals` (redundant with `arrivals_dev`),
`month×mandi` (curves are parallel; 130+ parameters to fit noise), `year` (only
2 full years; would fit shocks as a trend), `week_of_year` (52 buckets over 24
months), lagged prices (belong in the forecaster, not the explanatory model).

---

## Forecaster — feature set (monthly, per mandi)

The forecaster's job is different: predict next month, where **persistence is the
signal**. Features are all knowable at decision time (lagged), never
contemporaneous — a farmer deciding in June does not know July's arrivals.

| Feature | Why |
|---|---|
| `lag1`, `lag2`, `lag3` | recent price level and short-run momentum (monthly autocorr 0.86) |
| `lag12` | same month last year — the seasonal anchor |
| `roll3` | 3-month trailing mean — a smoother level |
| `mom_change` | last month's month-over-month change — momentum |
| `arr_lag1` | last month's arrivals — the only supply term available in advance |
| `month_sin`, `month_cos` | cyclical seasonality in 2 parameters, not 11 |
| `mandi_code` | market identity (level differences) |

**Target: the month-over-month change**, not the level. Trees cannot extrapolate
above their training range, so a level target under-predicts shock months;
predicting the change and adding it to last month fixes this (see model card B).

**Deliberately excluded:** contemporaneous arrivals or price (leakage — unknown at
decision time), daily features (the decision is monthly), calendar year (too few).

---

## What this feature set structurally cannot do (F6)

The 2024–25 shock episodes reach **₹25,000/quintal** with **no corresponding
variable in the dataset** — no weather, no MSP, no export policy, no acreage. Both
models therefore describe the *typical* pattern but under-predict exactly the weeks
that pay most. This is a missing-data problem, carried into the model card as the
core of the failure analysis rather than treated as a defect to minimise.
