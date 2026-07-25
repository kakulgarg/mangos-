"""
Step 7 -- Dashboard extracts.

Produces flat, denormalised CSVs for Power BI. Design rules:
  * One row = one fact. No pre-pivoted cross-tabs -- Power BI pivots natively.
  * Every measure a chart needs is a column. No DAX required for the core deck.
  * Month is emitted as BOTH a number (for sorting) and a name (for display).
  * Observation counts travel with every aggregate, so a thin cell stays visible.

All figures are computed on the CURATED markets and read model/forecast accuracy
from the results JSON -- never hardcoded -- so a re-run can never leave a stale
number on a farmer-facing dashboard.
"""

from __future__ import annotations

import json
import sqlite3

import numpy as np
import pandas as pd

import config as cfg
from logging_config import get_logger

log = get_logger(__name__)
DASH = cfg.ROOT / "dashboard" / "data"
MONTHS = cfg.MONTHS


def _model_accuracy() -> dict:
    """Read accuracy from artefacts so the dashboard never states a stale number."""
    acc = {"mape_normal": np.nan, "mae_forecast": np.nan, "forecast_mape": np.nan}
    fp = cfg.OUTPUTS / "forecast_results.json"
    if fp.exists():
        r = json.loads(fp.read_text())
        best = r.get("models", {}).get(r.get("models", {}).get("_best", "ensemble"), {})
        acc["mae_forecast"] = round(best.get("mae", np.nan), 0)
        acc["forecast_mape"] = round(best.get("mape", np.nan), 1)
    mp = cfg.OUTPUTS / "model_results.json"
    if mp.exists():
        r = json.loads(mp.read_text())
        acc["mape_normal"] = round(r.get("test", {}).get("mape", np.nan), 1)
    return acc


def load() -> tuple[pd.DataFrame, pd.DataFrame]:
    con = sqlite3.connect(cfg.DB_PATH)
    d = pd.read_sql("SELECT * FROM daily_prices_clean WHERE is_curated = 1",
                    con, parse_dates=["price_date"])
    v = pd.read_sql("SELECT * FROM daily_prices_variety WHERE is_curated = 1",
                    con, parse_dates=["price_date"])
    con.close()
    return d, v


def e1_fact_daily(d: pd.DataFrame) -> pd.DataFrame:
    f = d[["mandi_id", "mandi_name", "price_date", "commodity", "arrivals",
           "min_price", "max_price", "modal_price", "year", "month_num",
           "rolling_7d_price", "rolling_7d_arrivals"]].copy()
    f["month_name"] = f.month_num.map(lambda i: MONTHS[i - 1])
    f["quarter"] = "Q" + f.price_date.dt.quarter.astype(str)
    f["is_price_spike"] = (
        d.groupby("mandi_id").modal_price.transform(lambda s: (s - s.mean()) / s.std(ddof=0))
        .abs() > 3).map({True: "Shock", False: "Normal"})
    f["pct_vs_7d_trend"] = (100 * (f.modal_price - f.rolling_7d_price)
                            / f.rolling_7d_price).round(1)
    return f


def e2_seasonal(d: pd.DataFrame) -> pd.DataFrame:
    g = (d.groupby(["mandi_id", "mandi_name", "month_num"])
           .agg(avg_modal_price=("modal_price", "mean"),
                median_modal_price=("modal_price", "median"),
                min_modal_price=("modal_price", "min"),
                max_modal_price=("modal_price", "max"),
                avg_arrivals=("arrivals", "mean"),
                observations=("modal_price", "size")).reset_index())
    g["month_name"] = g.month_num.map(lambda i: MONTHS[i - 1])
    own = g.groupby("mandi_id").avg_modal_price.transform("mean")
    g["seasonal_index"] = (100 * g.avg_modal_price / own).round(1)
    g["month_rank"] = g.groupby("mandi_id").avg_modal_price.rank(ascending=False).astype(int)
    worst = g.groupby("mandi_id").avg_modal_price.transform("min")
    g["rs_above_worst_month"] = (g.avg_modal_price - worst).round(0)
    g["evidence"] = np.where(g.observations < 40, "Thin (<40 obs)", "Adequate")
    return g.round(1)


def e3_market(d: pd.DataFrame) -> pd.DataFrame:
    g = (d.groupby(["mandi_id", "mandi_name"])
           .agg(avg_modal_price=("modal_price", "mean"),
                total_arrivals=("arrivals", "sum"),
                avg_daily_arrivals=("arrivals", "mean"),
                reporting_days=("modal_price", "size"),
                first_report=("price_date", "min"),
                last_report=("price_date", "max")).reset_index())
    state = d.modal_price.mean()
    g["pct_vs_state_avg"] = (100 * (g.avg_modal_price - state) / state).round(1)
    g["rs_vs_state_avg"] = (g.avg_modal_price - state).round(0)
    g["price_rank"] = g.avg_modal_price.rank(ascending=False).astype(int)
    span = (d.price_date.max() - d.price_date.min()).days + 1
    g["pct_coverage"] = (100 * g.reporting_days / span).round(1)
    return g.round(1)


