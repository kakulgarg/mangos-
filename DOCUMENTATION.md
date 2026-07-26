# Onion Market Intelligence — Full Project Documentation

*A complete, detailed guide to the Mandi Price Watch project: what it does, the
idea behind it, the technology, how to run it, and how every part works.*

> This is the **deep reference**. For a one-page overview, see `README.md`.
> This document is written to be **balanced** — clear enough for a non-technical
> reader, but complete enough for an engineer or evaluator.

---

## Table of contents

1. [What this project is](#1-what-this-project-is)
2. [The real-world problem](#2-the-real-world-problem)
3. [The core idea — how we help a farmer make maximum profit](#3-the-core-idea)
4. [The technology stack (and why each piece)](#4-the-technology-stack)
5. [System architecture and data flow](#5-system-architecture-and-data-flow)
6. [Repository structure](#6-repository-structure)
7. [How to run the project (step by step)](#7-how-to-run-the-project)
8. [The web dashboard explained](#8-the-web-dashboard-explained)
9. [The Profit Calculator — the maths of maximum profit](#9-the-profit-calculator)
10. [The machine-learning models explained](#10-the-machine-learning-models)
11. [The data](#11-the-data)
12. [Key findings](#12-key-findings)
13. [Honesty, assumptions and limitations](#13-honesty-assumptions-and-limitations)
14. [How to extend the project](#14-how-to-extend-the-project)
15. [Credits](#15-credits)

---

## 1. What this project is

**Onion Market Intelligence** (a.k.a. *Mandi Price Watch*) is a data-science
project that takes two years of real government onion-price data from markets
("mandis") across Maharashtra and turns it into **clear, money-focused advice for
farmers**:

- **When** should I sell? (which month pays the most)
- **Where** should I sell? (which mandi pays the most)
- **Which** onion variety earns the most?
- **What will the price be next month?** (a forecast)
- **After transport and all costs, which mandi actually leaves me the most
  money?** (a profit calculator)

The final output is an **interactive dashboard** a field agent can open on a
laptop or phone, plus a full analysis pipeline, statistical models, and
documents suitable for academic evaluation.

It was built as a one-month capstone for the **IIT Mandi CCE AI & Data Science
Program** (Project #5).

---

## 2. The real-world problem

Onion is one of India's most **price-volatile** crops. The same sack of onions
can sell for ₹1,000 in one month and ₹2,500 a few months later. A farmer who
sells at the wrong time — or in the wrong market — can lose a large part of their
income, not because of a bad crop, but purely because of **timing, location, and
market choice**.

The company in the scenario, **DeHaat**, runs an advisory service. Their field
agents get asked the same questions every season, and today the answers are
mostly guesswork. This project replaces guesswork with **evidence from real
data**.

---

## 3. The core idea

### The concept in one line

> Break the "how do I earn the most from my onions?" question into **four levers
> a farmer can actually pull**, measure each one with real data, and then combine
> them into a single **net-profit** recommendation.

### The four profit levers

| Lever | Question | How we measure it |
|---|---|---|
| **1. Timing** | Which month pays most? | Seasonal analysis of 2 years of prices |
| **2. Location** | Which mandi pays most? | Average price per market |
| **3. Variety** | Which onion type pays most? | Price by variety (Red, Local, White, Unhali) |
| **4. Logistics** | After transport & costs, what's left? | The Profit Calculator |

### Why this makes maximum profit (the key insight)

The most important idea in the project is that **the highest *price* is not the
same as the highest *profit*.**

A far-away mandi may show a higher price, but once you subtract the cost of
transporting the onions there (plus the mandi's commission and labour), a
**closer mandi paying slightly less can leave more money in your pocket.**

So the project's "profit engine" works like this:

```
Take-home profit  =  (price at the mandi × quantity)
                     − transport cost   (distance × rate)
                     − mandi commission (a % of the sale)
                     − loading / labour cost
```

We calculate this for **every mandi**, then **rank them by take-home profit** and
recommend the winner. That is how the project turns raw prices into a genuine
*maximum-profit* decision — it accounts for the money that leaves the farmer's
hand, not just the money that comes in.

Layered on top of the four levers is a **price forecast** (what next month is
likely to bring) so the advice is forward-looking, not just historical.

---

## 4. The technology stack

Think of it like a kitchen: raw ingredients come in, pass through stations, and a
finished dish comes out.

| Stage | Tool | Why we use it (plain words) |
|---|---|---|
| **Language** | **Python 3.10–3.13** | The glue for all data work — clean, readable, huge ecosystem. |
| **Data wrangling** | **pandas**, **NumPy** | Load, clean, reshape and compute on tabular data. The "prep station". |
| **Database** | **SQLite** | A tiny, file-based database. Stores the cleaned data so we can query it with SQL. No server needed. |
| **Querying** | **SQL** | Standard language to ask the data questions ("average price per mandi per month"). |
| **Statistics / explain** | **statsmodels** | Fits the regression model that measures how much each month and market is worth, in rupees, with confidence ranges. |
| **Machine learning / forecast** | **LightGBM**, **scikit-learn** | Gradient-boosted trees that learn patterns from past prices to forecast next month. |
| **Charts (analysis)** | **Matplotlib** | Generates the static analysis figures (seasonal curve, model diagnostics, etc.). |
| **Reports (PDF)** | **ReportLab** | Renders the decision memo into a professional PDF. |
| **Testing** | **pytest** | Automated tests that catch mistakes (data parsing, leakage, etc.). |
| **Version control** | **Git** | Tracks every change — a logbook of the project's history. |
| **Web dashboard** | **HTML, CSS, JavaScript** + **Chart.js** | The interactive dashboard the farmer/agent actually uses. Runs in any browser, offline. |
| **BI option** | **Power BI** | An alternative dashboard built from the same exported data (for submission requirements). |

**Design principle:** everything is **reproducible** and **configuration-driven**
— one command rebuilds the whole project from raw files, and the scope (commodity,
state, markets, dates) lives in a single config file.

---

## 5. System architecture and data flow

The project is a **pipeline** — a chain of small programs where each one hands
its output to the next.

```
25 Agmarknet CSV exports (raw government data)
        │
        ▼  parse_agmarknet.py   → clean flat table (keeps variety, converts
        │                          tonnes→quintals, fixes market names)
        ▼  load_db.py           → SQLite database (data "as sourced")
        ▼  clean.py             → cleaned tables (duplicates, gaps, outliers,
        │                          all decisions logged)
        ├─► run_sql.py          → 7 analytical SQL queries → result CSVs
        ├─► eda.py              → 6 exploration charts + findings
        ├─► model.py            → explanatory model (month & market effects)
        ├─► forecast.py         → next-month price forecaster
        ▼  build_extracts.py    → 7 clean CSVs for dashboards
        ├─► build_dashboard_html.py → interactive web dashboard (HTML)
        └─► (Power BI reads the same 7 CSVs)
```

**One command runs all of it:** `python run_pipeline.py` (about 20 seconds).

Every number on the dashboard, in the figures, and in the documents is
**regenerated from the raw data** — nothing is typed by hand. Re-run the pipeline
and everything updates together.

---

## 6. Repository structure

```
DeHaat_Mandi_Price_Watch/
├── data/
│   ├── 01_source/       Raw Agmarknet exports (25 CSVs) — never edited
│   ├── 02_interim/      Parsed flat tables + coverage table
│   └── 03_processed/    SQLite database + cleaned CSVs
├── sql/
│   ├── schema.sql       Database table definitions
│   └── analysis.sql     7 analytical queries (incl. variety)
├── src/                 All the Python code
│   ├── config.py            Central settings (scope lives here)
│   ├── logging_config.py    Shared logging setup
│   ├── parse_agmarknet.py   Step 0 — parse raw exports
│   ├── load_db.py           Step 1 — load into SQLite
│   ├── clean.py             Step 3 — clean + feature engineer
│   ├── run_sql.py           Step 2 — run analytical SQL
│   ├── eda.py               Step 4 — exploration charts
│   ├── model.py             Step 5 — explanatory model
│   ├── forecast.py          Step 6 — next-month forecaster
│   ├── build_extracts.py    Step 7 — dashboard CSVs
│   ├── build_dashboard_html.py  Step 8 — web dashboard
│   ├── make_memo_pdf.py     Renders the decision memo PDF
│   └── run_pipeline.py      Runs all steps in order
├── tests/               pytest test suite
├── notebooks/           Reconciliation log, data-quality note, feature spec, model card
├── outputs/             Query results, 12 figures, model + forecast artefacts (JSON/CSV)
├── dashboard/
│   ├── data/            7 CSV extracts (feed both dashboards)
│   ├── mandi_dashboard.html   The interactive web dashboard
│   ├── onion_theme.json       Power BI colour theme
│   └── POWERBI_BUILD_GUIDE.md Step-by-step Power BI instructions
├── memo/                One-page decision memo (Markdown + PDF)
├── ai_appendix/         AI workflow appendix (how AI was used + its errors)
├── requirements.txt     Python dependencies
├── README.md            One-page overview
└── DOCUMENTATION.md     ← you are here
```

---

## 7. How to run the project

### Prerequisites

- **Python 3.10, 3.11, 3.12, or 3.13** installed.
- A terminal (Command Prompt / PowerShell on Windows, Terminal on Mac/Linux).

### Step 1 — Set up a clean environment

From the project's root folder:

```bash
# create an isolated environment
python -m venv .venv

# activate it
.venv\Scripts\activate        # Windows (PowerShell / CMD)
# source .venv/bin/activate   # Mac / Linux  (use only ONE of these lines)

# install all dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

*If pip complains about a package version, open `requirements.txt` and change
that line's `==` to `>=`, then re-run. The pinned versions are what we tested;
slightly newer ones are fine.*

### Step 2 — Run the whole pipeline

```bash
cd src
python run_pipeline.py
```

**What you'll see:** eight steps logged in order, finishing in about 20 seconds:

```
>>> Parse Agmarknet exports -> interim tables
>>> Load interim tables -> SQLite (as sourced)
>>> Clean + feature-engineer -> clean tables + audit
>>> Run analytical SQL -> query CSVs
>>> Exploration -> 6 figures + findings
>>> Explanatory OLS -> coefficients + diagnostics
>>> Monthly forecaster -> next-month CSV + backtest
>>> Dashboard extracts -> dashboard/data
>>> Interactive web dashboard -> dashboard/mandi_dashboard.html
Pipeline complete in ~20s.
```

### Step 3 — Run the tests (optional but recommended)

```bash
# from the src folder
python -m pytest ../tests -q
```

Expected: `9 passed`.

### Step 4 — Open the dashboard

Double-click **`dashboard/mandi_dashboard.html`** — it opens in any browser, no
server needed.

### Running individual steps

You can run any step on its own from the `src/` folder, or resume from the
middle:

```bash
python parse_agmarknet.py     # just parse
python forecast.py            # just the forecaster
python run_pipeline.py --from forecast   # resume from forecasting onward
```

### Refreshing after new data

Drop new monthly Agmarknet exports into `data/01_source/`, then run
`python run_pipeline.py` again. Every figure, table, and both dashboards update
automatically.

---

## 8. The web dashboard explained

Open `dashboard/mandi_dashboard.html`. It has a sidebar with five pages:

1. **Overview (When & Where)** — an executive summary, key numbers, the seasonal
   price curve, a market ranking, and a colour-coded "advice grid" (SELL / GOOD /
   HOLD / STORE for every market and month).
2. **Variety** — which onion type pays best, month by month.
3. **Forecast** — next month's predicted price for each market, with an
   uncertainty band.
4. **Profit Calculator** — the interactive tool (see next section).
5. **Evidence** — the statistical month-effects chart, a data-coverage table, and
   an honest list of the project's limitations.

The whole page is **generated from the model's output** by
`build_dashboard_html.py`, so it always matches the latest data.

---

## 9. The Profit Calculator

This is the project's standout feature — the part that turns analysis into a real
**maximum-profit** decision.

### What the farmer enters

- **Location** (their district / nearest town)
- **Quantity** (in quintals)
- **Variety** (Red, Local, White, Unhali, Other)
- *(Optional)* transport rate, labour cost, mandi commission — if left blank,
  sensible **defaults** are used.

### What it does

1. **Distance:** it knows the coordinates of all 14 markets, so it calculates the
   distance from the farmer's location to each mandi automatically (straight-line
   distance × 1.3 to approximate road distance).
2. **Price:** it takes each mandi's expected price and adjusts it for the chosen
   variety (e.g. Red onion carries a premium).
3. **Net profit:** for every mandi it computes:

   ```
   net price per quintal = price
                          − (distance × transport rate)
                          − (commission % × price)
                          − labour per quintal

   take-home = net price per quintal × quantity
   ```

4. **Ranking:** it sorts all mandis by take-home profit and shows the **winner**,
   a **cost-breakdown chart** ("where your money goes"), and a full ranked table.
   Very long hauls (>300 km) are flagged with ⚠.

### Why this is honest

The transport rate, commission and labour are **assumptions the farmer can
adjust** — they are clearly labelled on screen, and the result is described as a
**net *estimate*, not a guarantee**. This is the honest way to add logistics when
the dataset itself contains no transport cost.

### A note on "why the calculator's top mandi can differ from the Where page"

The **Where to sell** page ranks markets by their **2-year average price**, while
the **calculator** uses each market's **next-month forecast price** (a
forward-looking number). Because the Nashik-belt markets are clustered close
together, distance barely separates them, so the calculator tends to pick the one
with the highest *forecast*. Both views are valid — one looks at the past, one at
the future.

---

## 10. The machine-learning models

The project deliberately uses **two models**, each with a clear job.

### Model A — the explanatory model (the "why")

- **Type:** Ordinary Least Squares (OLS) linear regression.
- **What it answers:** *how much is each month and each market worth, in rupees?*
- **How it's read:** e.g. "November is worth about ₹759/quintal more than
  January," with a confidence range and a note on whether it's statistically
  significant.
- **Honesty:** it explains only ~25% of daily price swings — because daily onion
  prices are extremely noisy. That's expected, and it's exactly why a separate
  forecasting model is needed. It uses **robust (HAC) standard errors** because
  daily prices are correlated over time.

### Model B — the forecaster (the "what next month")

- **Grain:** monthly, per mandi (a farmer decides monthly, not daily).
- **Models compared (a "baseline ladder"):**
  1. **Persistence** — "next month ≈ this month" (a surprisingly strong baseline).
  2. **Seasonal-naive** — "next month ≈ same month last year".
  3. **LightGBM** — gradient-boosted trees on lag features (last month, last 3
     months, same month last year, momentum, etc.).
  4. **Hybrid ensemble** — a blend of persistence + LightGBM (the final choice).
- **Evaluation:** *walk-forward backtesting* — train on the past, predict the
  next month, roll forward. This never lets the model see the future.
- **Result:** the ensemble scores about **₹168/quintal (14%) mean error**, and it
  provides a **prediction interval** (a "likely range") — its real advantage over
  the naive baseline.

**Honest finding:** the fancy ML model only *ties* the simple persistence
baseline on accuracy, because monthly onion prices behave almost like a random
walk. We report this openly. The ensemble's value is the uncertainty band, not a
dramatic accuracy gain.

---

## 11. The data

| | |
|---|---|
| **Source** | Agmarknet (Government of India) — `agmarknet.gov.in` |
| **What** | "Date Wise Prices for Specified Commodity", 25 monthly CSV exports |
| **Commodity** | Onion (varieties: Red, Local, White, Unhali, + Other) |
| **Geography** | 111 markets loaded; **14 curated** high-coverage markets used for advice |
| **Period** | June 2024 – June 2026 (24 months; **August 2024 is missing** from the source) |
| **Size** | 31,930 cleaned variety-day rows → 8,114 curated mandi-days |
| **Price used** | Modal price (₹/quintal) — the price the most volume traded at |
| **Units** | Arrivals converted from tonnes → quintals (×10) so everything is per-quintal |

The raw data is messy in real ways — market names appear as headings not columns,
units differ, one month was downloaded twice. All of this is handled and
**documented** in `notebooks/data_quality_note.md` and
`notebooks/reconciliation_log.md`.

---

## 12. Key findings

- **Timing dominates.** Prices peak **September–November** and bottom out in
  **April–May** — a swing of about **₹1,500/quintal** (roughly 2.5×). *When* you
  sell is the biggest lever.
- **Location matters, about half as much.** The **Nashik belt** (Lasalgaon,
  Pimpalgaon) pays around **₹750/quintal more** than the cheapest market
  (Chh. Sambhajinagar) — before transport.
- **Variety matters too.** **Red onion** earns roughly **31% more** than Local.
- **Next month is broadly predictable in level** (~14% error) but **shocks are
  not** — the model can't foresee a price spike caused by weather or policy.

---

## 13. Honesty, assumptions and limitations

This project treats honesty as a feature, not an afterthought:

1. **Only 2 years of data**, and **August 2024 is missing** — each calendar month
   is observed only ~2 times, so the seasonal peak rests on few observations.
   *This is the single biggest limitation.*
2. **A market's own daily arrivals barely predict its price** (correlation ≈
   −0.03). Price is set by state/national supply, not one market's trucks. (An
   earlier "Simpson's paradox" finding from placeholder data **did not survive**
   contact with the real data — and we reported that.)
3. **The ML forecaster only ties a naive baseline** — reported openly.
4. **No weather, MSP, or export-policy data** — so no model here can foresee a
   supply shock. In a shock month the real price will be **higher** than
   predicted, never lower.
5. **The Profit Calculator's transport, commission and labour are assumptions**
   the farmer adjusts — a net *estimate*, not a guarantee.

---

## 14. How to extend the project

Because scope lives in `src/config.py`, the project is easy to extend:

- **Add more data:** drop new monthly exports into `data/01_source/` and re-run.
- **Change the crop/state:** edit `COMMODITY`, `STATE`, `CURATED_MANDIS`,
  `DATE_START/END` in `config.py` — no query or script hardcodes these.
- **Highest-value next step:** join **IMD district rainfall** — the direct driver
  of the supply shocks the model currently can't see. This is the one addition
  that could turn the forecaster from "ties the baseline" into a real predictive
  win.
- **Other ideas:** a geographic map of mandis, a quantile "how high could it go"
  forecast, and real road-distance via a maps API for the calculator.

---

## 15. Credits

- **Data:** Agmarknet, Directorate of Marketing & Inspection, Government of India.
- **Built for:** IIT Mandi CCE — AI & Data Science Program capstone (Project #5).
- **Stack:** Python, pandas, NumPy, SQLite/SQL, statsmodels, LightGBM,
  scikit-learn, Matplotlib, ReportLab, pytest, Git, HTML/CSS/JavaScript +
  Chart.js, Power BI.

*All figures are estimates for advisory use, not financial guarantees. Prices are
gross unless netted in the Profit Calculator. The full pipeline is reproducible
with a single command.*
