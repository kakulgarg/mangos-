"""
Step 8 -- Build the interactive web dashboard.

Reads the dashboard extract CSVs (produced by build_extracts.py) and writes a
single self-contained HTML file: dashboard/mandi_dashboard.html.

This is what "connects" the model output to the web page -- re-run the pipeline
and the page regenerates with fresh numbers. The page needs no server: open it
by double-clicking. All data is embedded; only the Chart.js library and the
Inter web font load from a CDN.

Features: executive summary, KPI cards, seasonal / market / variety / forecast
charts, an advice heatmap, an Evidence page, and a farmer PROFIT CALCULATOR
(location + quantity + variety, optional transport/labour/commission) that nets
each mandi's price against distance-based logistics cost, shows a live cost
breakdown, and ranks the markets by take-home profit.
"""

from __future__ import annotations

import json
from datetime import date

import numpy as np
import pandas as pd

import config as cfg
from logging_config import get_logger

log = get_logger(__name__)
DASH = cfg.ROOT / "dashboard" / "data"
OUT = cfg.ROOT / "dashboard" / "mandi_dashboard.html"

MANDI_COORDS = {
    "Bhusaval APMC": (21.043, 75.785),
    "Chattrapati Sambhajinagar APMC": (19.876, 75.343),
    "Kolhapur APMC": (16.705, 74.243),
    "Lasalgaon APMC": (20.145, 74.238),
    "Lasalgaon(Niphad) APMC": (20.100, 74.120),
    "Lasalgaon(Vinchur) APMC": (20.110, 74.350),
    "Mangal Wedha APMC": (17.516, 75.453),
    "Nasik APMC": (20.000, 73.780),
    "Pimpalgaon Baswant APMC": (20.172, 73.984),
    "Pune APMC": (18.501, 73.857),
    "Pune(Manjri) APMC": (18.503, 73.980),
    "Pune(Moshi) APMC": (18.683, 73.847),
    "Pune(Pimpri) APMC": (18.628, 73.800),
    "Satara APMC": (17.686, 74.005),
}

DISTRICTS = {
    "Nashik": (20.00, 73.79), "Pune": (18.52, 73.86), "Kolhapur": (16.70, 74.24),
    "Satara": (17.69, 74.00), "Sangli": (16.85, 74.58), "Solapur": (17.66, 75.91),
    "Ahilyanagar (Ahmednagar)": (19.09, 74.74), "Chh. Sambhajinagar": (19.88, 75.34),
    "Jalgaon": (21.01, 75.56), "Dhule": (20.90, 74.77), "Nandurbar": (21.37, 74.24),
    "Beed": (18.99, 75.76), "Jalna": (19.84, 75.88), "Dharashiv (Osmanabad)": (18.19, 76.04),
    "Latur": (18.40, 76.58), "Nanded": (19.15, 77.32), "Buldhana": (20.53, 76.18),
    "Nagpur": (21.15, 79.09), "Amravati": (20.93, 77.75),
}


def build_data() -> dict:
    M = cfg.MONTHS
    sb = pd.read_csv(DASH / "seasonal_by_mandi.csv")
    ms = pd.read_csv(DASH / "market_summary.csv").sort_values("avg_modal_price", ascending=False)
    vb = pd.read_csv(DASH / "variety_by_month.csv")
    fc = pd.read_csv(DASH / "forecast_next_month.csv").sort_values("rank_next_month")
    mc = pd.read_csv(DASH / "model_coefficients.csv")
    rec = pd.read_csv(DASH / "recommendation.csv")

    d: dict = {"months": M, "generated": date.today().isoformat()}
    d["state_by_month"] = [round(float(sb.groupby("month_num").avg_modal_price.mean()
                                       .reindex(range(1, 13)).fillna(0)[m]), 0) for m in range(1, 13)]
    piv = sb.pivot_table("avg_modal_price", "mandi_name", "month_num").reindex(columns=range(1, 13))
    d["markets_seasonal"] = {n: [None if pd.isna(v) else round(float(v)) for v in piv.loc[n]]
                             for n in piv.index}
    d["market_summary"] = [{"name": r.mandi_name, "price": round(float(r.avg_modal_price)),
                            "vs": float(r.pct_vs_state_avg)} for _, r in ms.iterrows()]
    d["coverage"] = [{"name": r.mandi_name, "days": int(r.reporting_days),
                      "cov": float(r.pct_coverage)} for _, r in ms.iterrows()]
    vpiv = vb.pivot_table("avg_modal_price", "variety_group", "month_num").reindex(columns=range(1, 13))
    d["variety"] = {n: [None if pd.isna(v) else round(float(v)) for v in vpiv.loc[n]] for n in vpiv.index}
    d["variety_avg"] = {n: round(float(vb[vb.variety_group == n].avg_modal_price.mean()))
                        for n in vb.variety_group.unique()}
    d["forecast"] = [{"name": r.mandi_name, "p": round(float(r.forecast_price)),
                      "lo": round(float(r.forecast_low)), "hi": round(float(r.forecast_high)),
                      "chg": float(r.vs_last_month_pct)} for _, r in fc.iterrows()]
    d["forecast_month"] = f"{fc.iloc[0].target_month_name} {int(fc.iloc[0].target_year)}"
    mm = mc[mc.kind == "month"]
    d["coef"] = [{"m": M[int(r.sort_order) - 1] if r.sort_order <= 12 else r.label,
                  "v": round(float(r.rs_vs_baseline)), "sig": r.significant == "Yes"}
                 for _, r in mm.iterrows()]
    rp = rec.pivot_table("seasonal_index", "mandi_name", "month_num").reindex(columns=range(1, 13))
    d["rec_index"] = {n: [None if pd.isna(v) else round(float(v)) for v in rp.loc[n]] for n in rp.index}

    peak_i = int(np.argmax(d["state_by_month"])); trough_i = int(np.argmin(d["state_by_month"]))
    d["insights"] = {
        "peak_month": M[peak_i], "peak_price": d["state_by_month"][peak_i],
        "trough_month": M[trough_i], "trough_price": d["state_by_month"][trough_i],
        "timing_gain": int(d["state_by_month"][peak_i] - d["state_by_month"][trough_i]),
        "top_market": d["market_summary"][0]["name"], "top_market_price": d["market_summary"][0]["price"],
        "market_spread": int(d["market_summary"][0]["price"] - d["market_summary"][-1]["price"]),
        "bottom_market": d["market_summary"][-1]["name"],
    }
    fc_by_name = {r["name"]: r for r in d["forecast"]}
    avg_by_name = {r["name"]: r["price"] for r in d["market_summary"]}
    mandis = []
    for name in avg_by_name:
        if name not in MANDI_COORDS:
            continue
        lat, lng = MANDI_COORDS[name]
        base = fc_by_name[name]["p"] if name in fc_by_name else avg_by_name[name]
        mandis.append({"name": name, "avg": avg_by_name[name], "price": base, "lat": lat, "lng": lng})
    d["calc_mandis"] = mandis
    d["districts"] = {k: list(v) for k, v in DISTRICTS.items()}
    overall = float(np.mean(list(d["variety_avg"].values())))
    d["variety_factor"] = {k: round(v / overall, 3) for k, v in d["variety_avg"].items()}
    return d


