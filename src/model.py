"""
Step 5 -- Model the price.

ONE model: linear regression, as the brief specifies. The value here is in the
evaluation and the honesty of the failure analysis, not in model choice.

Two decisions that matter more than the algorithm:

1. CHRONOLOGICAL SPLIT, never random. Prices are a time series with strong
   seasonality. A random split puts August 2025 in training and August 2024 in
   test, so the model is scored on months it has already seen -- it memorises
   the calendar and reports an inflated test score. The honest question is
   "trained on the past, how does it do on the future it has not seen?", and
   only a time-ordered split asks that.

2. FEATURES AS SPECIFIED IN notebooks/feature_spec.md, driven by the EDA:
   month (categorical), mandi (categorical), arrivals_dev (continuous).
   Raw arrivals is excluded -- collinear with month, sign-unstable.

The chronological split has a known cost, and it is reported rather than
hidden: the test period is Nov 2025 - Jun 2026, which contains no August. The
model is therefore evaluated on the low-price half of the year. This is
quantified in the seasonal error breakdown.
"""

import json
import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
from statsmodels.stats.outliers_influence import variance_inflation_factor

import config as cfg

plt.rcParams.update({
    "figure.dpi": 130, "savefig.dpi": 130, "font.size": 9,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "figure.facecolor": "white",
})
ACCENT, MUTED = "#c1440e", "#4a5568"
FIGS = cfg.OUTPUTS / "figures"
RESULTS = {}

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def load():
    con = sqlite3.connect(cfg.DB_PATH)
    d = pd.read_sql("SELECT * FROM daily_prices_clean WHERE is_curated = 1",
                    con, parse_dates=["price_date"])
    con.close()
    return d.sort_values("price_date").reset_index(drop=True)


def build_features(d):
    """arrivals_dev must be computed from TRAINING months only -- see split()."""
    d = d.copy()
    d["m"] = d.month_num.astype(str)
    return d


def split(d):
    """
    Chronological split at the (1 - TEST_FRACTION) quantile of dates.

    The month-mean used to build arrivals_dev is computed on TRAIN ONLY and
    then applied to test. Computing it over the full dataset would leak test-
    period information into a training feature -- a subtle form of the same
    mistake a random split makes loudly.
    """
    cut = d.price_date.quantile(1 - cfg.TEST_FRACTION)
    train = d[d.price_date <= cut].copy()
    test = d[d.price_date > cut].copy()

    month_mean = train.groupby("month_num").arrivals.mean()
    global_mean = train.arrivals.mean()
    for part in (train, test):
        part["arrivals_dev"] = part.arrivals - part.month_num.map(month_mean).fillna(global_mean)

    return train, test, cut


def fit_and_evaluate(train, test):
    formula = "modal_price ~ arrivals_dev + C(m) + C(mandi_id)"
    # HAC (Newey-West) robust standard errors. Daily prices within a mandi are
    # strongly autocorrelated, so classical OLS SEs -- and the CIs on the month
    # coefficients -- would be far too narrow. HAC widens them honestly.
    model = smf.ols(formula, train).fit(cov_type="HAC", cov_kwds={"maxlags": 5})

    pred_tr = model.predict(train)
    pred_te = model.predict(test)

    def metrics(y, yhat):
        err = y - yhat
        return dict(
            n=int(len(y)),
            mae=float(np.mean(np.abs(err))),
            rmse=float(np.sqrt(np.mean(err ** 2))),
            mape=float(np.mean(np.abs(err / y)) * 100),
            r2=float(1 - (err ** 2).sum() / ((y - y.mean()) ** 2).sum()),
        )

    m_tr = metrics(train.modal_price, pred_tr)
    m_te = metrics(test.modal_price, pred_te)
    return model, pred_tr, pred_te, m_tr, m_te


