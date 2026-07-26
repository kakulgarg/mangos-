"""
Step 6 -- Forecast next month's price, per mandi.

This is the decision the dashboard puts in front of a farmer: "given everything
up to now, which market will pay most NEXT month, and roughly how much?"

WHY MONTHLY, PER MANDI
----------------------
Daily onion prices are dominated by short-run shocks -- a static seasonal model
explains only ~25-30% of daily variance (see model.py). But the farmer's
decision is monthly ("sell in July or hold to September?"), and at MONTHLY grain
a market's price is strongly persistent: this month's mandi price correlates
0.86 with last month's. That persistence is real, forecastable signal, and it
is what the lag features below capture.

THE THREE MODELS (a baseline ladder, so the ML model must earn its place)
-------------------------------------------------------------------------
  1. persistence     next month = this month (lag-1). The naive strong baseline.
  2. seasonal_naive  next month = same month last year (lag-12).
  3. lightgbm        gradient-boosted trees on lag/rolling/seasonal features.

If LightGBM does not beat the baselines in walk-forward backtesting, that is
reported honestly rather than hidden.

HONESTY
-------
  * Evaluation is walk-forward: train on all months strictly before the test
    month, predict that month for every curated mandi, roll forward. No future
    information ever enters training. Features use only lagged values.
  * Prediction intervals come from LightGBM quantile models (q10/q90), so the
    dashboard shows a range, never a false-precision point.
  * Interpretability: gain-based feature importance + permutation importance,
    so the forecast can be explained ("driven mostly by last month's price and
    the seasonal month effect"), not delivered as a black box.
"""

from __future__ import annotations

import json
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import lightgbm as lgb

import config as cfg
from logging_config import get_logger

log = get_logger(__name__)

plt.rcParams.update({
    "figure.dpi": 130, "savefig.dpi": 130, "font.size": 9,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "figure.facecolor": "white",
})
ACCENT, MUTED, GOOD = "#c1440e", "#4a5568", "#2f855a"
FIGS = cfg.OUTPUTS / "figures"
RESULTS: dict = {}

FEATURES = ["lag1", "lag2", "lag3", "lag12", "roll3", "mom_change",
            "arr_lag1", "month_sin", "month_cos", "mandi_code"]
# Conservative trees: the monthly panel is small (~300 rows), so shallow leaves,
# a high min-leaf count and a slow learning rate keep variance down.
LGB_PARAMS = dict(objective="regression_l1", num_leaves=7, min_data_in_leaf=20,
                  learning_rate=0.03, feature_fraction=0.9, bagging_fraction=0.9,
                  bagging_freq=1, verbose=-1)
N_ROUNDS = 400
# Hybrid weight: the production forecast is BLEND*persistence + (1-BLEND)*lgb.
# Monthly onion prices are near a random walk, so persistence is a very strong
# baseline; the blend keeps its robustness while letting the trees add the
# seasonal/cross-market correction (and the quantile interval).
BLEND = 0.6
MODELS = ["persistence", "seasonal_naive", "lightgbm", "ensemble"]


# --- Build the monthly panel ------------------------------------------------

def build_panel() -> pd.DataFrame:
    con = sqlite3.connect(cfg.DB_PATH)
    d = pd.read_sql("SELECT * FROM daily_prices_clean WHERE is_curated = 1",
                    con, parse_dates=["price_date"])
    con.close()

    m = (d.groupby(["mandi_id", "mandi_name", "year", "month_num"])
           .agg(modal_price=("modal_price", "mean"),
                arrivals=("arrivals", "mean"),
                n_obs=("modal_price", "size"))
           .reset_index())
    m["ym"] = m.year * 12 + (m.month_num - 1)          # integer month index
    m = m.sort_values(["mandi_id", "ym"]).reset_index(drop=True)

    # Reindex onto a complete mandi x month grid so lags are true calendar lags
    # even across the missing Aug-2024 hole (the gap stays NaN, never filled).
    full = []
    span = range(int(m.ym.min()), int(m.ym.max()) + 1)
    for mid, g in m.groupby("mandi_id"):
        base = pd.DataFrame({"mandi_id": mid, "ym": list(span)})
        base = base.merge(g, on=["mandi_id", "ym"], how="left")
        base["mandi_name"] = g.mandi_name.iloc[0]
        full.append(base)
    m = pd.concat(full, ignore_index=True)
    m["year"] = m.ym // 12
    m["month_num"] = m.ym % 12 + 1

    g = m.groupby("mandi_id")
    m["lag1"] = g.modal_price.shift(1)
    m["lag2"] = g.modal_price.shift(2)
    m["lag3"] = g.modal_price.shift(3)
    m["lag12"] = g.modal_price.shift(12)
    m["roll3"] = g.modal_price.shift(1).rolling(3, min_periods=1).mean().reset_index(0, drop=True)
    m["mom_change"] = m.lag1 - m.lag2
    m["arr_lag1"] = g.arrivals.shift(1)
    m["month_sin"] = np.sin(2 * np.pi * m.month_num / 12)
    m["month_cos"] = np.cos(2 * np.pi * m.month_num / 12)
    m["mandi_code"] = m.mandi_id.astype("category").cat.codes
    return m


