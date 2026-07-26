"""
Central configuration for the Mandi Price Watch pipeline.

Every scope decision lives here and nowhere else. Adding a commodity, a state,
or another market is a change to this file only -- no query, notebook, or
script hardcodes a mandi, a commodity, or a price column.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Paths (numbered data layers: source is immutable, never written to) ----
ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SOURCE = DATA / "01_source"        # immutable raw Agmarknet exports
INTERIM = DATA / "02_interim"      # parsed flat tables
PROCESSED = DATA / "03_processed"  # SQLite db + cleaned csv
OUTPUTS = ROOT / "outputs"

# SQLite needs a filesystem that supports its locking. On a normal local disk
# (the user's machine) that is data/03_processed. The MANDI_DB env var lets a
# build run the DB on fast local storage when the working tree sits on a
# network/mounted filesystem that SQLite cannot journal on.
DB_PATH = Path(os.environ.get("MANDI_DB", PROCESSED / "mandi.db"))

# --- Scope ------------------------------------------------------------------
COMMODITY = "Onion"
STATE = "Maharashtra"

# Curated high-coverage markets. Chosen for coverage AND for representing the
# structures that make the advisory question meaningful: the Nashik onion belt
# (Lasalgaon is Asia's largest onion market and sets the reference price), the
# Pune consumption cluster, and a spread of regional hubs. Keyed on the market
# NAME (stable), not on a coverage-rank id. All 111 markets are loaded into the
# database; recommendations are made only on this reliable subset.
CURATED_MANDIS = [
    "Lasalgaon APMC",
    "Lasalgaon(Niphad) APMC",
    "Lasalgaon(Vinchur) APMC",
    "Pimpalgaon Baswant APMC",
    "Pune APMC",
    "Pune(Pimpri) APMC",
    "Pune(Manjri) APMC",
    "Pune(Moshi) APMC",
    "Kolhapur APMC",
    "Satara APMC",
    "Nasik APMC",
    "Chattrapati Sambhajinagar APMC",
    "Bhusaval APMC",
    "Mangal Wedha APMC",
]

# Markets below this coverage are never allowed to carry a recommendation,
# even if named above -- a guard against a curated name that turns out thin.
COVERAGE_MIN_PCT = 60.0

# Real coverage span. August 2024 is absent from the source (a genuine gap in
# the Agmarknet exports), so the seasonal August estimate rests on 2025 alone
# for some markets -- flagged in the model card, never silently filled.
DATE_START = "2024-06-01"
DATE_END = "2026-06-30"

# --- Analytical decisions ---------------------------------------------------
# modal_price -- the price at which the largest volume actually traded. Chosen
# over avg(min,max) because min/max are the extreme tails of the day's book.
PRICE_FIELD = "modal_price"

# Onion varieties worth analysing on their own (real price differences). Every
# other label is folded into "Other" so the drill-down stays legible.
KEY_VARIETIES = ["Red", "Local", "White", "Unhali"]

# Rolling window for the price trend, in days. 7 matches a farmer's real
# decision horizon: harvest, arrange transport, sell inside roughly a week.
ROLLING_WINDOW_DAYS = 7

# Fraction of the timeline held out for testing. The split is CHRONOLOGICAL,
# never random: a random split lets the model see the future.
TEST_FRACTION = 0.20

# --- Data-quality rules -----------------------------------------------------
DUPLICATE_RULE = "drop_exact_then_mean"   # exact repeats dropped; conflicts averaged
GAP_RULE = "leave"                        # no interpolation of unreported days

# Plausibility bounds for onion, real-data calibrated. Arrivals are in
# QUINTALS (parser converts tonnes -> quintals). Real modal reaches ~Rs
# 25,000/qtl in shock weeks, so the band is wide; obvious errors still caught.
PRICE_MIN = 100
PRICE_MAX = 30000
ARRIVALS_MIN = 0
ARRIVALS_MAX = 500000

# --- Shared display constants ----------------------------------------------
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
