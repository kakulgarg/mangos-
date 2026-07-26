"""
Step 3 -- Clean the data.

Reads daily_prices (grain: mandi x date x variety) AS SOURCED from the database,
applies each cleaning rule, and writes:

  daily_prices_clean    grain mandi x date  (arrivals-weighted across varieties)
                        + calendar & rolling features -- feeds EDA, the
                        explanatory model, and the forecaster.
  daily_prices_variety  grain mandi x date x variety (cleaned) -- feeds the
                        "which variety pays best" dashboard drill-down.

Design principle: every rule is chosen against evidence gathered from THIS
data. Where a verdict is asserted (e.g. "missingness is random"), it is now
COMPUTED from a statistic and a documented threshold, so an audit line can
actually fail. Nothing is silently dropped; every removal is counted and
written to outputs/cleaning_audit.json.
"""

from __future__ import annotations

import json
import sqlite3

import numpy as np
import pandas as pd

import config as C
from logging_config import get_logger

log = get_logger(__name__)
AUDIT: dict = {}


def record(step: str, **kw) -> None:
    AUDIT[step] = kw
    log.info("[%s] %s", step, "  ".join(f"{k}={v}" for k, v in kw.items()))


# --- C1. Duplicate (mandi, date, variety) keys ------------------------------

def resolve_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """Drop exact repeats; average any genuinely conflicting duplicates."""
    key = ["mandi_id", "price_date", "variety"]
    val = ["arrivals", "min_price", "max_price", "modal_price"]
    dup_mask = df.duplicated(key, keep=False)
    n_dup_rows = int(dup_mask.sum())
    if n_dup_rows:
        spread = df[dup_mask].groupby(key)[val].nunique().max(axis=1)
        n_conflicting = int((spread > 1).sum())
    else:
        n_conflicting = 0

    deduped = df.drop_duplicates(key + val, keep="first")
    if n_conflicting:
        out = deduped.groupby(key, as_index=False).agg(
            arrivals=("arrivals", "mean"), min_price=("min_price", "mean"),
            max_price=("max_price", "mean"), modal_price=("modal_price", "mean"),
            commodity=("commodity", "first"))
        rule = "drop_exact_then_mean_conflicting"
    else:
        out = deduped.copy()
        rule = "drop_exact_duplicates"
    record("C1_duplicates", duplicate_rows=n_dup_rows, conflicting=n_conflicting,
           rule=rule, rows_before=len(df), rows_after=len(out))
    return out


# --- C2. Impossible and internally inconsistent values ----------------------

def flag_impossible(df: pd.DataFrame) -> pd.DataFrame:
    n0 = len(df)
    bad_price = ~df.modal_price.between(C.PRICE_MIN, C.PRICE_MAX)
    bad_arr = ~df.arrivals.between(C.ARRIVALS_MIN, C.ARRIVALS_MAX)
    bad_order = df.min_price > df.max_price
    bad_modal = (df.modal_price < df.min_price) | (df.modal_price > df.max_price)
    null_key = df.modal_price.isna() | df.price_date.isna()
    bad = bad_price | bad_arr | bad_order | bad_modal | null_key
    out = df[~bad].copy()
    record("C2_impossible", price_out_of_range=int(bad_price.sum()),
           arrivals_out_of_range=int(bad_arr.sum()), min_gt_max=int(bad_order.sum()),
           modal_outside_min_max=int(bad_modal.sum()), null_price_or_date=int(null_key.sum()),
           rows_removed=int(n0 - len(out)))
    return out


# --- C3. Unit consistency (computed verdict) --------------------------------

def check_units(df: pd.DataFrame) -> pd.DataFrame:
    med = df.groupby("mandi_id").modal_price.median()
    overall = df.modal_price.median()
    ratio = (med / overall)
    suspect = ratio[(ratio > 5) | (ratio < 0.2)]
    verdict = "no unit mismatch" if suspect.empty else f"{len(suspect)} suspect market(s)"
    record("C3_units", state_median_price=round(float(overall), 1),
           mandi_ratio_min=round(float(ratio.min()), 2),
           mandi_ratio_max=round(float(ratio.max()), 2),
           suspected_unit_mismatch=int(len(suspect)), verdict=verdict)
    return df


