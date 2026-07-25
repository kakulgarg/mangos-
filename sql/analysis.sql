-- =============================================================================
-- DeHaat Mandi Price Watch -- analysis queries
-- =============================================================================
-- Commodity: Onion | State: Maharashtra | 14 curated mandis | 2024-06-01 .. 2026-06-30
--
-- EXTENSIBILITY (Q6)
-- Scope lives in exactly one place: the `scope` CTE at the top of each query.
-- Adding an 11th mandi, a second commodity, or another year is a change to
-- those literals and nothing else. No query hardcodes a mandi_id, a commodity
-- name, or a date outside `scope`; every query joins through `base`, so a new
-- mandi flows into all six results automatically.
--
-- "The price" is modal_price throughout -- the price at which the largest
-- volume actually traded. min/max are the tails of the day's book and get
-- dragged around by small lots of unusually good or poor grade; the modal
-- price is what a typical farmer with a typical lot actually receives, which
-- is the quantity the advisory recommendation is about.
-- =============================================================================


-- =============================================================================
-- Q0. The shared foundation.
-- Defined once here for readability; each query below repeats it so that every
-- query is independently runnable (SQLite has no persistent CTE).
-- =============================================================================
--
--   WITH scope AS (
--       SELECT 'Onion'      AS commodity,
--              'Maharashtra' AS state,
--              '2024-06-01'  AS date_start,
--              '2026-06-30'  AS date_end
--   ),
--   base AS (
--       SELECT p.mandi_id, m.mandi_name, m.district,
--              p.price_date, p.commodity,
--              p.arrivals, p.modal_price
--       FROM daily_prices p
--       JOIN mandis m USING (mandi_id)
--       CROSS JOIN scope s
--       WHERE p.commodity  = s.commodity
--         AND m.state      = s.state
      AND m.is_curated = 1
--         AND p.price_date BETWEEN s.date_start AND s.date_end
--   )


-- =============================================================================
-- SOLID: joins + GROUP BY
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Q1. Average modal price and total arrivals per mandi, over the full window.
--     The "where should we sell" question in its simplest form: which markets
--     pay more on average, and how much volume do they absorb?
-- -----------------------------------------------------------------------------
WITH scope AS (
    SELECT 'Onion' AS commodity, 'Maharashtra' AS state,
           '2024-06-01' AS date_start, '2026-06-30' AS date_end
),
base AS (
    SELECT p.mandi_id, m.mandi_name, m.district, p.price_date,
           p.arrivals, p.modal_price
    FROM daily_prices p
    JOIN mandis m USING (mandi_id)
    CROSS JOIN scope s
    WHERE p.commodity = s.commodity
      AND m.state     = s.state
      AND m.is_curated = 1
      AND p.price_date BETWEEN s.date_start AND s.date_end
)
SELECT
    mandi_name,
    district,
    COUNT(*)                                   AS reporting_days,
    ROUND(AVG(modal_price), 0)                  AS avg_modal_price,
    ROUND(MIN(modal_price), 0)                  AS min_modal_price,
    ROUND(MAX(modal_price), 0)                  AS max_modal_price,
    ROUND(SUM(arrivals), 0)                     AS total_arrivals,
    ROUND(AVG(arrivals), 0)                     AS avg_daily_arrivals,
    -- Price premium of this mandi against the state-wide average, in %.
    -- This is the number a field agent actually uses: "Pune pays X% more."
    ROUND(100.0 * (AVG(modal_price) - (SELECT AVG(modal_price) FROM base))
          / (SELECT AVG(modal_price) FROM base), 1) AS pct_vs_state_avg
FROM base
GROUP BY mandi_id, mandi_name, district
ORDER BY avg_modal_price DESC;


