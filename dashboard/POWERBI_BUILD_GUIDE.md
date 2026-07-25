# Power BI Build Guide — Mandi Price Watch

Build order for someone who has not used Power BI before. Roughly 2–3 hours
end to end. Each visual maps to a question from `DASHBOARD_BRIEF.md`.

**Audience:** DeHaat field agents, reading this on a phone in front of a
farmer. Every design choice below serves that, not visual density.

---

## 0. Before you start — resolve publishing

Power BI Desktop is free; **publishing publicly is not automatic**.
"Publish to web" requires a Fabric/Pro tenant. The capstone requires a link
that opens in an incognito window.

Test this **first**, not the night before:

1. Install Power BI Desktop (free, Microsoft Store or the download page).
2. Sign in with your **IIT Mandi account**, not a personal Microsoft one.
   Institutional accounts frequently have Fabric via Microsoft's education
   programme.
3. Publish anything trivial → in the Power BI Service, `File → Embed report →
   Publish to web (public)`.

If that option is greyed out, you have no public-link path. Fallback:

- Commit the `.pbix` to the Drive folder
- Export `File → Export → PDF` and include it
- Screenshot every page into `dashboard/screenshots/`
- **Tell your instructor why** — a missing public link is a Solid-baseline
  failure unless it is explained

---

## 1. Load the data

`Home → Get data → Text/CSV`, load all **seven** from `dashboard/data/`:

| File | Rows | Purpose |
|---|---|---|
| `fact_daily_prices.csv` | 8,114 | Base grain, one row per mandi-day (curated) |
| `seasonal_by_mandi.csv` | 168 | Mandi × month aggregates |
| `market_summary.csv` | 14 | One row per curated market |
| `recommendation.csv` | 168 | The decision layer (SELL / HOLD) |
| `model_coefficients.csv` | 26 | OLS month & market terms in rupees |
| `variety_by_month.csv` | 37 | **Which onion variety pays best, by month** |
| `forecast_next_month.csv` | 14 | **Next-month price forecast + range, per market** |

In the preview click **Transform Data**, confirm types, then **Close & Apply**:

- `price_date` → Date
- `modal_price`, `avg_modal_price`, `arrivals`, `seasonal_index` → Decimal Number
- `month_num`, `observations`, `month_rank` → Whole Number
- `mandi_name`, `month_name`, `recommendation` → Text

---

## 2. Fix month sorting — do this before any visual

**The single most common Power BI mistake.** Without this, every month axis
sorts alphabetically: Apr, Aug, Dec, Feb, Jan...

For **each** table containing `month_name`:

1. Data view → select the `month_name` column
2. `Column tools → Sort by Column → month_num`

Both columns are already in every extract for this purpose. Do it now — a
dashboard with alphabetical months looks broken to a reviewer regardless of
how good the analysis underneath is.

---

## 3. Relationships

`Model view`. Power BI will auto-detect some; verify and fix:

```
market_summary[mandi_id]  1 --- *  fact_daily_prices[mandi_id]
market_summary[mandi_id]  1 --- *  seasonal_by_mandi[mandi_id]
market_summary[mandi_id]  1 --- *  recommendation[mandi_id]
```

`market_summary` is the dimension (14 curated mandis), so it is the **one**
side. All cross-filter directions **Single**, from dimension to fact.

Delete any auto-detected relationship on `month_name` or `month_num` — those
create ambiguous paths and produce wrong totals.

`model_coefficients` stays **unrelated**. It is a reference table for one
visual, and joining it would fan out the fact rows.

---

## 4. Page 1 — "When and where should this farmer sell?"

The whole point. A field agent should answer the question without scrolling.

### 4.1 Header cards (top row)

Three `Card` visuals:

| Card | Field | Format |
|---|---|---|
| Best month | `recommendation[best_month]` (First) | Title: "Best month to sell" |
| Peak price | `recommendation[best_month_price]` (Max) | ₹, 0 decimals |
| Gain vs worst month | `seasonal_by_mandi[rs_above_worst_month]` (Max) | ₹, 0 decimals |