def report_coefficients(model, train):
    """Translate coefficients into rupees a field agent can sanity-check."""
    p = model.params
    ci = model.conf_int()
    base_mandi = sorted(train.mandi_id.unique())[0]
    base_name = train.loc[train.mandi_id == base_mandi, "mandi_name"].iloc[0]

    rows = []
    for i in range(1, 13):
        key = f"C(m)[T.{i}]"
        val = 0.0 if i == 1 else float(p.get(key, np.nan))
        lo, hi = (0.0, 0.0) if i == 1 else (float(ci.loc[key, 0]), float(ci.loc[key, 1]))
        rows.append(dict(kind="month", label=MONTHS[i - 1], rs_vs_baseline=val,
                         ci_low=lo, ci_high=hi))

    for mid in sorted(train.mandi_id.unique()):
        name = train.loc[train.mandi_id == mid, "mandi_name"].iloc[0]
        key = f"C(mandi_id)[T.{mid}]"
        val = 0.0 if mid == base_mandi else float(p.get(key, np.nan))
        lo, hi = (0.0, 0.0) if mid == base_mandi else (float(ci.loc[key, 0]), float(ci.loc[key, 1]))
        rows.append(dict(kind="mandi", label=name, rs_vs_baseline=val,
                         ci_low=lo, ci_high=hi))

    coef_df = pd.DataFrame(rows)
    coef_df.to_csv(cfg.OUTPUTS / "model_coefficients.csv", index=False)

    arr = float(p["arrivals_dev"])
    print("\n--- Coefficients in plain language ---------------------------")
    print(f"Baseline: {base_name}, January.")
    print(f"Intercept: Rs {p['Intercept']:,.0f}/quintal\n")
    print("Month effects (Rs/quintal vs January, holding market and arrivals constant):")
    for r in rows[:12]:
        bar = "#" * int(abs(r["rs_vs_baseline"]) / 25)
        print(f"  {r['label']}: {r['rs_vs_baseline']:>+8,.0f}  {bar}")
    print(f"\nMarket effects (Rs/quintal vs {base_name}):")
    for r in rows[12:]:
        print(f"  {r['label']:<12}{r['rs_vs_baseline']:>+8,.0f}")
    print(f"\narrivals_dev: {arr:+.4f} Rs per extra quintal above the month's norm")
    print(f"  -> 1,000 quintals above normal for the month = Rs {arr*1000:+,.0f}/quintal")
    print(f"  -> p = {model.pvalues['arrivals_dev']:.4f}")
    return coef_df, base_name


def check_vif(train):
    X = pd.get_dummies(train[["arrivals_dev", "m", "mandi_id"]],
                       columns=["m", "mandi_id"], drop_first=True).astype(float)
    X.insert(0, "const", 1.0)
    v = pd.Series([variance_inflation_factor(X.values, i) for i in range(X.shape[1])],
                  index=X.columns).drop("const")
    return float(v["arrivals_dev"]), float(v.max())


def failure_analysis(test, pred_te, train, pred_tr):
    """Where does it break, and why."""
    t = test.copy()
    t["pred"] = pred_te
    t["err"] = t.modal_price - t.pred
    t["abs_err"] = t.err.abs()

    print("\n--- Failure analysis ------------------------------------------")

    by_month = (t.groupby("month_num")
                 .agg(n=("err", "size"), mean_price=("modal_price", "mean"),
                      mae=("abs_err", "mean"), bias=("err", "mean")))
    by_month.index = [MONTHS[i - 1] for i in by_month.index]
    print("\nTest-period error by month:")
    print(by_month.round(0).to_string())

    by_mandi = (t.groupby("mandi_name")
                 .agg(n=("err", "size"), mae=("abs_err", "mean"), bias=("err", "mean"))
                 .sort_values("mae", ascending=False))
    print("\nTest-period error by market:")
    print(by_mandi.round(0).to_string())

    # Performance on extreme prices -- the weeks that matter most.
    tr = train.copy()
    tr["pred"] = pred_tr
    tr["err"] = tr.modal_price - tr.pred
    hi = tr[tr.modal_price >= tr.modal_price.quantile(0.95)]
    lo = tr[tr.modal_price <= tr.modal_price.quantile(0.50)]
    print(f"\nTraining-period bias on the top 5% of prices: "
          f"Rs {hi.err.mean():+,.0f}/qtl (n={len(hi)})")
    print(f"Training-period bias on the bottom 50%:        "
          f"Rs {lo.err.mean():+,.0f}/qtl (n={len(lo)})")

    RESULTS["failure"] = dict(
        by_month=by_month.round(1).to_dict(),
        by_mandi=by_mandi.round(1).to_dict(),
        bias_top5pct=float(hi.err.mean()),
        bias_bottom50pct=float(lo.err.mean()),
        test_months=sorted(test.month_num.unique().tolist()),
    )
    return t, hi


