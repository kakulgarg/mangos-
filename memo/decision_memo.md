# Decision Memo — Onion Selling Windows, Maharashtra

**To:** Advisory Team, DeHaat
**From:** Ritik
**Date:** 25 July 2026
**Re:** When, where, and which onion farmers should sell this season

---

## The question

Which selling window, which market, and which onion variety should field agents
recommend to FPO members selling onions in Maharashtra — and what will the price
do next month?

## The headline finding

**Timing is worth about twice what market choice is worth, and variety is worth
almost as much as market.**

The same lot sold in **November** rather than **May** fetches **₹1,503/quintal
more** — a 2.5× swing. Choosing the best market over the worst is worth
**₹756/quintal** (gross of transport). Growing **Red** onion rather than **Local**
is worth about **₹530/quintal**. A farmer who optimises location while selling in
the wrong month leaves most of the money on the table.

All 14 curated markets peak in **September–November** and trough in **April–May**;
the seasonal pattern is common across the state, and only the price level differs.

## Selling windows the data supports

**1. Sell September–November. Prioritise November; July is a secondary window.**
Curated-market average: **₹2,495/quintal in November** against **₹992 in May**.
Every market ranks the Sep–Nov window first.
*Confidence: high on direction, moderate on magnitude — 24 months only.*

**2. Prefer the Nashik belt (Lasalgaon, Pimpalgaon) — if transport is cheap.**
Lasalgaon markets average **₹1,960–2,030/quintal (+12–16% vs state)**; Chhatrapati
Sambhajinagar sits at **₹1,273 (−27%)**. The **₹756/quintal** spread is **gross**
of transport, which is not in this data and must be netted off before advising a
farmer to travel.
*Confidence: high. Price rankings are stable across the record.*

**3. Where feasible, grow and market Red onion.**
Red averages **₹2,231/quintal**, against Local at **₹1,701** and Unhali at
**₹1,328** — a **~31%** premium that holds across months.
*Confidence: high on ranking; a crop-planning lever, not a sell-timing one.*

**4. Next month, expect prices near this month's, market by market.**
The forecaster (walk-forward MAE **₹168/quintal, 13.9%**) ranks **Pimpalgaon
Baswant** highest for **July 2026** at **₹1,788/quintal** (range ₹1,555–1,884).
The dashboard carries the full ranking with an uncertainty band on each market.

## Recommendation

Field agents should advise members to **plan around a September–November sale**,
treating July as an earlier acceptable window, and to **avoid April–May sales
where storage allows** — the critical qualifier. The recommendation is only
actionable for farmers who can physically hold stock; for those who cannot,
market and variety choice are the levers left, and they are worth less than
timing.

**Before this reaches farmers, confirm three things:** that cold-storage capacity
is actually available to the members being advised; that transport cost to the
Nashik belt is lower than the ₹756/quintal premium; and that the variety advice
fits the member's agronomy.

## Uncertainty, stated plainly

**Next month's price is close to unpredictable beyond "near this month's level."**
Monthly onion prices behave like a random walk with large, unforecastable shocks:
a purpose-built model barely improves on assuming next month equals this month
(₹168 vs ₹169 mean error). The value of the model is the **uncertainty band** it
puts around each forecast, not a false claim of precision.

**No model here can see a supply shock.** The dataset records that prices spiked
to **₹25,000/quintal** in 2024–25 but contains nothing about *why* — no weather,
no MSP, no export policy. The error runs one way: in a shock year the real peak
will be **higher** than any forecast here, never lower. Advice built on it is
conservative, not optimistic.

## Limitations

**The seasonal pattern rests on 24 months — each month observed ~2 times, and
August 2024 is missing entirely.** The November peak is estimated from few
observations. This data cannot separate "November is reliably the peak" from "two
unusual Novembers." This is the single largest caveat on the recommendation.

**What would change my conclusion:** five to seven years of history. **What I
would want next**, in priority order: (1) district rainfall from IMD, (2) sowing
acreage by season, (3) dated MSP and export-policy announcements, (4) cold-storage
capacity by district, (5) farm-to-mandi transport costs. Items 1–3 address the
shock blindness; items 4–5 determine whether the advice is actionable for a given
farmer.

---

*Analysis: 31,930 daily price records, 111 Maharashtra mandis (14 curated),
Jun 2024 – Jun 2026, Agmarknet. Seasonal and market effects from OLS with robust
standard errors; next-month forecast from a hybrid persistence + LightGBM model
with quantile prediction intervals, evaluated walk-forward. Full methodology,
data-quality note, and model card in the repository.*