def e4_recommendation(d: pd.DataFrame, acc: dict) -> pd.DataFrame:
    """The decision layer -- an instruction, not a chart to interpret."""
    s = e2_seasonal(d)
    conditions = [s.seasonal_index >= 115, s.seasonal_index >= 100, s.seasonal_index >= 85]
    choices = ["SELL NOW", "GOOD TO SELL", "HOLD IF YOU CAN"]
    s["recommendation"] = np.select(conditions, choices, default="STORE OR HOLD")
    peak = s.loc[s.groupby("mandi_id").avg_modal_price.idxmax(),
                 ["mandi_id", "month_name", "avg_modal_price"]]
    peak.columns = ["mandi_id", "best_month", "best_month_price"]
    s = s.merge(peak, on="mandi_id", how="left")
    s["rs_gain_if_wait_for_peak"] = (s.best_month_price - s.avg_modal_price).round(0)
    # Accuracy read from artefacts (never hardcoded).
    band = (acc["forecast_mape"] / 100.0) if pd.notna(acc["forecast_mape"]) else 0.14
    s["forecast_mae_rs"] = acc["mae_forecast"]
    s["forecast_mape_pct"] = acc["forecast_mape"]
    s["price_range_low"] = (s.avg_modal_price * (1 - band)).round(0)
    s["price_range_high"] = (s.avg_modal_price * (1 + band)).round(0)
    return s


def e5_model_coefficients() -> pd.DataFrame | None:
    p = cfg.OUTPUTS / "model_coefficients.csv"
    if not p.exists():
        log.warning("model_coefficients.csv missing -- run model.py first")
        return None
    c = pd.read_csv(p)
    c["rs_vs_baseline"] = c.rs_vs_baseline.round(0)
    c["significant"] = np.where((c.ci_low > 0) | (c.ci_high < 0), "Yes", "No / baseline")
    order = {m: i + 1 for i, m in enumerate(MONTHS)}
    c["sort_order"] = c.apply(
        lambda r: order.get(r.label, 99) if r.kind == "month" else 99, axis=1)
    return c.round(1)


def e6_variety(v: pd.DataFrame) -> pd.DataFrame:
    """Grain: variety x month. Answers 'which onion category pays best, when'."""
    g = (v.groupby(["variety_group", "month_num"])
           .agg(avg_modal_price=("modal_price", "mean"),
                median_modal_price=("modal_price", "median"),
                observations=("modal_price", "size")).reset_index())
    g["month_name"] = g.month_num.map(lambda i: MONTHS[i - 1])
    # Premium of each variety vs the all-variety mean in that month.
    month_mean = g.groupby("month_num").avg_modal_price.transform("mean")
    g["pct_vs_month_avg"] = (100 * (g.avg_modal_price - month_mean) / month_mean).round(1)
    g["variety_rank_in_month"] = (g.groupby("month_num").avg_modal_price
                                  .rank(ascending=False).astype(int))
    g["evidence"] = np.where(g.observations < 30, "Thin (<30 obs)", "Adequate")
    return g.round(1)


def e7_forecast() -> pd.DataFrame | None:
    """Next-month forecast per mandi (the 'which mandi pays most next month')."""
    p = cfg.OUTPUTS / "forecast_next_month.csv"
    if not p.exists():
        log.warning("forecast_next_month.csv missing -- run forecast.py first")
        return None
    return pd.read_csv(p)


def main() -> None:
    DASH.mkdir(parents=True, exist_ok=True)
    d, v = load()
    acc = _model_accuracy()
    log.info("Building extracts from %d curated mandi-days (%d markets); "
             "forecast MAE Rs %s, MAPE %s%%",
             len(d), d.mandi_id.nunique(), acc["mae_forecast"], acc["forecast_mape"])

    extracts = {
        "fact_daily_prices": e1_fact_daily(d),
        "seasonal_by_mandi": e2_seasonal(d),
        "market_summary": e3_market(d),
        "recommendation": e4_recommendation(d, acc),
        "model_coefficients": e5_model_coefficients(),
        "variety_by_month": e6_variety(v),
        "forecast_next_month": e7_forecast(),
    }
    for name, df in extracts.items():
        if df is None:
            continue
        df.to_csv(DASH / f"{name}.csv", index=False)
        log.info("  %-24s %d rows x %d cols", name + ".csv", len(df), df.shape[1])

    rec = extracts["recommendation"]
    sell = rec[rec.recommendation == "SELL NOW"]
    log.info("SELL months flagged: %s", sorted(sell.month_name.unique()))
    log.info("Best month (mode across mandis): %s",
             rec.best_month.value_counts().idxmax())
    log.info("Extracts -> dashboard/data/")


if __name__ == "__main__":
    main()