def make_figures(train, test, pred_tr, pred_te, model, coef_df, t, hi):
    # M1: actual vs predicted over time
    fig, ax = plt.subplots(figsize=(9.5, 4))
    tr = train.assign(pred=pred_tr).groupby("price_date")[["modal_price", "pred"]].mean()
    te = test.assign(pred=pred_te).groupby("price_date")[["modal_price", "pred"]].mean()
    ax.plot(tr.index, tr.modal_price, color=MUTED, lw=0.7, alpha=0.8, label="Actual")
    ax.plot(tr.index, tr.pred, color=ACCENT, lw=1.3, label="Predicted")
    ax.plot(te.index, te.modal_price, color=MUTED, lw=0.7, alpha=0.8)
    ax.plot(te.index, te.pred, color=ACCENT, lw=1.3)
    ax.axvline(test.price_date.min(), color="black", ls="--", lw=1.2)
    ax.annotate("train | test", (test.price_date.min(), ax.get_ylim()[1] * 0.97),
                fontsize=8.5, ha="center")
    ax.set_ylabel("Modal price (₹/quintal)")
    ax.set_title("The model tracks the seasonal cycle but flattens the peaks",
                 loc="left", fontweight="bold")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout(); fig.savefig(FIGS / "m1_actual_vs_predicted.png", bbox_inches="tight")
    plt.close(fig)

    # M2: month coefficients
    fig, ax = plt.subplots(figsize=(7.5, 4))
    mc = coef_df[coef_df.kind == "month"]
    cols = [ACCENT if v > 0 else MUTED for v in mc.rs_vs_baseline]
    ax.bar(mc.label, mc.rs_vs_baseline, color=cols)
    ax.errorbar(mc.label, mc.rs_vs_baseline,
                yerr=[mc.rs_vs_baseline - mc.ci_low, mc.ci_high - mc.rs_vs_baseline],
                fmt="none", ecolor="black", elinewidth=0.8, capsize=2.5)
    ax.axhline(0, color="black", lw=0.9)
    ax.set_ylabel("₹/quintal vs January")
    ax.set_title("What each month is worth, holding market and arrivals constant",
                 loc="left", fontweight="bold")
    fig.tight_layout(); fig.savefig(FIGS / "m2_month_coefficients.png", bbox_inches="tight")
    plt.close(fig)

    # M3: residuals vs actual price -- the shrinkage toward the mean
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.9))
    ax = axes[0]
    allp = np.r_[train.modal_price.values, test.modal_price.values]
    alle = np.r_[(train.modal_price - pred_tr).values, (test.modal_price - pred_te).values]
    ax.scatter(allp, alle, s=4, alpha=0.15, color=MUTED)
    ax.axhline(0, color="black", lw=0.9)
    z = np.polyfit(allp, alle, 1)
    xs = np.linspace(allp.min(), allp.max(), 50)
    ax.plot(xs, np.polyval(z, xs), color=ACCENT, lw=2)
    ax.set_xlabel("Actual price (₹/quintal)")
    ax.set_ylabel("Residual (actual − predicted)")
    ax.set_title("Under-predicts high prices, over-predicts low",
                 loc="left", fontweight="bold")

    ax = axes[1]
    by_month = t.groupby("month_num").abs_err.mean()
    ax.bar([MONTHS[i - 1] for i in by_month.index], by_month.values, color=MUTED)
    ax.set_ylabel("Mean absolute error (₹/quintal)")
    ax.set_title("Test-period error by month", loc="left", fontweight="bold")
    fig.tight_layout(); fig.savefig(FIGS / "m3_residual_diagnostics.png", bbox_inches="tight")
    plt.close(fig)
    print("\nFigures -> m1_actual_vs_predicted, m2_month_coefficients, m3_residual_diagnostics")