# --- Metrics ----------------------------------------------------------------

def _metrics(y: np.ndarray, yhat: np.ndarray) -> dict:
    err = y - yhat
    return dict(n=int(len(y)), mae=float(np.mean(np.abs(err))),
                rmse=float(np.sqrt(np.mean(err ** 2))),
                mape=float(np.mean(np.abs(err / y)) * 100),
                bias=float(np.mean(err)))


# --- Walk-forward backtest --------------------------------------------------

def backtest(panel: pd.DataFrame) -> pd.DataFrame:
    """Predict each month from a model trained only on strictly earlier months."""
    usable = panel.dropna(subset=["modal_price", "lag1"]).copy()
    # Start testing only once there is enough history to fit trees (>= 8 months).
    test_months = sorted(usable.ym.unique())
    start = test_months[8]
    rows = []
    for ym in [t for t in test_months if t >= start]:
        train = usable[usable.ym < ym]
        test = usable[usable.ym == ym]
        if len(train) < 40 or test.empty:
            continue
        # baselines
        p_persist = test.lag1.values
        p_seasonal = np.where(test.lag12.notna(), test.lag12.values, test.lag1.values)
        # lightgbm predicts the month-over-month CHANGE, then adds it back to
        # lag1. Differencing lets the trees generalise to price levels higher
        # than anything in training -- the shock months persistence handles for
        # free but a level-target tree cannot reach.
        Xtr = train[FEATURES].fillna(-1).values
        Xte = test[FEATURES].fillna(-1).values
        booster = lgb.train(LGB_PARAMS,
                            lgb.Dataset(Xtr, label=(train.modal_price - train.lag1).values),
                            num_boost_round=N_ROUNDS)
        p_lgb = test.lag1.values + booster.predict(Xte)
        p_ens = BLEND * p_persist + (1 - BLEND) * p_lgb
        for i, (_, r) in enumerate(test.iterrows()):
            rows.append(dict(ym=ym, mandi_id=r.mandi_id, y=r.modal_price,
                             persistence=p_persist[i], seasonal_naive=p_seasonal[i],
                             lightgbm=p_lgb[i], ensemble=p_ens[i]))
    return pd.DataFrame(rows)


def summarise_backtest(bt: pd.DataFrame) -> dict:
    out = {}
    for model in MODELS:
        out[model] = _metrics(bt.y.values, bt[model].values)
    log.info("--- Walk-forward backtest (%d mandi-months) ---", len(bt))
    for model in MODELS:
        mm = out[model]
        log.info("  %-15s MAE Rs %5.0f  RMSE Rs %5.0f  MAPE %5.1f%%  bias %+5.0f",
                 model, mm["mae"], mm["rmse"], mm["mape"], mm["bias"])
    best = min(out, key=lambda k: out[k]["mae"])
    lift = 100 * (out["persistence"]["mae"] - out["ensemble"]["mae"]) / out["persistence"]["mae"]
    log.info("  Best by MAE: %s | ensemble lift vs persistence: %+.1f%%", best, lift)
    out["_best"] = best
    out["_ensemble_lift_vs_persistence_pct"] = lift
    return out


# --- Quantile models for prediction intervals -------------------------------

def fit_quantiles(train: pd.DataFrame) -> dict:
    """Quantiles of the month-over-month change; add lag1 back at predict time."""
    models = {}
    X = train[FEATURES].fillna(-1).values
    y = (train.modal_price - train.lag1).values
    for tag, alpha in [("p10", 0.10), ("p50", 0.50), ("p90", 0.90)]:
        params = dict(LGB_PARAMS)
        params.update(objective="quantile", alpha=alpha)
        models[tag] = lgb.train(params, lgb.Dataset(X, label=y), num_boost_round=N_ROUNDS)
    return models