### 4.2 Seasonal price curve — the primary visual

`Line chart`:
- X-axis: `seasonal_by_mandi[month_name]` (sorted by `month_num` per §2)
- Y-axis: `avg_modal_price` (Average)
- Legend: `mandi_name`
- Format → Data colors → set all 14 to light grey, then set **Lasalgaon** and
  **Pune** to a strong colour. Fourteen coloured lines is noise; two highlighted
  against the rest makes a point.

Title: **"Onion prices peak in September–November in every market"**

Titles should state the finding, not name the chart. "Average Price by Month"
tells a reader nothing they cannot see.

### 4.3 Recommendation matrix — the decision layer

`Matrix`:
- Rows: `recommendation[mandi_name]`
- Columns: `recommendation[month_name]`
- Values: `recommendation[recommendation]` (First)

Conditional formatting → Background colour → Format by **Rules** on
`seasonal_index`:

| Rule | Colour | Meaning |
|---|---|---|
| ≥ 115 | Green | SELL NOW |
| 100–115 | Light green | GOOD TO SELL |
| 85–100 | Amber | HOLD IF YOU CAN |
| < 85 | Grey | STORE OR HOLD |

Do **not** use red for the low months. Red reads as "error"; those months are
normal, just cheap. Grey reads as "not now", which is the actual message.

Title: **"September–November is the selling window in all 14 markets"**

### 4.4 Market comparison

`Bar chart` (horizontal):
- Y-axis: `market_summary[mandi_name]`
- X-axis: `avg_modal_price`
- Sort descending

Add `Analytics → Average line` at the state mean, labelled.

Title: **"Lasalgaon pays ₹756/quintal more than Sambhajinagar — but timing is worth ~2× that"**

That framing is the honest one. Without it, a reader over-weights market
choice, which the data does not support.

### 4.5 Slicers

Two only:
- `mandi_name` (dropdown)
- `month_name` (dropdown)

Resist adding more. A field agent using this on a phone needs two controls,
not seven.

---

## 5. Page 2 — Evidence and honesty

Reviewers weight this. It is where a Solid dashboard becomes a Strong one.

### 5.1 Arrivals vs price

`Scatter chart`:
- X: `fact_daily_prices[arrivals]` (Average)
- Y: `fact_daily_prices[modal_price]` (Average)
- Details: `month_name`
- Play axis: leave empty

Title: **"A single market's own arrivals barely move its price (r ≈ −0.03)"**

### 5.2 Month effects from the model

`Bar chart`:
- Filter `model_coefficients[kind]` = `month`
- X: `label` (sorted by `sort_order`)
- Y: `rs_vs_baseline`

Title: **"November is worth about ₹1,500/quintal more than May, holding market
constant"**

### 5.3 Model accuracy — state it, do not hide it

`Card` visuals or a text box:

- Next-month forecast error (walk-forward): **≈ ₹168/quintal, 13.9%**
- The ML forecaster **ties** a naive "next ≈ this month" baseline; its extra
  value is the **prediction interval**, not higher point accuracy
- Every model **under-predicts shock months** — the error runs one way

Add a text box, verbatim:

> This model describes a typical month. It cannot see weather, MSP
> announcements, or export policy — the causes of the 2024 and 2025 price
> spikes to ₹25,000/quintal. In a shock month the real price will be **higher**
> than shown here, not lower.

Putting your model's weakness on the dashboard is not a weakness in the
submission. It is the difference between a chart and an analysis.

### 5.4 Data coverage

`Table`: `mandi_name`, `reporting_days`, `pct_coverage`, `first_report`,
`last_report` from `market_summary`.

Title: **"76% of possible mandi-days reported; gaps left unfilled rather than
interpolated"**

---

## 6. Formatting pass

- **Theme:** `View → Themes → Executive`, or a custom one. Anything but the
  default.
- **Font:** Segoe UI 10pt minimum. This gets read on a phone.
- **Currency:** every price field `₹ #,0` — no decimals. Nobody quotes
  ₹1,503.47/quintal.