# --- C4. Reporting gaps (verdict computed from a dispersion statistic) -------

def assess_gaps(df: pd.DataFrame, curated_ids: set | None = None) -> pd.DataFrame:
    # Gaps are only meaningful for the markets we actually recommend on; sparse
    # tail markets would otherwise dominate a whole-population coverage figure.
    # NB: this is an ASSESSMENT step -- it measures on the curated subset but
    # returns the full frame untouched (see main).
    scoped = df[df.mandi_id.isin(curated_ids)] if curated_ids else df
    u = scoped.drop_duplicates(["mandi_id", "price_date"]).copy()
    u["price_date"] = pd.to_datetime(u.price_date)
    span = pd.date_range(u.price_date.min(), u.price_date.max())
    n_mandis = u.mandi_id.nunique()
    coverage = len(u) / (n_mandis * len(span))
    gaps = (u.sort_values("price_date").groupby("mandi_id")
              .price_date.diff().dt.days.dropna())

    grid = pd.MultiIndex.from_product(
        [u.mandi_id.unique(), span], names=["mandi_id", "price_date"]).to_frame(index=False)
    merged = grid.merge(u[["mandi_id", "price_date"]].assign(seen=1),
                        on=["mandi_id", "price_date"], how="left")
    merged["missing"] = merged.seen.isna()
    by_dow = merged.groupby(merged.price_date.dt.dayofweek).missing.mean()
    by_month = merged.groupby(merged.price_date.dt.month).missing.mean()

    # Verdict rule: missingness is "approximately random" if its relative spread
    # (coefficient of variation) across weekdays AND months is small. Weekend
    # closure is expected and excluded from the weekday test.
    wd = by_dow.loc[by_dow.index <= 4]      # Mon-Fri only
    cv_dow = float(wd.std() / wd.mean()) if wd.mean() else np.nan
    cv_month = float(by_month.std() / by_month.mean()) if by_month.mean() else np.nan
    random_like = (cv_dow < 0.25) and (cv_month < 0.25)
    verdict = ("approximately random (weekday+month); monthly means unbiased"
               if random_like else
               "NON-random; monthly means may be biased -- weight by n_obs")
    record("C4_gaps", rule="leave (no interpolation)",
           grid_coverage_pct=round(100 * coverage, 1),
           longest_gap_days=int(gaps.max()), mean_gap_days=round(float(gaps.mean()), 2),
           cv_missing_weekday=round(cv_dow, 3), cv_missing_month=round(cv_month, 3),
           missingness_verdict=verdict)
    return df


# --- C5. Outliers: measured, retained ---------------------------------------

def assess_outliers(df: pd.DataFrame) -> pd.DataFrame:
    z = df.groupby("mandi_id").modal_price.transform(
        lambda s: (s - s.mean()) / s.std(ddof=0))
    extreme = z.abs() > 3
    record("C5_outliers", action="retained (not winsorised)",
           beyond_3sd=int(extreme.sum()), pct_of_rows=round(100 * float(extreme.mean()), 2),
           p99_price=round(float(df.modal_price.quantile(0.99)), 0),
           max_price=round(float(df.modal_price.max()), 0),
           rationale="price spikes are the signal, not noise")
    return df


# --- Variety folding + aggregation ------------------------------------------

def fold_varieties(df: pd.DataFrame) -> pd.DataFrame:
    """Keep the economically distinct varieties; fold the rest into 'Other'."""
    df = df.copy()
    df["variety_grp"] = np.where(df.variety.isin(C.KEY_VARIETIES), df.variety, "Other")
    return df


