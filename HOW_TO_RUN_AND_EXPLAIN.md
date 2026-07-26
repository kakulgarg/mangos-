# How to Run It, Connect Power BI, and Explain It

Three parts:
- **Part A** — run the project locally in VS Code, and what to expect.
- **Part B** — connect the output to Power BI.
- **Part C** — the simple "tech stack" story to tell friends.

---

# PART A — Run it locally in VS Code

## A1. One-time setup

You need **Python 3.10, 3.11, or 3.12** installed. Check in a terminal:

```bash
python --version
```

Open the project folder in VS Code (`File → Open Folder →` the
`DeHaat_Mandi_Price_Watch` folder). Then open a terminal in VS Code
(`Terminal → New Terminal`) and create a clean environment:

```bash
# from the project root folder
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Mac/Linux:
source .venv/bin/activate

# install everything the project needs
pip install -r requirements.txt
```

> If `pip install` complains about an exact version, open `requirements.txt`
> and change that line's `==` to `>=`, then run it again. The pinned versions
> are what I tested with; slightly newer ones are fine.

## A2. Run the whole pipeline (the main command)

```bash
cd src
python run_pipeline.py
```

**What to expect:** it prints a log line for each of the 8 steps and finishes in
about 20 seconds. You should see something like:

```
>>> Parse Agmarknet exports -> interim tables
<<< parse_agmarknet done in 1.9s
>>> Load interim tables -> SQLite (as sourced)
<<< load_db done in 0.3s
>>> Clean + feature-engineer -> clean tables + audit
<<< clean done in 13.4s
>>> Run analytical SQL -> query CSVs
>>> Exploration -> 6 figures + findings
>>> Explanatory OLS -> coefficients + diagnostics
>>> Monthly forecaster -> next-month CSV + backtest
    Best market next month: Pimpalgaon Baswant APMC at ~Rs 1788/qtl (range 1555-1884)
>>> Dashboard extracts -> dashboard/data
Pipeline complete in ~20s.
```

**Note:** locally you do **NOT** need to set any `MANDI_DB` environment variable.
The database is created automatically at `data/03_processed/mandi.db`.

## A3. What you get after running (where the outputs are)

| Folder | What's inside |
|---|---|
| `outputs/figures/` | 12 charts (`.png`) — seasonal curve, model comparison, forecast, etc. |
| `outputs/` | `model_results.json`, `forecast_results.json`, query result CSVs |
| `dashboard/data/` | **7 CSV files — these are what Power BI reads** |
| `data/03_processed/` | the SQLite database + cleaned data |

## A4. Run the tests (optional, but good to show)

```bash
# from the src folder
python -m pytest ../tests -q
```

**Expect:** `9 passed in ~2s`.

## A5. Run one step at a time (optional)

If you want to see each stage on its own, run them in this order from `src/`:

```bash
python parse_agmarknet.py    # read + clean the raw files
python load_db.py            # put data into the database
python clean.py              # clean + add features
python run_sql.py            # run the 7 SQL queries
python eda.py                # make the exploration charts
python model.py              # the "why" model (month/market effects)
python forecast.py           # the next-month price forecaster
python build_extracts.py     # make the 7 CSVs for Power BI
python make_memo_pdf.py      # rebuild the memo PDF
```

Or resume from the middle: `python run_pipeline.py --from forecast`.

---

# PART B — Connect it to Power BI

The link between the code and Power BI is simple: **the code writes 7 CSV files
into `dashboard/data/`, and Power BI reads those files.** That's the whole
connection. There is no live database link — CSV is the handoff.

## B1. Load the data (easiest way — load the whole folder)

1. Open **Power BI Desktop** (free from the Microsoft Store).
2. `Home → Get data → More → Folder → Connect`.
3. Browse to your `dashboard/data` folder → `OK`.
4. In the window that appears, click **Combine → Combine & Load**, *or* just
   load them one by one with `Get data → Text/CSV` (7 files):
   - `fact_daily_prices.csv`
   - `seasonal_by_mandi.csv`
   - `market_summary.csv`
   - `recommendation.csv`
   - `model_coefficients.csv`
   - `variety_by_month.csv`  *(which variety pays best)*
   - `forecast_next_month.csv`  *(next-month price forecast)*

## B2. Build the visuals

