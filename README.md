<div align="center">

# 🧅 Mandi Price Watch

### *Turning two years of government onion data into simple advice for farmers*

**When to sell · Where to sell · Which variety · What's the price next month**

<br>

`Python` · `SQLite` · `statsmodels` · `LightGBM` · `Power BI` · `pytest`

<br>

> *"A farmer who sells at the wrong time can lose half their income — not because they grew a bad crop, but purely because of timing. This project turns gut-feeling advice into data-backed answers a field agent can show on a phone."*

</div>

---

## 📖 The One-Line Version

I took **two years of real government onion-price data** from markets across Maharashtra and turned it into simple advice for farmers: **when to sell, where to sell, which variety earns most, and what next month's price will probably be.**

That's it. Everything below is just *how*.

---

## 🌾 Why This Matters

Onion is one of India's most price-volatile crops. The **same sack** can sell for ₹1,000 one month and ₹2,500 a few months later.

**DeHaat** advises farmer groups, and their field agents hear the same questions every season:

- 🕐 *"When should I sell?"*
- 📍 *"Which market should I take my onions to?"*
- ⏳ *"Is it worth waiting?"*

Right now, those answers are mostly **gut feeling**. This project makes them **data-backed**.

---

## 📊 The Data

| | |
|---|---|
| **Source** | Agmarknet (Government of India) |
| **Crop** | Onion 🧅 |
| **Region** | Maharashtra |
| **Period** | June 2024 → June 2026 |
| **Size** | ~32,000 rows · 111 markets · multiple varieties |

> Think of it as *two years of receipts from 111 vegetable markets.*

---

## 🧹 The Unglamorous Half: Cleaning

Real government data is messy. Before *any* analysis, these had to be fixed — each one would have silently corrupted the results:

- **🏷️ Market name was a heading, not a column** — 32,000 prices belonging to nobody, until each was stamped with its market.
- **⚖️ Unit mismatch** — arrivals in tonnes, prices per quintal (1 tonne = 10 quintals). Mixing them = everything 10× wrong.
- **👯 Duplicate files** — one month downloaded twice; ~1,100 exact-copy rows removed.
- **✍️ Messy names** — the same market spelled two ways looked like two markets.
- **🕳️ Missing data** — some days gone, and all of **August 2024** simply absent. *Left as an honest gap — never fabricated.*

> **Cleaning this properly — and documenting every decision — is honestly half the project.**

---

## ⚙️ How It Works

One command runs the whole chain in about **20 seconds**:

```
Raw files  →  Clean  →  Database  →  Analyse  →  Charts  →  Model  →  Dashboard
```

1. **Read** 25 files, stitch into one clean table
2. **Clean** — remove duplicates, keep real spikes, handle gaps honestly
3. **Store** in a small SQLite database
4. **Explore** — charts to find the patterns
5. **Explain** — measure what each month & market is worth, in rupees
6. **Predict** — forecast next month's price per market
7. **Export** — clean summaries that feed a Power BI dashboard

---

## 🎯 What We Found

### 🕐 WHEN to sell — *matters most*
Prices **peak in September–November**, bottom out in **April–May**. The gap is about **₹1,500/quintal** — roughly **2.5×** across the year. *When* you sell is the single biggest lever.

### 📍 WHERE to sell — *matters, but less*
The **Nashik belt** (Lasalgaon — Asia's biggest onion market — and Pimpalgaon) pays about **₹756/quintal more** than the cheapest market. Worth knowing, but ~half as important as timing — and subtract transport cost.

### 🧅 WHICH variety — *a bonus finding*
**Red onion sells ~31% more** than Local, every month. That's a crop-planning decision, not a selling one.

### 🔮 NEXT MONTH's price — *the forecast*
A model predicts next month's price per market, with an honest **"it could be anywhere in this range"** band — not a fake-precise promise.

<div align="center">

> **The advice for a farmer:** Sell **Sept–Nov**. Prefer the **Nashik belt** if transport is cheap. Grow **Red onion** if you can. Treat next month's price as a **range, not a promise.**

</div>

---

## 🫡 The Honest Part *(what makes it trustworthy)*

This is the part I'm most proud of — and it's unusual for a student project.

- **I found something that turned out to be false — and said so.** A dramatic pattern on practice data completely disappeared on real data. I reported the truth instead of the exciting story: a single market's daily supply barely moves its own price, because onion prices are set at the *state* level, not by one market's trucks.

- **My fancy model barely beat a dumb guess.** The simple rule *"next month ≈ this month"* is very hard to beat for onions. My machine-learning model essentially tied it — so I reported that plainly, and made the model earn its keep by giving an honest **uncertainty range** the simple rule can't.

- **No model here can predict a crash or a spike.** Those come from weather, export bans, and policy — none of which are in this data. The model describes a *normal* year and will always under-predict a crazy one.

> **Being upfront about limitations is what separates a real analyst from someone who just makes charts.**

---

## 🛠️ Built With

| Tool | Job |
|---|---|
| **Python** | All the data work |
| **SQL / SQLite** | A small database for the cleaned data |
| **statsmodels** | The *"how much is each month worth"* model |
| **LightGBM** | The machine-learning forecaster |
| **Power BI** | The dashboard field agents would actually use |
| **pytest + Git** | Automated tests & version history — like real software |

> **Fully reproducible:** download the raw files, run one command, get the exact same numbers back. Most analyses can't be re-run by a stranger — this one can.

---

## ⚠️ Limitations *(what this model honestly cannot do)*

We'd rather state these plainly than let them hide.

- **🌪️ It can't predict crashes or spikes.** The biggest onion price moves come from **weather, government export bans, and policy announcements** — none of which are in this dataset. The model describes a *normal* year, and will always under-predict a crazy one.
- **📉 The forecaster only ties a dumb baseline.** The simple rule *"next month ≈ this month"* is extremely hard to beat for a series this volatile. Our LightGBM model essentially **matched** it rather than clearly beating it — so we made it useful a different way: an honest uncertainty *range* the simple rule can't give.
- **🗓️ Only two years of data.** Two seasonal cycles is the *minimum* to claim a pattern is seasonal. We can say "prices peaked Sept–Nov in both years" — we **cannot** claim a decade-long guarantee.
- **🕳️ A whole month is missing.** All of **August 2024** is absent from the government source. We left it as an honest gap rather than inventing values.
- **🏘️ Local supply barely predicts local price.** A single market's daily arrivals don't move *that market's* price much, because onion prices are set at the **state level**, not by one mandi's trucks. Supply matters — but at the aggregate/seasonal scale, not the single-market-single-day scale.

---