def aggregate_to_mandi_day(df: pd.DataFrame) -> pd.DataFrame:
    """Collapse varieties to one arrivals-weighted price per mandi-day."""
    def agg(g):
        w = g.arrivals.fillna(0)
        w = w if w.sum() > 0 else pd.Series(1.0, index=g.index)
        modal = float((g.modal_price * w).sum() / w.sum())
        return pd.Series({
            "arrivals": g.arrivals.sum(min_count=1),
            "min_price": g.min_price.min(),
            "max_price": g.max_price.max(),
            "modal_price": modal,
            "n_varieties": g.variety.nunique(),
            "variety_spread_pct": round(
                100 * (g.modal_price.max() - g.modal_price.min()) / g.modal_price.mean(), 1)
                if len(g) > 1 and g.modal_price.mean() > 0 else 0.0,
        })
    out = (df.groupby(["mandi_id", "price_date", "commodity"], as_index=False)
             .apply(agg, include_groups=False).reset_index(drop=True))
    return out


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["price_date"] = pd.to_datetime(df.price_date)
    df["year"] = df.price_date.dt.year
    df["month_num"] = df.price_date.dt.month
    df["month_name"] = df.month_num.map(lambda i: C.MONTHS[i - 1])
    df["week_of_year"] = df.price_date.dt.isocalendar().week.astype(int)
    df["day_of_week"] = df.price_date.dt.dayofweek
    df = df.sort_values(["mandi_id", "price_date"])
    w = C.ROLLING_WINDOW_DAYS
    df["rolling_7d_price"] = (df.groupby("mandi_id").modal_price
                              .transform(lambda s: s.rolling(w, min_periods=1).mean()))
    df["rolling_7d_arrivals"] = (df.groupby("mandi_id").arrivals
                                 .transform(lambda s: s.rolling(w, min_periods=1).mean()))
    return df


def main() -> None:
    with sqlite3.connect(C.DB_PATH) as con:
        raw = pd.read_sql("SELECT * FROM daily_prices", con)
        mandis = pd.read_sql("SELECT * FROM mandis", con)
        log.info("Loaded %d rows as sourced (mandi x date x variety)", len(raw))

        curated_ids = set(mandis.loc[mandis.is_curated == 1, "mandi_id"])
        df = resolve_duplicates(raw)
        df = flag_impossible(df)
        df = check_units(df)
        df = assess_gaps(df, curated_ids)
        df = assess_outliers(df)
        df = fold_varieties(df)

        # Variety-grain cleaned table (dashboard drill-down).
        variety_tbl = add_features(df.rename(columns={"variety_grp": "variety_group"}))
        variety_tbl = variety_tbl.merge(mandis, on="mandi_id", how="left")

        # Mandi-day aggregate (EDA / model / forecast).
        agg = aggregate_to_mandi_day(df)
        agg = add_features(agg).merge(mandis, on="mandi_id", how="left")

        record("SUMMARY", rows_in=len(raw), variety_rows=len(variety_tbl),
                mandi_day_rows=len(agg), mandis=int(agg.mandi_id.nunique()),
                curated=int(mandis.is_curated.sum()),
                date_min=str(agg.price_date.min().date()),
                date_max=str(agg.price_date.max().date()))

        agg.to_sql("daily_prices_clean", con, if_exists="replace", index=False)
        variety_tbl.to_sql("daily_prices_variety", con, if_exists="replace", index=False)
        con.commit()

    C.PROCESSED.mkdir(parents=True, exist_ok=True)
    agg.to_csv(C.PROCESSED / "daily_prices_clean.csv", index=False)
    variety_tbl.to_csv(C.PROCESSED / "daily_prices_variety.csv", index=False)
    C.OUTPUTS.mkdir(parents=True, exist_ok=True)
    (C.OUTPUTS / "cleaning_audit.json").write_text(
        json.dumps(AUDIT, indent=2, default=str), encoding="utf-8")
    log.info("Wrote daily_prices_clean (%d) + daily_prices_variety (%d) + audit",
             len(agg), len(variety_tbl))


if __name__ == "__main__":
    main()