Follow the step-by-step guide already in the repo:
**`dashboard/POWERBI_BUILD_GUIDE.md`** — it tells you exactly which chart to make
on each page (when to sell, where to sell, which variety, next-month forecast),
including the one setting beginners always miss (sorting months correctly).

## B3. Refreshing after you re-run the code

This is the nice part. Whenever you re-run `python run_pipeline.py`, the CSVs in
`dashboard/data/` are overwritten with fresh numbers. In Power BI, just click
**`Home → Refresh`** and every chart updates. No rebuilding.

> So the workflow is: **run the code → CSVs update → click Refresh in Power BI.**

## B4. Publishing (so you can submit a public link)

`File → Publish → Publish to Power BI` (needs your IIT Mandi Microsoft account),
then in the web service `File → Embed report → Publish to web (public)`. If that
option is greyed out, your account doesn't allow it — the fallback (save the
`.pbix` file + export a PDF + screenshots) is described in the build guide.

---

# PART C — The tech-stack story (to tell your friends)

Here's the whole thing in plain language. You can read this out.

## C1. The big picture in one line

> "We take messy government price data, run it through a chain of Python
> programs that clean it, analyse it, and predict future prices, and then show
> the results as a simple dashboard a farmer's advisor can read on a phone."

## C2. The tech stack, and *why* each piece is there

Think of it like a kitchen: raw ingredients come in, go through stations, and a
finished dish comes out.

| Stage | Tool we used | In plain words |
|---|---|---|
| **Get the data** | Agmarknet (govt website) | The raw ingredients — 2 years of real onion prices |
| **Clean + organise** | **Python** (pandas) | The prep station — wash, chop, remove the bad bits |
| **Store it** | **SQLite** (a small database) | The fridge — keep clean data ready to grab |
| **Ask questions** | **SQL** | The recipe cards — "average price per month per market" |
| **Make charts** | **Matplotlib** | Plating — turn numbers into pictures |
| **Explain prices** | **statsmodels** (regression) | Measures how much each month/market is worth in rupees |
| **Predict next month** | **LightGBM** (machine learning) | Learns patterns to guess next month's price |
| **Check our work** | **pytest** (tests) | A taste-test before serving — catches mistakes |
| **Track changes** | **Git** | A logbook of every edit, like save points in a game |
| **Show the result** | **Power BI** | The final plated dish the customer actually sees |

## C3. How it actually works, start to finish

1. **We downloaded** 2 years of onion prices from the government's Agmarknet
   site — about 32,000 daily records from 111 markets in Maharashtra.
2. **Python cleans it** — fixes messy market names, removes duplicate files,
   converts units (tonnes to quintals), and handles missing days honestly
   instead of faking numbers.
3. **The clean data goes into a small database (SQLite)** so we can ask
   questions fast.
4. **SQL queries** pull out the patterns — average price by month, by market,
   by onion variety.
5. **Two models run:**
   - one **explains** the price (how much is each month and market worth?),
   - one **predicts** next month's price for each market, with an honest
     "could be in this range" band.
6. **The results are saved as 7 simple CSV files.**
7. **Power BI reads those files** and turns them into an interactive dashboard:
   *when to sell, where to sell, which variety, and next month's forecast.*

The best part: it's **one command** (`python run_pipeline.py`) and it rebuilds
everything from scratch in 20 seconds. Anyone can re-run it and get the exact
same result — that's what makes it real engineering, not just a one-off analysis.

## C4. The 3 things that make it good (say these)

1. **It's honest.** One of our early "findings" turned out to be false on real
   data, and our fancy prediction model barely beat a simple guess — and we
   *reported both* instead of hiding them. That's what real data science looks
   like.
2. **It's reproducible.** One command, from raw files to dashboard, with
   automated tests. Most student projects can't be re-run by someone else.
3. **It's useful.** It answers a real question a real company (DeHaat) asks:
   when, where, and which onion should a farmer sell — plus a price forecast.

## C5. The 20-second pitch

> "It's a data pipeline in Python that turns two years of real government
> onion-price data into farmer-friendly advice — when to sell, where, which
> variety, and a forecast of next month's price — shown in a Power BI
> dashboard. The whole thing runs from raw files to finished dashboard with one
> command, and it's tested and reproducible. What we're proudest of is the
> honesty: we reported the findings that didn't work, not just the ones that
> did."
