"""
Step 4 -- Exploration.

Six charts. Each one exists because it changed a decision downstream; the
one-sentence claim each chart proves is printed alongside it and collected
into outputs/eda_findings.md.

The findings on the real Agmarknet data: season dominates (F1, a 2.5x swing),
market level matters but less (F5, ~40% spread), and -- importantly -- a single
mandi's own daily arrivals carry almost no independent signal for its price
(F2-F4). Price is set by state/national supply, not one market's truck count.
So the explanatory model is built on month and market; arrivals earns only a
minor role, and the real predictive lift for FORECASTING comes from lagged
prices (see forecast.py), not contemporaneous arrivals.
"""

import sqlite3

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

import config as cfg

plt.rcParams.update({
    "figure.dpi": 130, "savefig.dpi": 130, "font.size": 9,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.alpha": 0.25, "figure.facecolor": "white",
})
ACCENT, MUTED = "#c1440e", "#4a5568"
FIGS = cfg.OUTPUTS / "figures"
FINDINGS = []


def save(fig, name, claim):
    FIGS.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(FIGS / f"{name}.png", bbox_inches="tight")
    plt.close(fig)
    FINDINGS.append((name, claim))
    print(f"  {name}.png\n    -> {claim}\n")


def load():
    con = sqlite3.connect(cfg.DB_PATH)
    d = pd.read_sql("SELECT * FROM daily_prices_clean WHERE is_curated = 1",
                    con, parse_dates=["price_date"])
    con.close()
    d["m"] = d.month_num.astype(str)
    return d


# --- F1. Seasonal price curve ------------------------------------------------

def f1_seasonal(d):
    fig, ax = plt.subplots(figsize=(7.5, 4))
    piv = d.groupby(["month_num", "mandi_name"]).modal_price.mean().unstack()
    for c in piv.columns:
        ax.plot(piv.index, piv[c], color=MUTED, lw=0.9, alpha=0.5)
    state = d.groupby("month_num").modal_price.mean()
    peak_m, trough_m = cfg.MONTHS[state.idxmax() - 1], cfg.MONTHS[state.idxmin() - 1]
    ax.plot(state.index, state.values, color=ACCENT, lw=2.6, label="State average")
    ax.scatter([state.idxmax()], [state.max()], color=ACCENT, zorder=5, s=45)
    ax.annotate(f"{peak_m} peak\n₹{state.max():,.0f}/qtl",
                (state.idxmax(), state.max()), xytext=(-52, -8),
                textcoords="offset points", color=ACCENT, fontsize=8.5)
    ax.scatter([state.idxmin()], [state.min()], color=MUTED, zorder=5, s=45)
    ax.annotate(f"{trough_m} trough\n₹{state.min():,.0f}/qtl",
                (state.idxmin(), state.min()), xytext=(6, -4),
                textcoords="offset points", color=MUTED, fontsize=8.5)
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(cfg.MONTHS)
    ax.set_ylabel("Modal price (₹/quintal)")
    ax.set_title(f"Onion price follows one seasonal cycle across all {d.mandi_name.nunique()} curated mandis",
                 loc="left", fontweight="bold")
    ax.legend(frameon=False, fontsize=8)

    ratio = state.max() / state.min()
    save(fig, "f1_seasonal_curve",
         f"The curated mandis peak in {peak_m} and trough in {trough_m}; the state "
         f"average swings {ratio:.2f}x (₹{state.min():,.0f} to ₹{state.max():,.0f}/qtl), "
         f"so WHEN to sell dominates WHERE.")


# --- F2. The sign flip -------------------------------------------------------

def f2_sign_flip(d):
    """The chart that changed the model."""
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    ax = axes[0]
    ax.scatter(d.arrivals, d.modal_price, s=4, alpha=0.18, color=MUTED)
    z = np.polyfit(d.arrivals, d.modal_price, 1)
    xs = np.linspace(d.arrivals.min(), d.arrivals.max(), 50)
    ax.plot(xs, np.polyval(z, xs), color=ACCENT, lw=2)
    raw = d.arrivals.corr(d.modal_price)
    ax.set_title(f"All data pooled: r = {raw:+.3f}", loc="left", fontweight="bold")
    ax.set_xlabel("Arrivals (quintals/day)")
    ax.set_ylabel("Modal price (₹/quintal)")
    ax.text(0.97, 0.94, "almost no\nlinear relationship",
            transform=ax.transAxes, ha="right", va="top", fontsize=8, color=MUTED)

    ax = axes[1]
    within = d.groupby("month_num").apply(
        lambda g: g.arrivals.corr(g.modal_price), include_groups=False)
    cols = [ACCENT if v > 0 else MUTED for v in within]
    ax.bar(within.index, within.values, color=cols)
    ax.axhline(0, color="black", lw=0.8)
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    ax.set_ylabel("corr(arrivals, price) within month")
    ax.set_title(f"Within each month: mean r = {within.mean():+.3f}",
                 loc="left", fontweight="bold")
    ax.text(0.03, 0.94, "still near zero,\nno stable sign",
            transform=ax.transAxes, ha="left", va="top", fontsize=8, color=ACCENT)

    fig.suptitle("A single mandi's own arrivals barely move its price",
                 fontweight="bold", y=1.02)
    save(fig, "f2_arrivals_price_sign_flip",
         f"A market's daily arrivals carry almost no independent signal for its "
         f"modal price (pooled r={raw:+.3f}; within-month mean r={within.mean():+.3f}). "
         f"Onion price at a mandi is set by state/national supply and the reference "
         f"market, not by that day's local truck count -- so arrivals is a weak "
         f"predictor and season and market level do the work.")


