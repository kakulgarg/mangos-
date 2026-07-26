# Mandi Price Watch — The Whole Project, Explained Simply

*A plain-language walkthrough you can share with anyone, technical or not.*

---

## 1. The one-line version

> I took two years of real government onion-price data from markets across
> Maharashtra and turned it into simple advice for farmers: **when to sell,
> where to sell, which type of onion earns most, and what the price will
> probably be next month.**

That's it. Everything below is just *how*.

---

## 2. Why this matters (the real-world problem)

Onion is one of India's most price-volatile crops. The same sack of onions can
sell for ₹1,000 one month and ₹2,500 a few months later. A farmer who sells at
the wrong time can lose **half their income** — not because they grew a bad crop,
but purely because of *timing*.

DeHaat is a company that advises farmer groups. Their field agents get asked the
same questions every season:
- *"When should I sell?"*
- *"Which market should I take my onions to?"*
- *"Is it worth waiting?"*

Right now those answers are mostly gut feeling. My project turns them into
**data-backed answers** a field agent can show a farmer on a phone.

---

## 3. Where the data comes from

The Government of India runs a public website called **Agmarknet** that records
the daily price of crops in every market ("mandi"). I downloaded onion prices for
**Maharashtra**, one month at a time, for **June 2024 to June 2026**.

That's:
- **~32,000 rows** of daily prices
- **111 markets**
- **2 years** of history
- Different **varieties** of onion (Red, Local, White, etc.)

Think of it as two years of receipts from 111 vegetable markets.

---

## 4. The problem with raw data (why you can't just open it in Excel)

Real government data is messy. A few examples of what was wrong and had to be
fixed before any analysis:

- **The market name wasn't in a column.** It appeared as a heading between
  blocks of rows — so a normal spreadsheet would lose track of *which market*
  each price belonged to.
- **Arrivals were in tonnes, prices were per quintal.** (1 tonne = 10 quintals.)
  Mixing them up would make everything 10× wrong.
- **Duplicate files.** One month was downloaded twice, so ~1,100 rows were exact
  copies that had to be removed.
- **Messy names.** "Pune APMC" vs "Pune  APMC" — the same market spelled two ways
  would look like two different markets.
- **Missing days and a whole missing month** (August 2024 just isn't in the
  government data).

Cleaning this up properly — and *documenting every decision* — is honestly half
the project. Good data work is unglamorous but it's what separates a real
analysis from a pretty-but-wrong one.

---

## 5. What the project actually does, step by step

I built a **pipeline** — a chain of small programs where each one hands its
output to the next. One command runs the whole thing in about 20 seconds:

```
Raw files  →  Clean them  →  Store in a database  →  Analyse  →  Charts
           →  Build a prediction model  →  Export for the dashboard
```

The steps, in plain English:

1. **Read** the 25 downloaded files and stitch them into one clean table.
2. **Clean** — remove duplicates, flag impossible prices, keep the extreme
   spikes (they're real and important), handle the missing days honestly.
3. **Store** everything in a small database so it's easy to query.
4. **Explore** — make charts to find the patterns.
5. **Explain** — a simple model that measures how much each month and each
   market is worth, in rupees.
6. **Predict** — a model that forecasts next month's price for each market.
7. **Export** — save clean summary files that feed a Power BI dashboard.

---

## 6. What we found (the actual answers)

### 🗓️ WHEN to sell — this matters most
Onion prices **peak in September–November** and **bottom out in April–May**.
The difference is about **₹1,500 per quintal** — the price roughly *2.5×* across
the year. So *when* you sell is the single biggest lever a farmer has.

### 📍 WHERE to sell — matters, but less
The **Nashik belt** (markets like Lasalgaon and Pimpalgaon — Lasalgaon is Asia's
biggest onion market) pays about **₹756 per quintal more** than the cheapest
market. Worth knowing, but only about *half* as important as timing — and you
have to subtract the cost of transporting onions there.

### 🧅 WHICH variety — a nice bonus finding
**Red onion sells for about 31% more** than Local onion, in every month. That's a
crop-*planning* decision (what to grow), not a selling decision.

### 🔮 NEXT MONTH's price — the forecast
A model predicts next month's price for each market, with an honest "it could be
anywhere in this range" band. For example, for July 2026 it expects Pimpalgaon
Baswant to pay the most (~₹1,788/quintal).

**The bottom-line advice for a farmer:** *Sell September–November. Prefer the
Nashik belt if transport is cheap. Grow Red onion if you can. And treat next
month's price as a range, not a promise.*

---

## 7. The honest part (what makes it trustworthy, not just impressive)

This is the part I'm most proud of, and it's unusual for a student project.

**I found something that turned out to be false — and I said so.**
When I first built this on *practice* data, I found a dramatic pattern (more
supply → lower price, in a surprising way). When I plugged in the *real* data,
that pattern **completely disappeared**. I could have kept the exciting story.
Instead I reported the truth: a single market's daily supply barely affects its
price, because onion prices are driven by the whole state's supply, not one
market's trucks.

**My fancy prediction model barely beat a dumb guess.**
The simple rule "next month's price ≈ this month's price" is *really* hard to
beat for onions, because prices are so unpredictable. My machine-learning model
essentially *tied* it. Rather than dress that up as a win, I reported it plainly
— and made the model useful anyway by having it give an honest *uncertainty
range* the simple rule can't.

**No model here can predict a price crash or spike.** Those are caused by weather,
government export bans, and policy — none of which are in this dataset. So the
model describes a *normal* year and will always *under*-predict a crazy one.

Being upfront about limitations is what separates a real analyst from someone
who just makes charts. Professors and employers notice this.

---

## 8. What it's built with (the tech, kept light)

- **Python** — for all the data work
- **SQL / SQLite** — a small database for the cleaned data
- **statsmodels** — the "how much is each month worth" model
- **LightGBM** — the machine-learning forecaster
- **Power BI** — the interactive dashboard farmers' agents would actually use
- **pytest + Git** — automated tests and version history, like real software

The whole thing is *reproducible*: anyone can download the raw files, run one
command, and get exactly the same charts and numbers back. That's a big deal in
data science — most analyses can't be re-run by a stranger.

---

## 9. What's still left to do

- **Build the actual Power BI dashboard** (the data for it is all ready).
- **Record a short video** walking through it.
- **Ideally, add weather data** — that's the one thing that could help predict
  the price shocks the model currently can't see.

---

## 10. The 30-second summary to tell a friend

> "I took two years of real government onion-price data — 32,000 records from
> 111 markets — cleaned it up, and built a tool that tells farmers the best time
> to sell (September–November, worth ₹1,500 a quintal), the best market, the
> best variety, and a forecast of next month's price. The interesting twist is
> the honesty: one of my big findings turned out to be false on real data, and
> my fancy prediction model barely beat a simple guess — and I reported both
> instead of hiding them, because that's what real analysis looks like."

---

*Built for the IIT Mandi CCE AI & Data Science capstone. Data: Agmarknet
(Government of India). Everything reproducible from the raw files with one
command.*