- **Alignment:** `Format → Align` on selected visuals. Misaligned edges are
  the fastest way to look unfinished.
- **Page size:** `Format page → 16:9`. Set it before positioning anything.

---

## 7. Publish and verify

1. `File → Publish → Publish to Power BI`
2. In the Service: `File → Embed report → Publish to web (public)`
3. Copy the link
4. **Open it in an incognito window where you are not signed in**
5. Confirm both pages render and slicers work

Step 4 is not optional. The submission checklist requires it, and a link that
works only for you is the most common way this deliverable fails.

Then:
- Put the link in your README
- Screenshot both pages into `dashboard/screenshots/`
- Commit the `.pbix` to the Drive folder

---

## 8. Self-check against the rubric

| Level | Requirement | Met when |
|---|---|---|
| Solid | Published, shows seasonal patterns and market comparisons | §4.2 + §4.4 done, public link verified |
| Strong | Built around the advisory team's questions, in their language | §4.3 matrix answers "when and where" in words, not indices |
| Standout | A field agent could answer at a glance | Page 1 needs no scrolling; §5.3 states the uncertainty honestly |

The gap between Strong and Standout here is almost entirely §5.3. Most
submissions present a model as if it were right. Stating where yours breaks,
on the dashboard, is what reads as an analyst rather than a student.

---

## 9. Page 3 — "Which variety pays best?" (new)

Source: `variety_by_month.csv` (grain: variety × month).

**9.1 Variety price ranking (card + bar).**
- A **clustered column chart**: Axis = `month_name` (sorted by `month_num`),
  Legend = `variety_group`, Values = `avg_modal_price`. Reads at a glance as
  "Red sits above Local and Unhali in every month."
- A **card** showing the top variety overall: filter to the max of a
  `variety` measure, or just annotate: *"Red onion averages ₹2,231/qtl — about
  31% above Local."*

**9.2 Premium table.**
- A **matrix**: Rows = `variety_group`, Columns = `month_name`, Values =
  `pct_vs_month_avg`. Conditional-format the cells (green = premium, red =
  discount). This is the "which category, which month" answer in one visual.
- Add `evidence` as a tooltip so a thin variety-month (grey) is not over-read.

**Field-agent takeaway to put on the page:** *"Grow Red where agronomy allows —
it earns a premium in every month, independent of when and where you sell."*

---

## 10. Page 4 — "What will next month cost?" (new, the forecast)

Source: `forecast_next_month.csv` (grain: one row per curated market).

**10.1 Headline card.**
- Card visual: `forecast_price` filtered to `rank_next_month = 1`, titled with
  `target_month_name`. Reads: *"Best market next month (Jul 2026): Pimpalgaon
  Baswant, ~₹1,788/qtl."*

**10.2 Ranked forecast with uncertainty (the core visual).**
- A **bar chart**: Axis = `mandi_name` sorted by `forecast_price` descending,
  Value = `forecast_price`.
- Add the **range as error bars**: `Analytics → Error bars` (or an overlaid
  `forecast_low`/`forecast_high` as a shaded column). *Never* show the point
  without the band — the whole honesty of the forecast is the interval.
- Colour the bar by `vs_last_month_pct` (diverging) so a rising vs falling
  market is obvious.

**10.3 Accuracy disclosure (do not hide it).**
- A text box: *"Backtested error ≈ ₹168/quintal (14%). The forecast assumes no
  supply shock; in a shock month the real price will be higher, never lower."*
  Pull the number from `recommendation.csv`'s `forecast_mape_pct` column so it
  updates on a re-run rather than being typed by hand.

**10.4 Interpretability tooltip.**
- Add a small "what drives this" note referencing
  `outputs/figures/fc2_feature_importance.png`: *"Driven mostly by last month's
  price and the seasonal month effect."* This turns the model from a black box
  into something a field agent can defend.

**Design rule for this page:** the forecast is a *planning aid with a band*, not a
promise. If a viewer can screenshot a single number with no interval, redesign the
visual.