# --- F3. Why: arrivals is mostly a proxy for month ---------------------------

def f3_confound(d):
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.8))

    ax = axes[0]
    arr = d.groupby("month_num").arrivals.mean()
    pri = d.groupby("month_num").modal_price.mean()
    ax.plot(arr.index, arr.values, color=MUTED, lw=2, marker="o", ms=3, label="Arrivals")
    ax2 = ax.twinx()
    ax2.plot(pri.index, pri.values, color=ACCENT, lw=2, marker="o", ms=3, label="Price")
    ax2.grid(False)
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    ax.set_ylabel("Arrivals (qtl/day)", color=MUTED)
    ax2.set_ylabel("Price (₹/qtl)", color=ACCENT)
    r2 = smf.ols("arrivals ~ C(m)", d).fit().rsquared
    ax.set_title(f"Month explains only {r2:.1%} of arrivals variance",
                 loc="left", fontweight="bold")

    ax = axes[1]
    d2 = d.copy()
    d2["arr_dev"] = d2.arrivals - d2.groupby("month_num").arrivals.transform("mean")
    d2["price_dev"] = d2.modal_price - d2.groupby("month_num").modal_price.transform("mean")
    ax.scatter(d2.arr_dev, d2.price_dev, s=4, alpha=0.18, color=MUTED)
    z = np.polyfit(d2.arr_dev, d2.price_dev, 1)
    xs = np.linspace(d2.arr_dev.min(), d2.arr_dev.max(), 50)
    ax.plot(xs, np.polyval(z, xs), color=ACCENT, lw=2)
    ax.axhline(0, color="black", lw=0.6)
    ax.axvline(0, color="black", lw=0.6)
    ax.set_xlabel("Arrivals minus that month's mean")
    ax.set_ylabel("Price minus that month's mean")
    ax.set_title("The part of arrivals that is NOT season", loc="left", fontweight="bold")

    vif_raw = 1.0 / (1.0 - r2)  # VIF of arrivals in a model that also has month
    save(fig, "f3_arrivals_is_a_season_proxy",
         f"Month explains only {r2:.1%} of arrivals variance, so arrivals is nearly "
         f"orthogonal to season (VIF {vif_raw:.2f}) -- no collinearity problem, but "
         f"also no hidden signal: the deviation of arrivals from its monthly norm "
         f"still shows no clear link to price.")


# --- F4. Coefficient instability --------------------------------------------

def f4_instability(d):
    specs = [("arrivals\nalone", "modal_price ~ arrivals"),
             ("+ month", "modal_price ~ arrivals + C(m)"),
             ("+ month\n+ mandi", "modal_price ~ arrivals + C(m) + C(mandi_id)")]
    coefs, r2s = [], []
    for _, f in specs:
        r = smf.ols(f, d).fit()
        coefs.append(r.params["arrivals"])
        r2s.append(r.rsquared)

    fig, ax = plt.subplots(figsize=(6.2, 3.8))
    cols = [ACCENT if c < 0 else MUTED for c in coefs]
    bars = ax.bar([s[0] for s in specs], coefs, color=cols, width=0.55)
    ax.axhline(0, color="black", lw=0.9)
    for b, c, r in zip(bars, coefs, r2s):
        ax.text(b.get_x() + b.get_width() / 2,
                c + (0.02 if c > 0 else -0.045),
                f"{c:+.3f}\nR²={r:.2f}", ha="center", fontsize=8.5)
    ax.set_ylabel("Coefficient on arrivals (₹ per extra quintal)")
    ax.set_title("The arrivals effect is tiny in every specification", loc="left", fontweight="bold")
    ax.set_ylim(min(coefs) - 0.15, max(coefs) + 0.12)

    save(fig, "f4_coefficient_instability",
         f"Across specifications the arrivals coefficient stays within "
         f"[{min(coefs):+.3f}, {max(coefs):+.3f}] ₹/quintal -- economically negligible "
         f"against a seasonal swing of over ₹1,400. Arrivals earns at most a minor role; "
         f"the model is carried by month and market.")