def blocked_cv(d):
    """
    A single chronological split is honest about time-ordering but can be
    misleading about DIFFICULTY.

    Here the final 20% of the timeline is Dec 2025 - Jun 2026: the low-price
    half of the year, containing neither of the two shock episodes. Test
    price SD is Rs 275 against Rs 431 in training. The model therefore scores
    BETTER on test than on train (MAE Rs 54 vs Rs 104), which is not evidence
    of good generalisation -- it is evidence of an easy test period.

    Reporting that 4.8% MAPE as the headline would overstate the model badly.

    Blocked (expanding-window) CV fixes the diagnosis: train on everything up
    to a cut, test on the following block, roll the cut forward. Every fold
    still respects time order, but across folds the model is scored on high-
    price months and shock periods too. The spread ACROSS folds is the real
    measure of how much the answer depends on which season you test in.
    """
    folds, n = [], 5
    d = d.sort_values("price_date").reset_index(drop=True)
    dates = d.price_date
    start = dates.quantile(0.40)
    cuts = pd.date_range(start, dates.max(), periods=n + 1)[:-1]

    for cut in cuts:
        tr = d[d.price_date <= cut].copy()
        te = d[(d.price_date > cut) &
               (d.price_date <= cut + pd.Timedelta(days=90))].copy()
        if len(te) < 50 or tr.month_num.nunique() < 12:
            continue
        mm = tr.groupby("month_num").arrivals.mean()
        gm = tr.arrivals.mean()
        for part in (tr, te):
            part["arrivals_dev"] = part.arrivals - part.month_num.map(mm).fillna(gm)
        try:
            mdl = smf.ols("modal_price ~ arrivals_dev + C(m) + C(mandi_id)", tr).fit()
            pr = mdl.predict(te)
        except Exception:
            continue
        ok = pr.notna()
        if ok.sum() < 30:
            continue
        err = te.modal_price[ok] - pr[ok]
        folds.append(dict(
            cut=str(cut.date()),
            test_months=sorted(te.month_num.unique().tolist()),
            n=int(ok.sum()),
            mean_price=float(te.modal_price[ok].mean()),
            mae=float(err.abs().mean()),
            mape=float((err / te.modal_price[ok]).abs().mean() * 100),
            bias=float(err.mean()),
        ))

    print("\n--- Blocked time-series CV (the honest evaluation) -------------")
    cv = pd.DataFrame(folds)
    if len(cv):
        show = cv[["cut", "n", "mean_price", "mae", "mape", "bias"]].copy()
        print(show.round(1).to_string(index=False))
        print(f"\n  MAE  across folds: Rs {cv.mae.mean():,.0f} "
              f"(range Rs {cv.mae.min():,.0f} - Rs {cv.mae.max():,.0f})")
        print(f"  MAPE across folds: {cv.mape.mean():.1f}% "
              f"(range {cv.mape.min():.1f}% - {cv.mape.max():.1f}%)")
        RESULTS["blocked_cv"] = dict(
            folds=folds,
            mae_mean=float(cv.mae.mean()), mae_min=float(cv.mae.min()),
            mae_max=float(cv.mae.max()), mape_mean=float(cv.mape.mean()),
            mape_min=float(cv.mape.min()), mape_max=float(cv.mape.max()),
        )
    return cv


def main():
    d = build_features(load())
    train, test, cut = split(d)
    print(f"Chronological split at {cut.date()}")
    print(f"  train: {len(train):,} rows  {train.price_date.min().date()} -> {train.price_date.max().date()}")
    print(f"  test:  {len(test):,} rows  {test.price_date.min().date()} -> {test.price_date.max().date()}")
    print(f"  test months present: {sorted(test.month_num.unique())}")

    model, pred_tr, pred_te, m_tr, m_te = fit_and_evaluate(train, test)

    print("\n--- Fit -------------------------------------------------------")
    print(f"  train  MAE Rs {m_tr['mae']:,.0f}  RMSE Rs {m_tr['rmse']:,.0f}  "
          f"MAPE {m_tr['mape']:.1f}%  R2 {m_tr['r2']:.3f}")
    print(f"  test   MAE Rs {m_te['mae']:,.0f}  RMSE Rs {m_te['rmse']:,.0f}  "
          f"MAPE {m_te['mape']:.1f}%  R2 {m_te['r2']:.3f}")
    gap = 100 * (m_te["mae"] - m_tr["mae"]) / m_tr["mae"]
    print(f"  overfitting check: test MAE is {gap:+.1f}% vs train MAE")
    if gap < 0:
        print("  !! test error is LOWER than train error -- this is a warning, not a win.")
        print(f"     test price SD Rs {test.modal_price.std():,.0f} vs "
              f"train Rs {train.modal_price.std():,.0f}; test months = "
              f"{sorted(test.month_num.unique())} (no Aug/Oct peak).")
        print("     The single split lands on the easy half of the year.")
        print("     See blocked CV below for the evaluation that should be quoted.")

    vif_arr, vif_max = check_vif(train)
    print(f"  VIF: arrivals_dev {vif_arr:.2f}, max {vif_max:.2f}")

    coef_df, base_name = report_coefficients(model, train)
    blocked_cv(d)
    t, hi = failure_analysis(test, pred_te, train, pred_tr)
    make_figures(train, test, pred_tr, pred_te, model, coef_df, t, hi)

    RESULTS.update(dict(
        formula="modal_price ~ arrivals_dev + C(m) + C(mandi_id)",
        split_date=str(cut.date()), train=m_tr, test=m_te,
        overfit_gap_pct=float(gap), vif_arrivals_dev=vif_arr, vif_max=vif_max,
        arrivals_dev_coef=float(model.params["arrivals_dev"]),
        arrivals_dev_p=float(model.pvalues["arrivals_dev"]),
        baseline=base_name,
    ))
    (cfg.OUTPUTS / "model_results.json").write_text(json.dumps(RESULTS, indent=2))
    with open(cfg.OUTPUTS / "model_summary.txt", "w") as f:
        f.write(str(model.summary()))
    print("\nWrote model_results.json, model_coefficients.csv, model_summary.txt")


if __name__ == "__main__":
    main()