# --- Interpretability -------------------------------------------------------

def importances(panel: pd.DataFrame) -> pd.DataFrame:
    usable = panel.dropna(subset=["modal_price", "lag1"]).copy()
    X = usable[FEATURES].fillna(-1).values
    y = (usable.modal_price - usable.lag1).values   # model the change
    booster = lgb.train(LGB_PARAMS, lgb.Dataset(X, label=y), num_boost_round=N_ROUNDS)
    gain = booster.feature_importance(importance_type="gain")
    # Permutation importance (increase in MAE when a feature is shuffled).
    base = np.mean(np.abs(y - booster.predict(X)))
    rng = np.random.default_rng(0)
    perm = []
    for j in range(len(FEATURES)):
        Xp = X.copy()
        Xp[:, j] = rng.permutation(Xp[:, j])
        perm.append(np.mean(np.abs(y - booster.predict(Xp))) - base)
    imp = pd.DataFrame({"feature": FEATURES,
                        "gain_pct": 100 * gain / gain.sum(),
                        "perm_mae_increase": perm}).sort_values("gain_pct", ascending=False)
    log.info("--- Feature importance (gain) ---\n%s", imp.round(2).to_string(index=False))
    return imp


# --- Next-month forecast for the dashboard ----------------------------------

def forecast_next_month(panel: pd.DataFrame) -> pd.DataFrame:
    """Train on everything; predict the first month with no actual yet."""
    usable = panel.dropna(subset=["modal_price", "lag1"]).copy()
    booster = lgb.train(LGB_PARAMS, lgb.Dataset(usable[FEATURES].fillna(-1).values,
                        label=(usable.modal_price - usable.lag1).values),
                        num_boost_round=N_ROUNDS)
    quant = fit_quantiles(usable)

    # The target month is the last observed month + 1, per mandi.
    next_ym = int(panel.ym.max()) + 1
    rows = []
    for mid, g in panel.groupby("mandi_id"):
        g = g.sort_values("ym")
        last = g.iloc[-1]
        hist = g.dropna(subset=["modal_price"])
        if hist.empty:
            continue
        month_num = next_ym % 12 + 1
        feat = {
            "lag1": last.modal_price, "lag2": last.lag1, "lag3": last.lag2,
            "lag12": g.loc[g.ym == next_ym - 12, "modal_price"].mean(),
            "roll3": hist.modal_price.tail(3).mean(),
            "mom_change": last.modal_price - (last.lag1 if pd.notna(last.lag1) else last.modal_price),
            "arr_lag1": last.arrivals,
            "month_sin": np.sin(2 * np.pi * month_num / 12),
            "month_cos": np.cos(2 * np.pi * month_num / 12),
            "mandi_code": last.mandi_code,
        }
        x = np.array([[feat[f] if pd.notna(feat[f]) else -1 for f in FEATURES]])
        anchor = float(last.modal_price)   # lag1; the model predicts change vs this
        lgb_price = anchor + float(booster.predict(x)[0])
        ens_price = BLEND * anchor + (1 - BLEND) * lgb_price   # production forecast
        rows.append(dict(
            mandi_id=mid, mandi_name=last.mandi_name,
            target_year=next_ym // 12, target_month=month_num,
            target_month_name=cfg.MONTHS[month_num - 1],
            forecast_price=ens_price,
            forecast_low=anchor + float(quant["p10"].predict(x)[0]),
            forecast_high=anchor + float(quant["p90"].predict(x)[0]),
            last_actual_price=anchor,
            last_year_same_month=float(feat["lag12"]) if pd.notna(feat["lag12"]) else np.nan,
        ))
    fc = pd.DataFrame(rows)
    # Keep the interval bracketing the point forecast (quantiles are of the
    # change, the point is the shrunk ensemble, so clamp for consistency).
    fc["forecast_low"] = fc[["forecast_low", "forecast_price"]].min(axis=1)
    fc["forecast_high"] = fc[["forecast_high", "forecast_price"]].max(axis=1)
    for c in ["forecast_price", "forecast_low", "forecast_high"]:
        fc[c] = fc[c].round(0)
    fc["rank_next_month"] = fc.forecast_price.rank(ascending=False).astype(int)
    fc["vs_last_month_pct"] = (100 * (fc.forecast_price - fc.last_actual_price)
                               / fc.last_actual_price).round(1)
    return fc.sort_values("rank_next_month")


# --- Figures ----------------------------------------------------------------