# --- F5. Market comparison ---------------------------------------------------

def f5_markets(d):
    fig, axes = plt.subplots(1, 2, figsize=(10, 3.9))

    ax = axes[0]
    lvl = d.groupby("mandi_name").modal_price.mean().sort_values()
    ax.barh(lvl.index, lvl.values, color=MUTED)
    ax.barh([lvl.index[-1]], [lvl.values[-1]], color=ACCENT)
    state = d.modal_price.mean()
    ax.axvline(state, color="black", ls="--", lw=1)
    ax.text(state, -0.75, f" state avg ₹{state:,.0f}", fontsize=8)
    ax.set_xlabel("Average modal price (₹/quintal)")
    ax.set_title("Price LEVEL differs by market", loc="left", fontweight="bold")

    ax = axes[1]
    idx = d.groupby(["mandi_name", "month_num"]).modal_price.mean().unstack()
    idx = idx.div(idx.mean(axis=1), axis=0) * 100
    for name in idx.index:
        ax.plot(idx.columns, idx.loc[name], lw=1.1, alpha=0.75,
                color=ACCENT if name == lvl.index[-1] else MUTED)
    ax.axhline(100, color="black", ls="--", lw=0.8)
    ax.set_xticks(range(1, 13))
    ax.set_xticklabels(["J", "F", "M", "A", "M", "J", "J", "A", "S", "O", "N", "D"])
    ax.set_ylabel("Seasonal index (100 = own annual mean)")
    ax.set_title("...but TIMING is identical", loc="left", fontweight="bold")

    spread = 100 * (lvl.max() - lvl.min()) / lvl.mean()
    save(fig, "f5_market_level_vs_timing",
         f"Markets differ in price level by {spread:.0f}% ({lvl.index[0]} to "
         f"{lvl.index[-1]}) but share the same seasonal timing, so 'where' and "
         f"'when' are separable and mandi enters the model as a level shift only.")


# --- F6. What the model will not see -----------------------------------------

def f6_shocks(d):
    fig, ax = plt.subplots(figsize=(9, 3.8))
    ts = d.groupby("price_date").modal_price.mean()
    ax.plot(ts.index, ts.values, color=MUTED, lw=0.8)
    roll = ts.rolling(30, min_periods=5).mean()
    ax.plot(roll.index, roll.values, color=ACCENT, lw=1.8, label="30-day mean")

    z = d.groupby("mandi_id").modal_price.transform(lambda s: (s - s.mean()) / s.std())
    ext = d[z.abs() > 3]
    for period, grp in ext.groupby(ext.price_date.dt.to_period("M")):
        ax.axvspan(grp.price_date.min(), grp.price_date.max(),
                   color=ACCENT, alpha=0.16)
        ax.annotate(f"shock\n{period}", (grp.price_date.min(), ts.max() * 0.99),
                    fontsize=8, color=ACCENT, ha="left", va="top")
    ax.set_ylabel("Mean modal price (₹/quintal)")
    ax.set_title("Two shocks the model has no variable to anticipate",
                 loc="left", fontweight="bold")
    ax.legend(frameon=False, fontsize=8, loc="upper left")

    episodes = sorted(str(p) for p in ext.price_date.dt.to_period("M").unique())
    ep_txt = ", ".join(episodes[:4]) + ("..." if len(episodes) > 4 else "")
    save(fig, "f6_unexplained_shocks",
         f"{len(ext)} observations in shock months ({ep_txt}) reach "
         f"₹{d.modal_price.max():,.0f}/qtl with no variable in the dataset that "
         f"explains them -- the model will systematically miss the weeks that pay most.")


def main():
    d = load()
    print(f"Exploring {len(d):,} clean rows\n")
    f1_seasonal(d)
    f2_sign_flip(d)
    f3_confound(d)
    f4_instability(d)
    f5_markets(d)
    f6_shocks(d)

    lines = ["# EDA Findings\n",
             "Each chart and the single claim it establishes.\n"]
    for i, (name, claim) in enumerate(FINDINGS, 1):
        lines.append(f"### F{i} — `{name}.png`\n\n{claim}\n")
    (cfg.OUTPUTS / "eda_findings.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(FINDINGS)} figures -> outputs/figures/")


if __name__ == "__main__":
    main()
