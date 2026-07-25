"""
Step 0 -- Parse Agmarknet "Date Wise Prices for Specified Commodity" exports.

WHY THIS FILE EXISTS
--------------------
The Agmarknet report is not a flat table. Market names appear as HEADER ROWS
between blocks of data rather than as a column:

    Arrival Date,Arrivals (Metric Tonnes),Variety,Minimum Price,...
    Market Name : Lasalgaon APMC
    01/06/2026,1233.0,Unhali,100.0,2051.0,1460.0
    Market Name : Pune APMC
    01/06/2026,980.0,Local,300.0,1900.0,1400.0

A normal CSV reader produces garbage from this: the market header lands in the
date column and the market identity is lost. So the file is walked line by
line, carrying the current market forward until the next header.

WHAT THIS VERSION DOES DIFFERENTLY (real-data hardening)
--------------------------------------------------------
1. VARIETY IS KEPT. The grain of the output is (mandi, date, variety), because
   the project now answers "which onion category pays best". Aggregation to a
   single mandi-day price happens later, in cleaning, where it is auditable.
2. ARRIVALS ARE CONVERTED tonnes -> quintals. The Agmarknet header reads
   "Arrivals (Metric Tonnes)" but every downstream price is Rs/QUINTAL. Mixing
   the two makes the arrivals coefficient wrong by 10x. 1 tonne = 10 quintal.
3. MANDI IDs ARE KEYED ON THE NAME, not on coverage rank. Rank-based IDs
   silently re-point a fixed MANDI_FILTER when new months are added. IDs here
   are assigned by sorted canonical name and are therefore stable.
4. EXACT DUPLICATE ROWS ARE DROPPED. Re-downloaded months (e.g. a duplicate
   February export) would otherwise double-count.

Output: data/02_interim/daily_prices.csv  (grain: mandi x date x variety)
        data/02_interim/mandis.csv
        data/02_interim/coverage.csv       (used to pick the curated subset)
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pandas as pd

import config as cfg
from logging_config import get_logger

log = get_logger(__name__)

DATE_RE = re.compile(r"^\d{2}/\d{2}/\d{4}$")
MARKET_RE = re.compile(r"^\s*Market\s*Name\s*:\s*(.+?)\s*$", re.I)
NUM_COLS = ["arrivals", "min_price", "max_price", "modal_price"]

# 1 metric tonne = 10 quintals. Agmarknet reports arrivals in tonnes; the whole
# analysis works in quintals, so convert once, here, and never think about it
# again downstream.
TONNES_TO_QUINTALS = 10.0


def canonical_name(raw: str) -> str:
    """
    Normalise a raw market string into a stable display name.

    Real Agmarknet names are inconsistent in case and whitespace across months
    ('Pune  APMC' vs 'Pune APMC'). Collapsing whitespace and title-casing keeps
    one market from splitting into several. The APMC token is normalised in
    upper-case because 'Apmc' reads wrong.
    """
    s = re.sub(r"\s+", " ", str(raw).strip())
    # Title-case but preserve well-known upper-case tokens.
    s = s.title()
    s = re.sub(r"\bApmc\b", "APMC", s)
    s = re.sub(r"\bComitee\b", "Committee", s)
    return s


def canonical_key(name: str) -> str:
    """A case/space-insensitive key used only to detect that two spellings are
    the same market. Never shown to a user."""
    return re.sub(r"\s+", "", canonical_name(name).upper())


def parse_file(path: Path) -> pd.DataFrame:
    """Walk one export, carrying the current market header forward."""
    rows, market, skipped = [], None, 0
    with open(path, encoding="utf-8-sig", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\r\n").strip()
            if not line:
                continue
            m = MARKET_RE.match(line.strip('"'))
            if m:
                market = m.group(1).strip()
                continue
            parts = [p.strip().strip('"') for p in line.split(",")]
            if len(parts) < 6 or not DATE_RE.match(parts[0]):
                continue  # title lines, column headers, footers
            if market is None:
                skipped += 1
                continue
            rows.append({
                "mandi_name_raw": market,
                "price_date": parts[0],
                "arrivals": parts[1],
                "variety": parts[2],
                "min_price": parts[3],
                "max_price": parts[4],
                "modal_price": parts[5],
            })
    if skipped:
        log.warning("%s: %d rows before any market header, skipped", path.name, skipped)
    return pd.DataFrame(rows)


def main() -> None:
    source_files = sorted(cfg.SOURCE.glob("*.csv"))
    if not source_files:
        sys.exit(f"No Agmarknet exports found in {cfg.SOURCE}")

    log.info("Parsing %d Agmarknet export(s) from %s", len(source_files), cfg.SOURCE)
    frames = []
    for p in source_files:
        df = parse_file(p)
        if len(df):
            frames.append(df)
    if not frames:
        sys.exit("No parseable rows found. Check the file format.")

    d = pd.concat(frames, ignore_index=True)
    log.info("Combined raw rows: %d", len(d))

    # --- Types --------------------------------------------------------------
    d["price_date"] = pd.to_datetime(d.price_date, format="%d/%m/%Y", errors="coerce")
    for c in NUM_COLS:
        d[c] = pd.to_numeric(
            d[c].astype(str).str.replace(",", "", regex=False), errors="coerce")

    bad_dates = int(d.price_date.isna().sum())
    if bad_dates:
        log.warning("%d unparseable dates dropped", bad_dates)
        d = d.dropna(subset=["price_date"])

    # --- Unit conversion: tonnes -> quintals --------------------------------
    d["arrivals"] = d["arrivals"] * TONNES_TO_QUINTALS

    # --- Canonicalise market names, assign STABLE ids -----------------------
    d["mandi_name"] = d.mandi_name_raw.map(canonical_name)
    d["_key"] = d.mandi_name.map(canonical_key)
    # Collapse any spelling variants onto the most common display spelling.
    display = (d.groupby("_key").mandi_name
                 .agg(lambda s: s.value_counts().index[0]))
    d["mandi_name"] = d["_key"].map(display)
    # Stable ids: sorted by canonical key, independent of coverage/row counts.
    keys = sorted(d["_key"].unique())
    ids = {k: f"M{i + 1:03d}" for i, k in enumerate(keys)}
    d["mandi_id"] = d["_key"].map(ids)
    d["commodity"] = cfg.COMMODITY

    # --- Drop exact duplicate rows (re-downloaded months) -------------------
    key_cols = ["mandi_id", "price_date", "variety"] + NUM_COLS
    before = len(d)
    d = d.drop_duplicates(key_cols, keep="first")
    if before - len(d):
        log.info("Dropped %d exact duplicate variety-day rows", before - len(d))

    # --- Coverage table (feeds the curated-subset choice) -------------------
    md = d.drop_duplicates(["mandi_id", "price_date"])   # unique mandi-days
    span_days = (d.price_date.max() - d.price_date.min()).days + 1
    cov = (md.groupby(["mandi_id", "mandi_name"]).size()
             .reset_index(name="reporting_days"))
    cov["pct_coverage"] = (100 * cov.reporting_days / span_days).round(1)
    cov = cov.sort_values("pct_coverage", ascending=False).reset_index(drop=True)

    # --- Write --------------------------------------------------------------
    cfg.INTERIM.mkdir(parents=True, exist_ok=True)
    out_prices = cfg.INTERIM / "daily_prices.csv"
    out_mandis = cfg.INTERIM / "mandis.csv"
    out_cov = cfg.INTERIM / "coverage.csv"

    cols = ["mandi_id", "price_date", "commodity", "variety",
            "arrivals", "min_price", "max_price", "modal_price"]
    d.sort_values(["mandi_id", "price_date", "variety"])[cols].to_csv(out_prices, index=False)

    mandis = (d[["mandi_id", "mandi_name"]].drop_duplicates()
                .assign(district=pd.NA, state=cfg.STATE)
                .sort_values("mandi_id"))
    mandis.to_csv(out_mandis, index=False)
    cov.to_csv(out_cov, index=False)

    log.info("Date span: %s to %s (%d months)",
             d.price_date.min().date(), d.price_date.max().date(),
             d.price_date.dt.to_period("M").nunique())
    log.info("Markets: %d | varieties: %d | rows: %d",
             d.mandi_id.nunique(), d.variety.nunique(), len(d))
    log.info("Wrote %s, %s, %s", out_prices.name, out_mandis.name, out_cov.name)
    log.info("Top coverage:\n%s", cov.head(15).to_string(index=False))


if __name__ == "__main__":
    main()