-- -----------------------------------------------------------------------------
-- Q2. Average price by month, across all mandis. First look at seasonality.
--     Note: averaging raw daily rows lets the mandis that report most often
--     dominate the month. The `per_mandi_month` step averages within each
--     mandi first, so every market contributes equally to the seasonal shape.
--     Reporting frequency differs by ~6% across mandis, so this matters.
-- -----------------------------------------------------------------------------
WITH scope AS (
    SELECT 'Onion' AS commodity, 'Maharashtra' AS state,
           '2024-06-01' AS date_start, '2026-06-30' AS date_end
),
base AS (
    SELECT p.mandi_id, m.mandi_name, p.price_date, p.arrivals, p.modal_price
    FROM daily_prices p
    JOIN mandis m USING (mandi_id)
    CROSS JOIN scope s
    WHERE p.commodity = s.commodity
      AND m.state     = s.state
      AND m.is_curated = 1
      AND p.price_date BETWEEN s.date_start AND s.date_end
),
per_mandi_month AS (
    SELECT mandi_id,
           CAST(STRFTIME('%m', price_date) AS INTEGER) AS month_num,
           AVG(modal_price) AS mandi_month_price,
           AVG(arrivals)    AS mandi_month_arrivals
    FROM base
    GROUP BY mandi_id, month_num
)
SELECT
    month_num,
    CASE month_num
        WHEN 1 THEN 'Jan' WHEN 2 THEN 'Feb' WHEN 3 THEN 'Mar'
        WHEN 4 THEN 'Apr' WHEN 5 THEN 'May' WHEN 6 THEN 'Jun'
        WHEN 7 THEN 'Jul' WHEN 8 THEN 'Aug' WHEN 9 THEN 'Sep'
        WHEN 10 THEN 'Oct' WHEN 11 THEN 'Nov' ELSE 'Dec'
    END                                          AS month_name,
    COUNT(*)                                     AS mandis_reporting,
    ROUND(AVG(mandi_month_price), 0)             AS avg_modal_price,
    ROUND(AVG(mandi_month_arrivals), 0)          AS avg_daily_arrivals,
    -- Seasonal index: 100 = the annual average. Above 100 is a paying month.
    ROUND(100.0 * AVG(mandi_month_price)
          / (SELECT AVG(mandi_month_price) FROM per_mandi_month), 1)
                                                 AS seasonal_index
FROM per_mandi_month
GROUP BY month_num
ORDER BY month_num;


-- =============================================================================
-- STRONG: window functions + CTEs
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Q3. Rolling average price per mandi.
--
--     Window length: 7 days. Justified agriculturally, not arbitrarily -- it
--     matches a farmer's real decision horizon: harvest, arrange transport,
--     reach the mandi and sell, all inside roughly a week. A 30-day window
--     smooths away exactly the short-run movement a sell-timing decision
--     depends on.
--
--     ROWS (not RANGE) is deliberate: mandis do not report every calendar day
--     (the grid is 85% populated), so "the last 7 REPORTED days" is the
--     honest unit. A calendar-day window would silently shrink to 4-5
--     observations whenever a mandi went quiet.
-- -----------------------------------------------------------------------------
WITH scope AS (
    SELECT 'Onion' AS commodity, 'Maharashtra' AS state,
           '2024-06-01' AS date_start, '2026-06-30' AS date_end
),
base AS (
    SELECT p.mandi_id, m.mandi_name, p.price_date, p.arrivals, p.modal_price
    FROM daily_prices p
    JOIN mandis m USING (mandi_id)
    CROSS JOIN scope s
    WHERE p.commodity = s.commodity
      AND m.state     = s.state
      AND m.is_curated = 1
      AND p.price_date BETWEEN s.date_start AND s.date_end
)
SELECT
    mandi_name,
    price_date,
    modal_price,
    ROUND(AVG(modal_price) OVER w7, 0)  AS rolling_7d_price,
    ROUND(AVG(arrivals)    OVER w7, 0)  AS rolling_7d_arrivals,
    COUNT(*)               OVER w7      AS obs_in_window,
    -- How far today sits from its own 7-day trend, in %. A field agent reads
    -- a large positive number as "today is a spike, not the new level."
    ROUND(100.0 * (modal_price - AVG(modal_price) OVER w7)
          / AVG(modal_price) OVER w7, 1) AS pct_vs_7d_trend
FROM base
WINDOW w7 AS (
    PARTITION BY mandi_id
    ORDER BY price_date
    ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
)
ORDER BY mandi_name, price_date;


