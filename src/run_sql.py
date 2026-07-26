"""
Step 2 -- Execute the analytical SQL.

Splits sql/analysis.sql on its `-- Qn.` markers, runs each query against the
database, and writes the full result to outputs/ as CSV. Those CSVs are the
dashboard extracts, so the dashboard is fed by the same SQL that is graded.
"""

from __future__ import annotations

import re
import sqlite3
import sys

import pandas as pd

import config as C
from logging_config import get_logger

log = get_logger(__name__)
SQL_PATH = C.ROOT / "sql" / "analysis.sql"

DESCRIPTIONS = {
    "Q1": "Price and arrivals per mandi (where to sell)",
    "Q2": "Seasonality across all mandis (when to sell)",
    "Q3": "7-day rolling price per mandi",
    "Q4": "Year-on-year comparison per mandi-month",
    "Q5": "Seasonal pattern per mandi (when, per market)",
    "Q6": "Coverage and extensibility check",
    "Q7": "Price by variety and month (which category pays best)",
}


def split_queries(text: str):
    """Return [(label, sql)] for each `-- Qn.` block that ends in a statement."""
    lines = text.splitlines()
    starts = [i for i, ln in enumerate(lines) if re.match(r"^--\s*Q\d+\.", ln)]
    out = []
    for n, start in enumerate(starts):
        end = starts[n + 1] if n + 1 < len(starts) else len(lines)
        block = "\n".join(lines[start:end])
        label = re.match(r"^--\s*(Q\d+)\.", lines[start]).group(1)
        m = re.search(r"^\s*(WITH|SELECT)\b", block, re.M)
        if not m:
            continue
        sql = block[m.start():]
        sql = sql[: sql.rindex(";") + 1] if ";" in sql else sql
        out.append((label, sql))
    return out


def main() -> None:
    ver = tuple(int(x) for x in sqlite3.sqlite_version.split("."))
    if ver < (3, 28, 0):
        sys.exit(f"SQLite {sqlite3.sqlite_version} too old; need >= 3.28 for WINDOW.")
    if not C.DB_PATH.exists():
        sys.exit(f"No database at {C.DB_PATH}. Run load_db.py first.")

    C.OUTPUTS.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(C.DB_PATH)
    queries = split_queries(SQL_PATH.read_text())
    log.info("SQLite %s | %d queries", sqlite3.sqlite_version, len(queries))

    failures = []
    for label, sql in queries:
        desc = DESCRIPTIONS.get(label, "")
        try:
            df = pd.read_sql_query(sql, con)
        except Exception as e:  # noqa: BLE001 -- want the label with the error
            failures.append((label, e))
            log.error("[%s] FAILED: %s", label, e)
            continue
        slug = desc.split("(")[0].strip().lower().replace(" ", "_").replace("-", "_")
        path = C.OUTPUTS / f"{label.lower()}_{slug}.csv"
        df.to_csv(path, index=False)
        log.info("[%s] %s -> %s (%d rows)", label, desc, path.name, len(df))

    con.close()
    if failures:
        sys.exit(f"{len(failures)} quer(ies) failed: {[f[0] for f in failures]}")
    log.info("All queries ran cleanly.")


if __name__ == "__main__":
    main()
