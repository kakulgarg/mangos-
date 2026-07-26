# Walkthrough Script — 6 to 7 minutes

`SUBMISSION.md` requires **5–10 minutes**. This script runs about 6:30 at a
natural pace.

**Rules reviewers actually weight:**
- Business impact first, methodology second
- Your own voice — the one artifact that cannot be copy-pasted
- Do not read verbatim. Learn the beats and speak from them.

---

## [0:00–0:45] The question — open with the number

> A Maharashtra onion farmer who sells in **May instead of November** loses about
> **₹1,500 a quintal** — the price more than doubles across the year. So the two
> questions DeHaat's field agents get every season are simple: **when do we sell,
> where do we sell, and which onion earns most** — and what will the price do
> next month?
>
> I built that answer from **real government Agmarknet data**: 25 monthly exports,
> about **32,000 daily price records**, **111 markets**, two years of onions.

---

## [0:45–1:45] The answer, up front

> Three findings, in order of how much money they're worth.
>
> **Timing is worth about twice what market choice is worth.** Prices peak
> September to November, trough April–May. That swing is ₹1,500 a quintal.
>
> **Where** matters next: the Nashik belt — Lasalgaon, Pimpalgaon — pays about
> **₹756 a quintal more** than the cheapest market. That's gross of transport,
> which I'll flag.
>
> And **which variety**: **Red onion earns about 31% more** than Local, in every
> month. That's a crop-planning lever worth roughly ₹530 a quintal.
>
> So the headline for a field agent: **sell September to November, prefer the
> Nashik belt if transport is cheap, and grow Red where you can.**

---

## [1:45–3:15] Dashboard walkthrough

> Page one answers when and where. The seasonal curve — every one of the 14
> markets peaks in the same Sep–Nov window; only the level differs. The
> recommendation matrix turns that into an instruction per market and month:
> green is sell, grey is hold.
>
> Page two is the new one for a farmer: **which variety pays best**, month by
> month. Red sits above Local and Unhali across the board.
>
> Page three is the forecast: **next month's expected price for every market,
> with an uncertainty band.** For July it puts Pimpalgaon Baswant on top at about
> ₹1,788 a quintal. Notice I never show a forecast without its range — that band
> is the honest part.

---

## [3:15–4:30] The finding that changed the analysis

> Here's where I had to be honest with myself. The obvious model was
> price against arrivals, month, and market — supply and demand.
>
> But on the real data, **a single market's own daily arrivals barely predict its
> price** — correlation about minus 0.03, essentially nothing. Onion price at a
> mandi is set by state and national supply and by the reference market, not by
> how many trucks showed up that day.
>
> That's worth saying because my *first* build, on the scaffold's sample data,
> found a dramatic supply effect — a textbook Simpson's paradox. When I swapped in
> the real data, it vanished. I could have kept the better story. I reported the
> real one instead, and rebuilt the recommendation around timing, market, and
> variety — which the data genuinely supports.

---

## [4:30–5:45] Where the model breaks — say it before you're asked

> The forecast. I built a LightGBM model on lag features — and I'll tell you
> straight: **it did not beat a naive "next month equals this month" baseline.**
> Monthly onion prices are close to a random walk. What I did was blend the two,
> which ties the baseline on accuracy — about **₹168 a quintal, 14% error** in
> walk-forward testing — and adds a calibrated uncertainty band the baseline
> can't give.
>
> And no model here can see a **supply shock**. Prices hit ₹25,000 a quintal in
> 2024 and 2025, and this dataset has nothing about *why* — no weather, no MSP, no
> export policy. So every model under-predicts exactly the weeks that pay most,
> always in the same direction: **the real peak is higher than I predict, never
> lower.** The advice is conservative, not optimistic.

---

## [5:45–6:30] Limitation and close

> The biggest caveat: **two years, each month seen about twice, and August 2024 is
> missing from the source entirely.** So the November peak rests on few
> observations. What would change my mind is five to seven years of data, and what
> I'd add first is IMD district rainfall — the direct cause of the shocks I can't
> currently see.
>
> But the pipeline runs end to end in twenty seconds, every number on that
> dashboard regenerates from the raw files, and it's tested. Point it at a new
> commodity and you change one config file.
>
> The one-line version for a farmer: **sell Sep to November, prefer the Nashik
> belt, grow Red — and treat next month's price as a range, not a promise.**

---

## Recording notes

- **The two moments that make this sound like an analyst:** admitting the
  Simpson's-paradox finding didn't survive real data (4:00), and admitting the ML
  model tied a naive baseline (4:45). Volunteering both *before* a reviewer asks is
  the single most trust-building thing in the talk.
- Keep the dashboard on screen for the middle third; talk over it, don't narrate
  every click.
- If you run long, cut the dashboard tour, never the honesty section.