-- -----------------------------------------------------------------------------
-- Q4. Year-on-year price comparison for the same calendar period, per mandi.
--
--     Gap handling (the question APPROACH.md asks): comparison is at
--     (mandi, month) grain, not date-to-date. A missing day inside a month
--     shrinks that month's sample rather than voiding the comparison. The
--     `days_this_year` / `days_last_year` columns are returned so a thin
--     month is visible rather than hidden -- a month standing on 3 reported
--     days is not evidence, and the reader can see that directly.
-- -----------------------------------------------------------------------------
WITH scope AS (
    SELECT 'Onion' AS commodity, 'Maharashtra' AS state,
           '2024-06-01' AS date_start, '2026-06-30' AS date_end
),
base AS (
    SELECT p.mandi_id, m.mandi_name, p.price_date, p.arrivals, p.modal_price
    FROM daily_prices p
    JOIN mandis m USING (mandi_id)
    CROSS JOIN scope s
    WHERE p.commodity = s.commodity
      AND m.state     = s.state
      AND m.is_curated = 1
      AND p.price_date BETWEEN s.date_start AND s.date_end
),
monthly AS (
    SELECT mandi_id, mandi_name,
           CAST(STRFTIME('%Y', price_date) AS INTEGER) AS yr,
           CAST(STRFTIME('%m', price_date) AS INTEGER) AS month_num,
           AVG(modal_price) AS avg_price,
           AVG(arrivals)    AS avg_arrivals,
           COUNT(*)         AS reporting_days
    FROM base
    GROUP BY mandi_id, mandi_name, yr, month_num
)
SELECT
    mandi_name,
    yr,
    month_num,
    ROUND(avg_price, 0)                                   AS avg_price,
    ROUND(LAG(avg_price) OVER yoy, 0)                     AS avg_price_last_year,
    ROUND(avg_price - LAG(avg_price) OVER yoy, 0)         AS yoy_change_rs,
    ROUND(100.0 * (avg_price - LAG(avg_price) OVER yoy)
          / LAG(avg_price) OVER yoy, 1)                   AS yoy_change_pct,
    reporting_days                                        AS days_this_year,
    LAG(reporting_days) OVER yoy                          AS days_last_year
FROM monthly
WINDOW yoy AS (PARTITION BY mandi_id, month_num ORDER BY yr)
ORDER BY mandi_name, month_num, yr;


-- -----------------------------------------------------------------------------
-- Q5. Seasonal pattern per mandi, built with CTEs.
--
--     Resolution: month, not week-of-year. A farmer decides "sell in March or
--     hold to May", not "sell in week 11". Week-of-year also splits 2-3 years
--     of data into ~52 buckets per mandi, leaving each bucket standing on a
--     handful of observations -- noise dressed as precision.
--
--     Each mandi's months are indexed against that mandi's OWN annual average,
--     so the output is comparable across markets that sit at different price
--     levels. Pune being expensive year-round is a Q1 finding; Q5 is about
--     WHEN each market peaks.
-- -----------------------------------------------------------------------------
WITH scope AS (
    SELECT 'Onion' AS commodity, 'Maharashtra' AS state,
           '2024-06-01' AS date_start, '2026-06-30' AS date_end
),
base AS (
    SELECT p.mandi_id, m.mandi_name, p.price_date, p.arrivals, p.modal_price
    FROM daily_prices p
    JOIN mandis m USING (mandi_id)
    CROSS JOIN scope s
    WHERE p.commodity = s.commodity
      AND m.state     = s.state
      AND m.is_curated = 1
      AND p.price_date BETWEEN s.date_start AND s.date_end
),
mandi_month AS (
    SELECT mandi_id, mandi_name,
           CAST(STRFTIME('%m', price_date) AS INTEGER) AS month_num,
           AVG(modal_price) AS avg_price,
           AVG(arrivals)    AS avg_arrivals,
           COUNT(*)         AS n_obs
    FROM base
    GROUP BY mandi_id, mandi_name, month_num
),
mandi_baseline AS (
    SELECT mandi_id, AVG(avg_price) AS annual_avg_price
    FROM mandi_month
    GROUP BY mandi_id
)
SELECT
    mm.mandi_name,
    mm.month_num,
    ROUND(mm.avg_price, 0)                                    AS avg_price,
    ROUND(mm.avg_arrivals, 0)                                 AS avg_arrivals,
    mm.n_obs,
    -- 100 = this mandi's own annual average.
    ROUND(100.0 * mm.avg_price / mb.annual_avg_price, 1)      AS seasonal_index,
    -- Rank of this month within this mandi: 1 = best-paying month here.
    RANK() OVER (PARTITION BY mm.mandi_id ORDER BY mm.avg_price DESC)
                                                              AS month_rank,
    -- Gain from selling in this month vs this mandi's worst month, in rupees
    -- per quintal. This is the number that goes in front of a farmer.
    ROUND(mm.avg_price - MIN(mm.avg_price) OVER (PARTITION BY mm.mandi_id), 0)
                                                              AS rs_above_worst_month
FROM mandi_month mm
JOIN mandi_baseline mb USING (mandi_id)
ORDER BY mm.mandi_name, mm.month_num;