def make_figures(bt: pd.DataFrame, summary: dict, imp: pd.DataFrame, fc: pd.DataFrame) -> None:
    FIGS.mkdir(parents=True, exist_ok=True)

    # M4: model comparison (MAE)
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    maes = [summary[m]["mae"] for m in MODELS]
    cols = [GOOD if m == summary["_best"] else MUTED for m in MODELS]
    bars = ax.bar([m.replace("_", "\n") for m in MODELS], maes, color=cols)
    for b, v in zip(bars, maes):
        ax.text(b.get_x() + b.get_width() / 2, v, f"₹{v:,.0f}", ha="center",
                va="bottom", fontsize=9)
    ax.set_ylabel("Walk-forward MAE (₹/quintal)")
    ax.set_title("Does the ML forecaster beat the naive baselines?",
                 loc="left", fontweight="bold")
    fig.tight_layout(); fig.savefig(FIGS / "fc1_model_comparison.png", bbox_inches="tight")
    plt.close(fig)

    # M5: feature importance
    fig, ax = plt.subplots(figsize=(6.6, 3.8))
    top = imp.head(8).iloc[::-1]
    ax.barh(top.feature, top.gain_pct, color=ACCENT)
    ax.set_xlabel("Gain importance (%)")
    ax.set_title("What drives the forecast", loc="left", fontweight="bold")
    fig.tight_layout(); fig.savefig(FIGS / "fc2_feature_importance.png", bbox_inches="tight")
    plt.close(fig)

    # M6: actual vs predicted over the backtest (state mean)
    fig, ax = plt.subplots(figsize=(9, 3.8))
    g = bt.groupby("ym").agg(y=("y", "mean"), p=("lightgbm", "mean"))
    xs = [f"{int(v // 12)}-{int(v % 12 + 1):02d}" for v in g.index]
    ax.plot(xs, g.y, color=MUTED, lw=1.6, marker="o", ms=3, label="Actual")
    ax.plot(xs, g.p, color=ACCENT, lw=1.6, marker="o", ms=3, label="LightGBM forecast")
    ax.set_ylabel("Mean modal price (₹/quintal)")
    ax.set_title("Walk-forward forecast vs actual (curated-market mean)",
                 loc="left", fontweight="bold")
    ax.tick_params(axis="x", rotation=90, labelsize=7)
    ax.legend(frameon=False, fontsize=8)
    fig.tight_layout(); fig.savefig(FIGS / "fc3_backtest_actual_vs_pred.png", bbox_inches="tight")
    plt.close(fig)
    log.info("Figures -> fc1_model_comparison, fc2_feature_importance, fc3_backtest_actual_vs_pred")


def main() -> None:
    panel = build_panel()
    log.info("Monthly panel: %d mandi-months, %d mandis, %d months",
             len(panel), panel.mandi_id.nunique(), panel.ym.nunique())

    bt = backtest(panel)
    summary = summarise_backtest(bt)
    imp = importances(panel)
    fc = forecast_next_month(panel)

    tm = fc.iloc[0]
    log.info("--- Next-month forecast: %s %d ---", tm.target_month_name, tm.target_year)
    log.info("Best market next month: %s at ~Rs %.0f/qtl (range %.0f-%.0f)",
             tm.mandi_name, tm.forecast_price, tm.forecast_low, tm.forecast_high)
    log.info("\n%s", fc[["rank_next_month", "mandi_name", "forecast_price",
                          "forecast_low", "forecast_high", "vs_last_month_pct"]]
             .head(8).to_string(index=False))

    cfg.OUTPUTS.mkdir(parents=True, exist_ok=True)
    fc.to_csv(cfg.OUTPUTS / "forecast_next_month.csv", index=False)
    imp.to_csv(cfg.OUTPUTS / "forecast_feature_importance.csv", index=False)
    RESULTS.update(dict(
        grain="monthly x mandi", models=summary,
        target_month=f"{tm.target_month_name} {int(tm.target_year)}",
        best_market_next_month=dict(mandi=tm.mandi_name, price=float(tm.forecast_price),
                                    low=float(tm.forecast_low), high=float(tm.forecast_high)),
        feature_importance=imp.round(3).to_dict(orient="records"),
    ))
    (cfg.OUTPUTS / "forecast_results.json").write_text(json.dumps(RESULTS, indent=2))
    make_figures(bt, summary, imp, fc)
    log.info("Wrote forecast_next_month.csv, forecast_results.json, importance + figures")


if __name__ == "__main__":
    main()