def main() -> None:
    data = build_data()
    html = TEMPLATE.replace("/*DATA*/{}/*END*/", json.dumps(data))
    OUT.write_text(html, encoding="utf-8")
    log.info("Wrote %s (%d markets, %d districts, calculator + exec summary)",
             OUT.name, len(data["calc_mandis"]), len(data["districts"]))


TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Onion Market Intelligence — Farmer Advisory Dashboard</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.1/dist/chart.umd.min.js"></script>
<style>
  :root{
    --p1:#5b1746;--p2:#2e0b24;--accent:#c1440e;--accent-d:#9a3409;--green:#2f855a;--gold:#d69e2e;
    --bg:#f4f1ee;--card:#ffffff;--line:#e7e1dc;--ink:#1b1420;--muted:#71727a;--muted2:#9a9aa2;
    --shadow:0 1px 3px rgba(46,11,36,.06),0 8px 24px rgba(46,11,36,.05);
    --radius:16px;
  }
  *{box-sizing:border-box;margin:0;padding:0;}
  html{scroll-behavior:smooth;}
  body{font-family:'Inter',system-ui,'Segoe UI',sans-serif;background:var(--bg);color:var(--ink);-webkit-font-smoothing:antialiased;}
  .sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0);}
  a{color:inherit;text-decoration:none;}
  .app{display:flex;min-height:100vh;}
  /* ---- sidebar ---- */
  .side{width:230px;background:linear-gradient(175deg,var(--p1),var(--p2));color:#fff;display:flex;
        flex-direction:column;position:sticky;top:0;height:100vh;flex-shrink:0;}
  .brand{padding:22px 20px;display:flex;align-items:center;gap:12px;border-bottom:1px solid rgba(255,255,255,.10);}
  .brand .logo{width:42px;height:42px;border-radius:12px;background:radial-gradient(circle at 32% 28%,#f0789c,#7a1f5a);
        display:flex;align-items:center;justify-content:center;font-size:22px;box-shadow:0 4px 12px rgba(0,0,0,.25);}
  .brand b{font-size:15.5px;font-weight:700;letter-spacing:.2px;}
  .brand small{font-size:10.5px;opacity:.65;display:block;font-weight:500;letter-spacing:.3px;text-transform:uppercase;}
  .nav{padding:12px 0;flex:1;overflow-y:auto;}
  .nav a{display:flex;align-items:center;gap:12px;padding:12px 22px;color:#e7d6e3;cursor:pointer;
        font-size:13.5px;font-weight:600;border-left:3px solid transparent;transition:.15s;}
  .nav a .ic{width:20px;text-align:center;font-size:16px;}
  .nav a:hover{background:rgba(255,255,255,.06);color:#fff;}
  .nav a.active{background:rgba(255,255,255,.12);color:#fff;border-left-color:var(--gold);}
  .side .foot{padding:16px 20px;font-size:10.5px;line-height:1.6;opacity:.6;border-top:1px solid rgba(255,255,255,.10);}
  .side .foot b{opacity:.9;}
  /* ---- main ---- */
  .main{flex:1;min-width:0;display:flex;flex-direction:column;}
  .top{background:rgba(255,255,255,.9);backdrop-filter:blur(6px);border-bottom:1px solid var(--line);
       padding:15px 30px;position:sticky;top:0;z-index:20;display:flex;justify-content:space-between;align-items:center;gap:16px;}
  .top .crumb{font-size:11px;color:var(--muted2);font-weight:600;text-transform:uppercase;letter-spacing:.5px;}
  .top h1{font-size:19px;font-weight:700;margin-top:2px;}
  .top .meta{display:flex;gap:8px;align-items:center;flex-shrink:0;}
  .chip{display:inline-flex;align-items:center;gap:6px;background:#f3eeeb;border:1px solid var(--line);
        border-radius:20px;padding:6px 12px;font-size:11.5px;color:var(--muted);font-weight:600;}
  .chip .dot{width:7px;height:7px;border-radius:50%;background:var(--green);}
  .wrap{padding:26px 30px;max-width:1200px;width:100%;}
  .page{display:none;} .page.active{display:block;animation:fade .35s ease;}
  @keyframes fade{from{opacity:0;transform:translateY(8px);}to{opacity:1;transform:none;}}
  .sec-h{font-size:12px;font-weight:700;color:var(--muted2);text-transform:uppercase;letter-spacing:.6px;margin:6px 0 12px;}
  /* ---- executive summary ---- */
  .exec{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-bottom:24px;}
  .ex{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:20px;
      box-shadow:var(--shadow);border-top:4px solid var(--accent);}
  .ex:nth-child(2){border-top-color:var(--green);} .ex:nth-child(3){border-top-color:var(--gold);}
  .ex .q{font-size:12px;font-weight:700;color:var(--muted);text-transform:uppercase;letter-spacing:.4px;}
  .ex .a{font-size:20px;font-weight:800;margin:8px 0 4px;color:var(--ink);}
  .ex .d{font-size:12.5px;color:var(--muted);line-height:1.5;}
  /* ---- kpis ---- */
  .kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-bottom:24px;}
  .kpi{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:18px;
       box-shadow:var(--shadow);display:flex;gap:14px;align-items:flex-start;transition:.2s;}
  .kpi:hover{transform:translateY(-3px);box-shadow:0 12px 26px rgba(46,11,36,.12);}
  .kpi .chipi{width:46px;height:46px;border-radius:13px;display:flex;align-items:center;justify-content:center;
        font-size:22px;background:linear-gradient(135deg,#faf1ec,#f3e3dd);flex-shrink:0;}
  .kpi .lbl{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;font-weight:700;}
  .kpi .val{font-size:24px;font-weight:800;color:var(--p1);margin-top:4px;line-height:1.05;}
  .kpi .sub{font-size:11.5px;color:var(--muted);margin-top:3px;}
  /* ---- cards ---- */
  .card{background:var(--card);border:1px solid var(--line);border-radius:var(--radius);padding:22px;
        margin-bottom:22px;box-shadow:var(--shadow);}
  .card h3{font-size:16.5px;font-weight:700;margin-bottom:3px;display:flex;align-items:center;gap:8px;}
  .card .note{font-size:12.5px;color:var(--muted);margin-bottom:16px;line-height:1.5;}
  .card .foot{font-size:11px;color:var(--muted2);margin-top:12px;border-top:1px dashed var(--line);padding-top:10px;}
  .chartwrap{position:relative;height:340px;} .chartwrap.tall{height:440px;}
  .grid-2{display:grid;grid-template-columns:1fr 1fr;gap:22px;}
  select,input{padding:10px 12px;border:1px solid var(--line);border-radius:10px;font-size:13.5px;
        font-family:inherit;background:#fff;color:var(--ink);width:100%;transition:.15s;}
  select:focus,input:focus{outline:none;border-color:var(--accent);box-shadow:0 0 0 3px rgba(193,68,14,.12);}
  label.fld{display:block;font-size:12px;font-weight:700;color:var(--muted);margin:12px 0 5px;}
  table{border-collapse:collapse;width:100%;font-size:12px;}
  th,td{padding:8px 6px;text-align:center;border-bottom:1px solid #f0ece8;}
  thead th{background:#faf7f5;font-weight:700;color:var(--muted);text-transform:uppercase;font-size:10.5px;letter-spacing:.4px;position:sticky;top:0;}
  td.name,th.name{text-align:left;white-space:nowrap;font-weight:600;}
  tbody tr:hover{background:#faf7f5;}
  .pill{display:inline-block;padding:3px 10px;border-radius:20px;font-size:11px;font-weight:700;}
  .banner{background:linear-gradient(120deg,#fff8f4,#fdf1ea);border:1px solid #f0d5c8;border-left:4px solid var(--accent);
        border-radius:12px;padding:14px 18px;font-size:13px;color:#7c2d12;margin-bottom:20px;line-height:1.55;}
  .grid2{display:grid;grid-template-columns:360px 1fr;gap:22px;align-items:start;}
  .btn{background:var(--accent);color:#fff;border:none;border-radius:11px;padding:13px 18px;font-size:14.5px;
        font-weight:700;cursor:pointer;width:100%;margin-top:16px;transition:.15s;}
  .btn:hover{background:var(--accent-d);transform:translateY(-1px);}
  .btn:active{transform:none;}
  .winner{background:linear-gradient(120deg,#2f855a,#22633f);color:#fff;border-radius:var(--radius);padding:24px;
        margin-bottom:18px;box-shadow:0 10px 28px rgba(47,133,90,.28);}
  .winner .t{font-size:11.5px;opacity:.85;text-transform:uppercase;letter-spacing:.06em;font-weight:700;}
  .winner .m{font-size:28px;font-weight:800;margin:5px 0 8px;}
  .winner .big{font-size:34px;font-weight:800;}
  .winner .n{font-size:13.5px;opacity:.95;line-height:1.6;margin-top:6px;}
  details{margin-top:10px;border-top:1px dashed var(--line);padding-top:8px;}
  summary{cursor:pointer;font-size:12.5px;color:var(--accent);font-weight:700;}
  .assume{font-size:11px;color:var(--muted);margin-top:12px;line-height:1.65;background:#faf7f5;padding:10px 12px;border-radius:9px;}
  .callout{background:#f0f7f3;border:1px solid #cfe8db;border-radius:11px;padding:12px 16px;font-size:12.5px;color:#22633f;margin-top:6px;}
  footer.page-foot{padding:22px 30px;border-top:1px solid var(--line);color:var(--muted2);font-size:11.5px;line-height:1.7;background:#fbf9f8;}
  footer.page-foot b{color:var(--muted);}
  @media(max-width:900px){
    .app{flex-direction:column;} .side{width:100%;height:auto;position:relative;flex-direction:row;overflow-x:auto;align-items:center;}
    .nav{display:flex;padding:0;} .nav a{border-left:none;border-bottom:3px solid transparent;white-space:nowrap;padding:14px 16px;}
    .nav a.active{border-left:none;border-bottom-color:var(--gold);} .brand{border:none;flex-shrink:0;} .side .foot{display:none;}
    .exec,.grid-2,.grid2{grid-template-columns:1fr;} .top{padding:14px 18px;} .wrap{padding:18px;}
  }
  @media print{.side,.top .meta{display:none;} .page{display:block!important;} .card{break-inside:avoid;}}
</style>
</head>
<body>
<div class="app">
<aside class="side">
  <div class="brand"><div class="logo">🧅</div><div><b>Onion Intel</b><small>Farmer Advisory</small></div></div>
  <nav class="nav" role="navigation" aria-label="Dashboard sections">
    <a class="active" data-p="p1" tabindex="0"><span class="ic">📊</span> Overview</a>
    <a data-p="p2" tabindex="0"><span class="ic">🧅</span> Variety</a>
    <a data-p="p3" tabindex="0"><span class="ic">🔮</span> Forecast</a>
    <a data-p="p4" tabindex="0"><span class="ic">🧮</span> Profit Calculator</a>
    <a data-p="p5" tabindex="0"><span class="ic">✅</span> Evidence</a>
  </nav>
  <div class="foot"><b>Data:</b> Agmarknet (Govt. of India)<br>14 curated Maharashtra markets<br>Jun 2024 – Jun 2026 · <span id="genDate"></span></div>
</aside>
<div class="main">
  <div class="top">
    <div><div class="crumb">Onion Market Intelligence</div><h1 id="ttl">Overview — When &amp; Where to Sell</h1></div>
    <div class="meta"><span class="chip"><span class="dot"></span>Live from model output</span>
      <span class="chip" id="upd">Updated —</span></div>
  </div>
  <div class="wrap">

  <!-- P1 -->
  <div class="page active" id="p1">
    <h2 class="sr-only">Overview: when, where and which onion to sell</h2>
    <div class="sec-h">Executive summary</div>
    <div class="exec" id="exec"></div>
    <div class="sec-h">Key numbers</div>
    <div class="kpis" id="kpis1"></div>
    <div class="card"><h3>📈 Seasonal price cycle — when to sell</h3>
      <p class="note">Average onion price by month. Prices peak Sep–Nov and trough Apr–May. Pick a market to overlay it on the state average.</p>
      <select id="marketSel" style="max-width:320px"></select><div class="chartwrap" style="margin-top:12px"><canvas id="seasonalChart"></canvas></div>
      <div class="foot">Source: curated-market monthly averages. Higher = a better month to sell.</div></div>
    <div class="card"><h3>📍 Which market pays the most — where to sell</h3>
      <p class="note">Average modal price per market over the full period. The Nashik belt leads; Chh. Sambhajinagar trails.</p>
      <div class="chartwrap tall"><canvas id="marketChart"></canvas></div>
      <div class="foot">Gross prices — transport cost is applied in the Profit Calculator.</div></div>
    <div class="card"><h3>🗓️ Advice grid — seasonal index by market &amp; month</h3>
      <p class="note">100 = that market's own yearly average, so higher means an above-average month for that market.
        <span class="pill" style="background:#2f855a;color:#fff">≥115 SELL</span>
        <span class="pill" style="background:#c6f0d4">100–115 good</span>
        <span class="pill" style="background:#fde9c8">85–100 hold</span>
        <span class="pill" style="background:#eceae8">&lt;85 store</span></p>
      <div style="overflow-x:auto"><table id="heatmap"></table></div></div>
  </div>

  <!-- P2 -->
  <div class="page" id="p2">
    <h2 class="sr-only">Which onion variety pays best</h2>
    <div class="kpis" id="kpis2"></div>
    <div class="card"><h3>🧅 Which onion variety pays best</h3>
      <p class="note">Average price by variety, month by month. Red onion sits above the rest almost everywhere.</p>
      <div class="chartwrap"><canvas id="varietyChart"></canvas></div>
      <div class="callout" id="varInsight"></div></div>
    <div class="card"><h3>Variety average price (whole period)</h3>
      <div class="chartwrap"><canvas id="varietyBar"></canvas></div>
      <div class="foot">"Other" groups the long tail of minor varieties (~52% of rows); Red/Local/White/Unhali are shown on their own.</div></div>
  </div>

  <!-- P3 -->
  <div class="page" id="p3">
    <h2 class="sr-only">Next-month price forecast</h2>
    <div class="banner">🔮 Forecast for <b id="fcMonth"></b>. Bars show the predicted price; the light band is the likely range (10th–90th percentile).
      Backtested error ≈ <b>₹168/quintal (14%)</b>. The model cannot predict supply shocks — a real shock month would be <b>higher</b>, never lower.</div>
    <div class="kpis" id="kpis3"></div>
    <div class="card"><h3>Predicted price next month, per market (with range)</h3>
      <p class="note">Ranked best to worst. The range is the honest uncertainty band, not a guarantee.</p>
      <div class="chartwrap tall"><canvas id="forecastChart"></canvas></div>
      <div class="foot">Model: hybrid of a persistence baseline and a LightGBM lag-feature model, evaluated walk-forward. Quantile intervals from LightGBM.</div></div>
  </div>

  <!-- P4 CALCULATOR -->
  <div class="page" id="p4">
    <h2 class="sr-only">Profit calculator</h2>
    <div class="banner">💡 Enter your details and this calculator finds the mandi that puts the <b>most money in your pocket</b> —
      after price, transport, mandi commission and labour. Transport &amp; labour are optional; sensible defaults are used if left blank.</div>
    <div class="grid2">
      <div class="card">
        <h3>🚜 Your details</h3>
        <label class="fld" for="cLoc">Your location (district / town)</label>
        <select id="cLoc"></select>
        <label class="fld" for="cQty">Quantity (quintals)</label>
        <input id="cQty" type="number" value="50" min="1" max="100000">
        <label class="fld" for="cVar">Onion variety</label>
        <select id="cVar"></select>
        <details><summary>Optional: adjust cost assumptions</summary>
          <label class="fld" for="cRate">Transport ₹ per km per quintal</label>
          <input id="cRate" type="number" value="0.5" step="0.1" min="0">
          <label class="fld" for="cLab">Loading / labour ₹ per quintal</label>
          <input id="cLab" type="number" value="30" min="0">
          <label class="fld" for="cComm">Mandi commission (%)</label>
          <input id="cComm" type="number" value="6" step="0.5" min="0">
        </details>
        <button class="btn" id="cGo">Calculate best mandi 🧮</button>
        <div class="assume" id="cAssume"></div>
      </div>
      <div>
        <div id="cWinner"></div>
        <div class="card"><h3>💸 Where your money goes (best mandi)</h3>
          <p class="note">Of the price at the recommended mandi, this is how much you keep vs what costs eat.</p>
          <div class="chartwrap" style="height:150px"><canvas id="breakdownChart"></canvas></div></div>
        <div class="card"><h3>All mandis ranked by take-home profit</h3>
          <div style="overflow-x:auto"><table id="cTable"></table></div>
          <div class="foot">⚠ = over 300 km. Onions store and travel well, so long hauls can still pay — but factor your own time and spoilage risk.</div></div>
      </div>
    </div>
  </div>

  <!-- P5 -->
  <div class="page" id="p5">
    <h2 class="sr-only">Evidence and honesty</h2>
    <div class="card"><h3>📊 How much each month is worth (₹ vs January)</h3>
      <p class="note">From the statistical model, holding market constant. Solid bars are statistically significant (95% CI excludes zero).</p>
      <div class="chartwrap"><canvas id="coefChart"></canvas></div></div>
    <div class="grid-2">
      <div class="card"><h3>🔎 What this dashboard is honest about</h3>
        <p class="note" style="line-height:1.85;font-size:12.5px">
          • <b>2 years of data only</b> (Aug 2024 missing) — each month seen ~2 times.<br>
          • <b>A market's own daily arrivals barely predict its price</b> (r ≈ −0.03) — price is set by state/national supply.<br>
          • <b>The ML forecaster ties a naive baseline</b> — monthly prices are near a random walk; its value is the uncertainty band.<br>
          • <b>The profit calculator uses assumed transport &amp; commission</b> the farmer can adjust — a net <i>estimate</i>, not a guarantee.<br>
          • <b>No weather / policy data</b> — so no model here can foresee a price shock.</p></div>
      <div class="card"><h3>🗂️ Data coverage by market</h3>
        <p class="note">How many days each curated market reported (of the full window).</p>
        <div style="overflow-x:auto;max-height:300px"><table id="covTable"></table></div></div>
    </div>
  </div>

  </div>
  <footer class="page-foot">
    <b>Methodology:</b> 31,930 daily Agmarknet onion records (111 markets, 14 curated) → cleaned → seasonal &amp; market analysis (OLS, HAC robust SEs) +
    a monthly per-mandi forecaster (persistence + LightGBM ensemble with quantile intervals). Full pipeline reproducible with one command.<br>
    <b>Disclaimer:</b> Figures are estimates for advisory use, not financial guarantees. Prices are gross; the calculator's transport, labour and commission are
    user-adjustable assumptions. In supply-shock periods the real peak price will be higher than shown.<br>
    <b>Source:</b> Agmarknet, Government of India · Built for the IIT Mandi CCE AI &amp; Data Science capstone · <span id="genDate2"></span>
  </footer>
</div>
</div>

<script>
const D = /*DATA*/{}/*END*/;
const A='#c1440e',P='#5b1746',G='#2f855a',MUT='#b6a9b0',GOLD='#d69e2e',months=D.months;
const INR=n=>'₹'+Math.round(n).toLocaleString('en-IN');
const INRk=n=>Math.round(n).toLocaleString('en-IN');
Chart.defaults.font.family="'Inter','Segoe UI',sans-serif";Chart.defaults.font.size=12;Chart.defaults.color='#71727a';
document.getElementById('genDate').textContent='built '+D.generated;
document.getElementById('genDate2').textContent='Generated '+D.generated;
document.getElementById('upd').textContent='Updated '+D.generated;

const TITLES={p1:['Overview — When & Where to Sell','Overview'],p2:['Which Variety Pays Best','Variety analysis'],
  p3:['Next-Month Price Forecast','Forecast'],p4:['Profit Calculator','Net-profit calculator'],p5:['Evidence & Honesty','Evidence']};
function go(p){document.querySelectorAll('.nav a').forEach(x=>x.classList.toggle('active',x.dataset.p===p));
  document.querySelectorAll('.page').forEach(x=>x.classList.toggle('active',x.id===p));
  document.getElementById('ttl').textContent=TITLES[p][0];
  document.querySelector('.top .crumb').textContent='Onion Market Intelligence  ›  '+TITLES[p][1];
  window.scrollTo({top:0,behavior:'smooth'});}
document.querySelectorAll('.nav a').forEach(t=>{t.onclick=()=>go(t.dataset.p);
  t.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();go(t.dataset.p);}};});

// exec summary
const I=D.insights;
document.getElementById('exec').innerHTML=
  `<div class="ex"><div class="q">🗓️ When to sell</div><div class="a">${I.peak_month} (peak)</div>
    <div class="d">${INR(I.peak_price)}/qtl in ${I.peak_month} vs ${INR(I.trough_price)} in ${I.trough_month} — timing is worth <b>${INR(I.timing_gain)}/qtl</b>.</div></div>
   <div class="ex"><div class="q">📍 Where to sell</div><div class="a">${I.top_market.replace(' APMC','')}</div>
    <div class="d">Pays ${INR(I.top_market_price)}/qtl — about <b>${INR(I.market_spread)}/qtl</b> more than the cheapest market (gross of transport).</div></div>
   <div class="ex"><div class="q">🧅 Which variety</div><div class="a">Red onion</div>
    <div class="d">Averages ${INR(D.variety_avg.Red)}/qtl — roughly <b>+${Math.round((D.variety_avg.Red/D.variety_avg.Local-1)*100)}%</b> over Local onion.</div></div>`;

function kpi(ic,l,v,s){return `<div class="kpi"><div class="chipi">${ic}</div><div><div class="lbl">${l}</div><div class="val">${v}</div><div class="sub">${s}</div></div></div>`;}
document.getElementById('kpis1').innerHTML=
  kpi('📅','Best month',I.peak_month,INR(I.peak_price)+'/qtl peak')+
  kpi('📉','Worst month',I.trough_month,INR(I.trough_price)+'/qtl trough')+
  kpi('💰','Timing worth',INR(I.timing_gain),'per quintal (peak − trough)')+
  kpi('🏆','Top market',I.top_market.replace(' APMC',''),INR(I.top_market_price)+'/qtl');
const vTop=Object.entries(D.variety_avg).sort((a,b)=>b[1]-a[1]);
document.getElementById('kpis2').innerHTML=
  kpi('🥇','Top variety',vTop[0][0],INR(vTop[0][1])+'/qtl avg')+
  kpi('📈','Red vs Local','+'+Math.round((D.variety_avg.Red/D.variety_avg.Local-1)*100)+'%','price premium')+
  kpi('🥉','Lowest variety',vTop[vTop.length-1][0],INR(vTop[vTop.length-1][1])+'/qtl');
document.getElementById('varInsight').innerHTML='💡 <b>Red onion</b> earns the highest price in almost every month — a crop-planning lever worth about ₹'+INRk(D.variety_avg.Red-D.variety_avg.Local)+'/quintal over Local.';
const f0=D.forecast[0];
document.getElementById('kpis3').innerHTML=
  kpi('🏆','Best next month',f0.name.replace(' APMC',''),'rank #1 for '+D.forecast_month)+
  kpi('🔮','Forecast price',INR(f0.p),'range '+INR(f0.lo)+'–'+INRk(f0.hi))+
  kpi('🎯','Backtest error','~14%','₹168/qtl mean');
document.getElementById('fcMonth').textContent=D.forecast_month;

// seasonal
const mkSel=document.getElementById('marketSel');
mkSel.innerHTML='<option value="">— state average only —</option>'+Object.keys(D.markets_seasonal).map(m=>`<option>${m}</option>`).join('');
let seasonal;
function drawSeasonal(){const ds=[{label:'State average',data:D.state_by_month,borderColor:A,backgroundColor:A,borderWidth:3,tension:.35,pointRadius:3,fill:false}];
  if(mkSel.value)ds.push({label:mkSel.value.replace(' APMC',''),data:D.markets_seasonal[mkSel.value],borderColor:P,borderWidth:2,borderDash:[6,4],tension:.35,pointRadius:2});
  if(seasonal)seasonal.destroy();
  seasonal=new Chart(seasonalChart,{type:'line',data:{labels:months,datasets:ds},
    options:{maintainAspectRatio:false,plugins:{legend:{position:'top'},tooltip:{callbacks:{label:c=>c.dataset.label+': '+INR(c.raw)}}},
      scales:{y:{title:{display:true,text:'₹ / quintal'},ticks:{callback:v=>'₹'+INRk(v)}}}}});}
mkSel.onchange=drawSeasonal;drawSeasonal();

new Chart(marketChart,{type:'bar',data:{labels:D.market_summary.map(m=>m.name.replace(' APMC','')),
  datasets:[{data:D.market_summary.map(m=>m.price),backgroundColor:D.market_summary.map((m,i)=>i===0?A:P),borderRadius:4}]},
  options:{indexAxis:'y',maintainAspectRatio:false,plugins:{legend:{display:false},
    tooltip:{callbacks:{label:c=>INR(c.raw)+'  ('+(D.market_summary[c.dataIndex].vs>0?'+':'')+D.market_summary[c.dataIndex].vs+'% vs state)'}}},
    scales:{x:{title:{display:true,text:'Average ₹ / quintal'},ticks:{callback:v=>'₹'+INRk(v)}}}}});

function hcol(v){if(v==null)return '#fff';if(v>=115)return '#2f855a';if(v>=100)return '#c6f0d4';if(v>=85)return '#fde9c8';return '#eceae8';}
function hfg(v){return (v!=null&&v>=115)?'#fff':'#1b1420';}
let h='<thead><tr><th class="name">Market</th>'+months.map(m=>`<th>${m}</th>`).join('')+'</tr></thead><tbody>';
for(const[name,arr]of Object.entries(D.rec_index))h+=`<tr><td class="name">${name.replace(' APMC','')}</td>`+arr.map(v=>`<td style="background:${hcol(v)};color:${hfg(v)};font-weight:600">${v??''}</td>`).join('')+'</tr>';
document.getElementById('heatmap').innerHTML=h+'</tbody>';

const vcol={Red:A,Local:G,Other:MUT,Unhali:GOLD,White:'#805ad5'};
new Chart(varietyChart,{type:'line',data:{labels:months,datasets:Object.entries(D.variety).map(([k,v])=>({label:k,data:v,borderColor:vcol[k]||MUT,backgroundColor:vcol[k]||MUT,borderWidth:k==='Red'?3:1.8,tension:.3,spanGaps:true,pointRadius:2}))},
  options:{maintainAspectRatio:false,plugins:{legend:{position:'top'},tooltip:{callbacks:{label:c=>c.dataset.label+': '+INR(c.raw)}}},scales:{y:{title:{display:true,text:'₹ / quintal'},ticks:{callback:v=>'₹'+INRk(v)}}}}});
const va=Object.entries(D.variety_avg).sort((a,b)=>b[1]-a[1]);
new Chart(varietyBar,{type:'bar',data:{labels:va.map(x=>x[0]),datasets:[{data:va.map(x=>x[1]),backgroundColor:va.map((x,i)=>i===0?A:P),borderRadius:4}]},
  options:{maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>INR(c.raw)}}},scales:{y:{title:{display:true,text:'Average ₹ / quintal'},ticks:{callback:v=>'₹'+INRk(v)}}}}});

const fc=D.forecast;
new Chart(forecastChart,{type:'bar',data:{labels:fc.map(f=>f.name.replace(' APMC','')),
  datasets:[{label:'Likely range',data:fc.map(f=>[f.lo,f.hi]),backgroundColor:fc.map((f,i)=>i===0?'#e8a687':'#dcc9d6'),barPercentage:0.6,borderRadius:3},
    {label:'Forecast',data:fc.map(f=>[f.p-10,f.p+10]),backgroundColor:fc.map((f,i)=>i===0?A:P),barPercentage:0.6}]},
  options:{indexAxis:'y',maintainAspectRatio:false,plugins:{legend:{position:'top'},
    tooltip:{callbacks:{title:c=>fc[c[0].dataIndex].name,label:c=>{const f=fc[c.dataIndex];return 'Forecast '+INR(f.p)+' (range '+INR(f.lo)+'–'+INRk(f.hi)+', '+(f.chg>0?'+':'')+f.chg+'%)';}}}},
    scales:{x:{title:{display:true,text:'Predicted ₹ / quintal'},ticks:{callback:v=>'₹'+INRk(v)}},y:{stacked:true}}}});

new Chart(coefChart,{type:'bar',data:{labels:D.coef.map(c=>c.m),datasets:[{data:D.coef.map(c=>c.v),
  backgroundColor:D.coef.map(c=>c.v>=0?(c.sig?A:'#e8a687'):(c.sig?P:'#c9b6c3')),borderRadius:4}]},
  options:{maintainAspectRatio:false,plugins:{legend:{display:false},tooltip:{callbacks:{label:c=>(c.raw>0?'+':'')+INR(c.raw)+' vs Jan'+(D.coef[c.dataIndex].sig?'':' (not significant)')}}},
    scales:{y:{title:{display:true,text:'₹ / quintal vs January'},ticks:{callback:v=>'₹'+INRk(v)}}}}});

// coverage table
let ct='<thead><tr><th class="name">Market</th><th>Days</th><th>Coverage</th></tr></thead><tbody>';
D.coverage.forEach(r=>{ct+=`<tr><td class="name">${r.name.replace(' APMC','')}</td><td>${r.days}</td><td>${r.cov}%</td></tr>`;});
document.getElementById('covTable').innerHTML=ct+'</tbody>';

/* ---------- PROFIT CALCULATOR ---------- */
const locSel=document.getElementById('cLoc'),varSel=document.getElementById('cVar');
locSel.innerHTML=Object.keys(D.districts).map(k=>`<option${k==='Nashik'?' selected':''}>${k}</option>`).join('');
varSel.innerHTML=Object.keys(D.variety_factor).map(k=>`<option${k==='Red'?' selected':''}>${k}</option>`).join('');
function haversine(a,b,c,d){const R=6371,r=Math.PI/180,dφ=(c-a)*r,dλ=(d-b)*r;
  const x=Math.sin(dφ/2)**2+Math.cos(a*r)*Math.cos(c*r)*Math.sin(dλ/2)**2;return 2*R*Math.asin(Math.sqrt(x));}
function num(id,def,min){let v=parseFloat(document.getElementById(id).value);if(isNaN(v)||v<(min??-1e9))v=def;return v;}
let breakdown;
function calc(){
  const loc=D.districts[locSel.value],qty=num('cQty',50,1),vf=D.variety_factor[varSel.value]||1;
  const rate=num('cRate',0.5,0),lab=num('cLab',30,0),comm=num('cComm',6,0)/100;
  const rows=D.calc_mandis.map(m=>{
    const dist=Math.round(haversine(loc[0],loc[1],m.lat,m.lng)*1.3);
    const price=Math.round(m.price*vf),transport=dist*rate,commission=price*comm;
    const net=price-transport-commission-lab;
    return{name:m.name,dist,price,transport:Math.round(transport),commission:Math.round(commission),lab,
      netQtl:Math.round(net),netTotal:Math.round(net*qty)};
  }).sort((a,b)=>b.netTotal-a.netTotal);
  const w=rows[0],second=rows[1];
  document.getElementById('cWinner').innerHTML=
    `<div class="winner"><div class="t">✅ Best mandi for you</div><div class="m">🏆 ${w.name.replace(' APMC','')}</div>
     <div class="big">${INR(w.netTotal)}</div>
     <div class="n">take-home for ${qty} quintals of ${varSel.value} onion &nbsp;·&nbsp; ${INR(w.netQtl)}/qtl net &nbsp;·&nbsp; ${w.dist} km away<br>
     That's <b>${INR(w.netTotal-second.netTotal)}</b> more than the next best (${second.name.replace(' APMC','')}, ${INR(second.netTotal)}).</div></div>`;
  // breakdown chart (per quintal)
  if(breakdown)breakdown.destroy();
  breakdown=new Chart(document.getElementById('breakdownChart'),{type:'bar',
    data:{labels:['₹ / quintal'],datasets:[
      {label:'You keep (net)',data:[w.netQtl],backgroundColor:G,borderRadius:4},
      {label:'Transport',data:[w.transport],backgroundColor:A},
      {label:'Commission',data:[w.commission],backgroundColor:GOLD},
      {label:'Labour',data:[w.lab],backgroundColor:P}]},
    options:{indexAxis:'y',maintainAspectRatio:false,plugins:{legend:{position:'bottom'},
      tooltip:{callbacks:{label:c=>c.dataset.label+': '+INR(c.raw)}}},
      scales:{x:{stacked:true,ticks:{callback:v=>'₹'+INRk(v)},title:{display:true,text:'Gross price = '+INR(w.price)+'/qtl'}},y:{stacked:true}}}});
  // table
  let t='<thead><tr><th class="name">Mandi</th><th>Dist (km)</th><th>Price ₹/qtl</th><th>Transport</th><th>Commission</th><th>Net ₹/qtl</th><th>Take-home</th></tr></thead><tbody>';
  rows.forEach((r,i)=>{const far=r.dist>300?' <span title="over 300 km">⚠</span>':'';
    t+=`<tr style="${i===0?'background:#eafaf0;font-weight:700':''}"><td class="name">${r.name.replace(' APMC','')}${far}</td>
    <td>${r.dist}</td><td>${INRk(r.price)}</td><td>−${INRk(r.transport)}</td><td>−${INRk(r.commission)}</td>
    <td>${INRk(r.netQtl)}</td><td>${INR(r.netTotal)}</td></tr>`;});
  document.getElementById('cTable').innerHTML=t+'</tbody>';
  document.getElementById('cAssume').innerHTML=
    `<b>Assumptions</b> (adjustable): transport ₹${rate}/km/qtl · labour ₹${lab}/qtl · commission ${(comm*100).toFixed(1)}%. `+
    `Price = ${varSel.value} estimate per mandi. Distance = straight-line × 1.3 road factor. This is a net <b>estimate</b>, not a guarantee.`;
}
document.getElementById('cGo').onclick=calc;
[locSel,varSel,document.getElementById('cQty'),document.getElementById('cRate'),document.getElementById('cLab'),document.getElementById('cComm')].forEach(e=>e.onchange=calc);
calc();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