-- =============================================================================
-- STANDOUT: structured so another analyst could extend it
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Q6. Extensibility check, run as an actual query rather than asserted in prose.
--
--     Returns one row per (commodity, mandi) present under the current scope,
--     with coverage diagnostics. Point `scope` at a second commodity or an
--     11th mandi and this -- and every query above -- returns it with no
--     structural edit, because nothing downstream of `base` names a mandi or
--     a commodity.
--
--     It doubles as the pre-flight check before trusting any result: a mandi
--     with 40% coverage or a 200-day gap should not carry a recommendation,
--     and this surfaces that before the modelling does.
-- -----------------------------------------------------------------------------
WITH scope AS (
    SELECT 'Onion' AS commodity, 'Maharashtra' AS state,
           '2024-06-01' AS date_start, '2026-06-30' AS date_end
),
base AS (
    SELECT p.mandi_id, m.mandi_name, p.commodity, p.price_date,
           p.arrivals, p.modal_price
    FROM daily_prices p
    JOIN mandis m USING (mandi_id)
    CROSS JOIN scope s
    WHERE p.commodity = s.commodity
      AND m.state     = s.state
      AND m.is_curated = 1
      AND p.price_date BETWEEN s.date_start AND s.date_end
),
span AS (
    SELECT JULIANDAY(MAX(price_date)) - JULIANDAY(MIN(price_date)) + 1 AS total_days
    FROM base
),
-- A window function cannot be nested directly inside an aggregate, so the
-- day-to-day gap is computed first and aggregated in a second step.
day_gaps AS (
    SELECT mandi_id,
           JULIANDAY(price_date)
             - JULIANDAY(LAG(price_date) OVER (PARTITION BY mandi_id
                                               ORDER BY price_date)) AS gap_days
    FROM base
),
gaps AS (
    SELECT mandi_id, MAX(gap_days) AS longest_gap_days
    FROM day_gaps
    GROUP BY mandi_id
)
SELECT
    b.commodity,
    b.mandi_name,
    COUNT(*)                                                  AS reporting_days,
    ROUND(100.0 * COUNT(*) / (SELECT total_days FROM span), 1) AS pct_coverage,
    CAST(g.longest_gap_days AS INTEGER)                        AS longest_gap_days,
    MIN(b.price_date)                                          AS first_report,
    MAX(b.price_date)                                          AS last_report,
    SUM(b.modal_price IS NULL)                                 AS null_prices,
    SUM(b.arrivals IS NULL)                                    AS null_arrivals,
    -- Blocks a market from carrying a recommendation on thin evidence.
    CASE WHEN 100.0 * COUNT(*) / (SELECT total_days FROM span) < 60
              THEN 'EXCLUDE - coverage too thin'
         WHEN g.longest_gap_days > 45
              THEN 'CAUTION - long reporting gap'
         ELSE 'OK'
    END                                                        AS usability
FROM base b
JOIN gaps g USING (mandi_id)
GROUP BY b.commodity, b.mandi_id, b.mandi_name, g.longest_gap_days
ORDER BY b.commodity, pct_coverage DESC;


-- =============================================================================
-- STANDOUT (variety): which onion category pays best, and when
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Q7. Average price by variety and month, on curated markets.
--     Answers "which category of onion pays best, in which month". Uses the
--     variety-grain cleaned table. n_obs travels with every cell so a thin
--     variety-month is visible rather than hidden.
-- -----------------------------------------------------------------------------
SELECT
    v.variety_group                              AS variety,
    v.month_num,
    CASE v.month_num
        WHEN 1 THEN 'Jan' WHEN 2 THEN 'Feb' WHEN 3 THEN 'Mar'
        WHEN 4 THEN 'Apr' WHEN 5 THEN 'May' WHEN 6 THEN 'Jun'
        WHEN 7 THEN 'Jul' WHEN 8 THEN 'Aug' WHEN 9 THEN 'Sep'
        WHEN 10 THEN 'Oct' WHEN 11 THEN 'Nov' ELSE 'Dec'
    END                                          AS month_name,
    COUNT(*)                                     AS n_obs,
    ROUND(AVG(v.modal_price), 0)                 AS avg_modal_price,
    ROUND(MIN(v.modal_price), 0)                 AS min_modal_price,
    ROUND(MAX(v.modal_price), 0)                 AS max_modal_price
FROM daily_prices_variety v
WHERE v.is_curated = 1
GROUP BY v.variety_group, v.month_num
ORDER BY v.variety_group, v.month_num;
