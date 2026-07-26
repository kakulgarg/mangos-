"""
Step 1 -- Assemble the data into SQLite.

Reads the parsed interim tables (grain: mandi x date x variety), applies scope
from config, and loads them into SQLite AS SOURCED. Nothing is cleaned here
beyond structural normalisation -- deduplication, gap handling, and
impossible-value treatment are Step 3 decisions and are logged there, so the
database always holds the data as sourced and every judgement call is visible.

Two tables:
  mandis        one row per market (all 111 loaded; scope applied to prices)
  daily_prices  one row per mandi x date x variety
"""

from __future__ import annotations

import sqlite3
import sys

import pandas as pd

import config as C
from logging_config import get_logger

log = get_logger(__name__)

SCHEMA = """
DROP TABLE IF EXISTS daily_prices;
DROP TABLE IF EXISTS mandis;

CREATE TABLE mandis (
    mandi_id    TEXT PRIMARY KEY,
    mandi_name  TEXT NOT NULL,
    district    TEXT,
    state       TEXT NOT NULL,
    is_curated  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE daily_prices (
    mandi_id    TEXT NOT NULL REFERENCES mandis(mandi_id),
    price_date  DATE NOT NULL,
    commodity   TEXT NOT NULL,
    variety     TEXT,
    arrivals    REAL,
    min_price   REAL,
    max_price   REAL,
    modal_price REAL
);

CREATE INDEX idx_prices_mandi_date ON daily_prices(mandi_id, price_date);
CREATE INDEX idx_prices_variety    ON daily_prices(variety);
CREATE INDEX idx_prices_commodity  ON daily_prices(commodity);
"""


def build_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    prices_path = C.INTERIM / "daily_prices.csv"
    mandis_path = C.INTERIM / "mandis.csv"
    if not prices_path.exists():
        sys.exit(f"No parsed data at {prices_path}. Run parse_agmarknet.py first.")

    prices = pd.read_csv(prices_path, parse_dates=["price_date"])
    mandis = pd.read_csv(mandis_path)
    log.info("Read %d price rows, %d markets", len(prices), len(mandis))

    # Curated flag by NAME (stable) with a coverage floor.
    cov = pd.read_csv(C.INTERIM / "coverage.csv")
    covered = set(cov.loc[cov.pct_coverage >= C.COVERAGE_MIN_PCT, "mandi_name"])
    curated = {n for n in C.CURATED_MANDIS if n in covered}
    mandis["is_curated"] = mandis.mandi_name.isin(curated).astype(int)
    log.info("Curated subset: %d markets (coverage >= %.0f%%)",
             mandis.is_curated.sum(), C.COVERAGE_MIN_PCT)

    # Scope: commodity + date range. Mandi scope is NOT applied to the DB (all
    # markets load); it is applied where recommendations are made.
    before = len(prices)
    prices = prices[prices.commodity.str.strip().str.lower() == C.COMMODITY.lower()]
    prices = prices[prices.price_date.between(C.DATE_START, C.DATE_END)]
    log.info("Scope (commodity+dates): kept %d of %d rows", len(prices), before)

    prices = prices.dropna(subset=["mandi_id", "price_date"])
    prices["price_date"] = prices.price_date.dt.strftime("%Y-%m-%d")
    return mandis, prices.reset_index(drop=True)


def sanity_checks(con: sqlite3.Connection) -> None:
    q = lambda s: con.execute(s).fetchall()
    log.info("--- Sanity checks ---")
    n_mandis, n_rows = q(
        "SELECT (SELECT COUNT(*) FROM mandis), COUNT(*) FROM daily_prices")[0]
    n_curated = q("SELECT COUNT(*) FROM mandis WHERE is_curated=1")[0][0]
    span = q("SELECT MIN(price_date), MAX(price_date) FROM daily_prices")[0]
    log.info("Rows: %d | markets: %d (%d curated) | span: %s..%s",
             n_rows, n_mandis, n_curated, span[0], span[1])

    dupes = q("""SELECT COUNT(*) FROM (
                   SELECT mandi_id, price_date, variety
                   FROM daily_prices GROUP BY 1,2,3 HAVING COUNT(*) > 1)""")[0][0]
    log.info("Duplicate (mandi,date,variety) keys carried in: %d", dupes)

    bad = q(f"""SELECT
        SUM(modal_price NOT BETWEEN {C.PRICE_MIN} AND {C.PRICE_MAX}),
        SUM(arrivals    NOT BETWEEN {C.ARRIVALS_MIN} AND {C.ARRIVALS_MAX}),
        SUM(modal_price < min_price OR modal_price > max_price),
        SUM(min_price > max_price) FROM daily_prices""")[0]
    log.info("Implausible: %s price OOR, %s arrivals OOR, %s modal outside "
             "[min,max], %s min>max", bad[0] or 0, bad[1] or 0, bad[2] or 0, bad[3] or 0)


def main() -> None:
    C.PROCESSED.mkdir(parents=True, exist_ok=True)
    mandis, prices = build_frames()
    with sqlite3.connect(C.DB_PATH) as con:
        con.executescript(SCHEMA)
        mandis.to_sql("mandis", con, if_exists="append", index=False)
        prices.to_sql("daily_prices", con, if_exists="append", index=False)
        con.commit()
        log.info("Loaded -> %s (mandis=%d, daily_prices=%d)",
                 C.DB_PATH, len(mandis), len(prices))
        sanity_checks(con)


if __name__ == "__main__":
    main()
