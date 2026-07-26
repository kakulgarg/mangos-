"""
Unit tests for the highest-risk pipeline logic.

Run:  cd src && python -m pytest ../tests -q
(the tests add ../src to the path so the modules import as in the pipeline).
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import config as cfg                    # noqa: E402
import parse_agmarknet as P            # noqa: E402
import clean as C                      # noqa: E402
import forecast as F                   # noqa: E402


# --- Parser: canonicalisation + the tonnes->quintals guard ------------------

def test_canonical_name_collapses_variants():
    assert P.canonical_name("pune  apmc") == P.canonical_name("Pune APMC")
    assert P.canonical_key("Pune  APMC") == P.canonical_key("pune apmc")


def test_tonnes_to_quintals_constant():
    # 1 tonne must equal 10 quintals -- the bug that would make the arrivals
    # coefficient wrong by 10x if it regressed.
    assert P.TONNES_TO_QUINTALS == 10.0


def test_market_header_regex_matches_real_format():
    assert P.MARKET_RE.match("Market Name : Lasalgaon APMC")
    assert P.MARKET_RE.match("  Market Name : Pune(Pimpri) APMC ")
    assert P.DATE_RE.match("01/06/2026")
    assert not P.DATE_RE.match("2026-06-01")   # ISO must NOT match the DD/MM regex


# --- Cleaning: duplicate resolution + variety folding -----------------------

def _tiny_frame():
    return pd.DataFrame({
        "mandi_id": ["M1", "M1", "M1", "M2"],
        "price_date": ["2025-01-01", "2025-01-01", "2025-01-02", "2025-01-01"],
        "commodity": ["Onion"] * 4,
        "variety": ["Red", "Red", "Red", "Local"],
        "arrivals": [100.0, 100.0, 120.0, 50.0],
        "min_price": [1000, 1000, 1100, 900],
        "max_price": [2000, 2000, 2100, 1800],
        "modal_price": [1500.0, 1500.0, 1600.0, 1400.0],
    })


def test_exact_duplicates_dropped_not_averaged():
    out = C.resolve_duplicates(_tiny_frame())
    # The two identical (M1, Jan-01, Red) rows collapse to one; 4 -> 3.
    assert len(out) == 3
    assert C.AUDIT["C1_duplicates"]["rule"] == "drop_exact_duplicates"


def test_impossible_values_removed():
    df = _tiny_frame()
    df.loc[0, "modal_price"] = 999999      # above PRICE_MAX
    df.loc[1, "min_price"] = 5000          # min > max
    kept = C.flag_impossible(df)
    assert len(kept) < len(df)


def test_fold_varieties_keeps_key_and_buckets_rest():
    df = _tiny_frame()
    df["variety"] = ["Red", "Chinchwad", "Halva", "Local"]
    folded = C.fold_varieties(df)
    assert set(folded.variety_grp) <= set(cfg.KEY_VARIETIES) | {"Other"}
    assert (folded.loc[df.variety == "Chinchwad", "variety_grp"] == "Other").all()


# --- Forecaster: no leakage, and differencing target -----------------------

def test_forecast_features_are_all_lagged():
    # Every model feature must be knowable at decision time (lag/rolling/season).
    contemporaneous = {"modal_price", "arrivals"}
    assert not (set(F.FEATURES) & contemporaneous)


def test_blend_weight_in_unit_interval():
    assert 0.0 <= F.BLEND <= 1.0


def test_metrics_zero_error_is_perfect():
    m = F._metrics(np.array([100.0, 200.0]), np.array([100.0, 200.0]))
    assert m["mae"] == 0 and m["mape"] == 0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
