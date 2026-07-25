# EDA Findings

Each chart and the single claim it establishes.

### F1 — `f1_seasonal_curve.png`

The curated mandis peak in Nov and trough in May; the state average swings 2.50x (₹991 to ₹2,475/qtl), so WHEN to sell dominates WHERE.

### F2 — `f2_arrivals_price_sign_flip.png`

A market's daily arrivals carry almost no independent signal for its modal price (pooled r=-0.033; within-month mean r=+0.072). Onion price at a mandi is set by state/national supply and the reference market, not by that day's local truck count -- so arrivals is a weak predictor and season and market level do the work.

### F3 — `f3_arrivals_is_a_season_proxy.png`

Month explains only 2.7% of arrivals variance, so arrivals is nearly orthogonal to season (VIF 1.03) -- no collinearity problem, but also no hidden signal: the deviation of arrivals from its monthly norm still shows no clear link to price.

### F4 — `f4_coefficient_instability.png`

Across specifications the arrivals coefficient stays within [-0.028, +0.003] ₹/quintal -- economically negligible against a seasonal swing of over ₹1,400. Arrivals earns at most a minor role; the model is carried by month and market.

### F5 — `f5_market_level_vs_timing.png`

Markets differ in price level by 43% (Chattrapati Sambhajinagar APMC to Lasalgaon(Niphad) APMC) but share the same seasonal timing, so 'where' and 'when' are separable and mandi enters the model as a level shift only.

### F6 — `f6_unexplained_shocks.png`

64 observations in shock months (2024-09, 2024-11, 2024-12, 2025-07...) reach ₹11,000/qtl with no variable in the dataset that explains them -- the model will systematically miss the weeks that pay most.
