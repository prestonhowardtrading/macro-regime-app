import streamlit as st
import anthropic
import json

st.set_page_config(layout="wide", page_title="Regime.ai")

# ================================================
# SAMPLE SCORES
# ================================================

growth_score    = 35
inflation_score = -10
liquidity_score = 50

risk_appetite = (
    0.5 * liquidity_score +
    0.3 * growth_score +
    0.2 * inflation_score
)
risk_appetite         = max(min(risk_appetite, 100), -100)
risk_appetite_rounded = round(risk_appetite, 1)

# ================================================
# REGIME LOGIC
# ================================================

if risk_appetite > 0 and inflation_score > 0:
    regime = "Risk-On Inflation"
elif risk_appetite < 0 and inflation_score > 0:
    regime = "Risk-Off Inflation"
elif risk_appetite > 0 and inflation_score < 0:
    regime = "Risk-On Disinflation"
else:
    regime = "Risk-Off Disinflation"

REGIME_CONFIG = {
    "Risk-On Inflation": {
        "color":  "#FF6B35", "bg": "rgba(255,107,53,0.12)", "border": "rgba(255,107,53,0.4)",
        "icon": "↗", "desc": "Growth accelerating + Prices rising",
        "favor": ["Commodities", "Energy", "Financials", "TIPS", "EM equities"],
    },
    "Risk-On Disinflation": {
        "color":  "#00D4AA", "bg": "rgba(0,212,170,0.12)", "border": "rgba(0,212,170,0.4)",
        "icon": "↗", "desc": "Growth accelerating + Prices cooling",
        "favor": ["Growth equities", "Tech", "Small caps", "Corp bonds", "Crypto"],
    },
    "Risk-Off Inflation": {
        "color":  "#FF4757", "bg": "rgba(255,71,87,0.12)", "border": "rgba(255,71,87,0.4)",
        "icon": "↘", "desc": "Growth slowing + Prices rising",
        "favor": ["Gold", "Commodities", "Short-dur bonds", "Cash", "Defensives"],
    },
    "Risk-Off Disinflation": {
        "color":  "#5B8DEF", "bg": "rgba(91,141,239,0.12)", "border": "rgba(91,141,239,0.4)",
        "icon": "↘", "desc": "Growth slowing + Prices cooling",
        "favor": ["Long-duration Treasuries", "Gold", "Cash", "Utilities", "REITs"],
    },
}
cfg = REGIME_CONFIG.get(regime, REGIME_CONFIG["Risk-On Disinflation"])

# ================================================
# HISTORICAL DATA
# ================================================

historical_data = [
    {"month": "October 2024",  "regime": "Risk-On Inflation",     "liquidity": 45,  "growth": 40,  "inflation": 30,  "risk_appetite": 46.5,  "color": "#FF6B35"},
    {"month": "November 2024", "regime": "Risk-On Inflation",     "liquidity": 55,  "growth": 42,  "inflation": 20,  "risk_appetite": 52.1,  "color": "#FF6B35"},
    {"month": "December 2024", "regime": "Risk-Off Inflation",    "liquidity": -20, "growth": 10,  "inflation": 25,  "risk_appetite": -4.0,  "color": "#FF4757"},
    {"month": "January 2025",  "regime": "Risk-Off Disinflation", "liquidity": -35, "growth": -15, "inflation": -18, "risk_appetite": -26.1, "color": "#5B8DEF"},
    {"month": "February 2025", "regime": "Risk-On Disinflation",  "liquidity": 30,  "growth": 20,  "inflation": -5,  "risk_appetite": 21.0,  "color": "#00D4AA"},
    {"month": "March 2025",    "regime": "Risk-On Disinflation",  "liquidity": 50,  "growth": 35,  "inflation": -10, "risk_appetite": risk_appetite_rounded, "color": "#00D4AA"},
]

# ================================================
# COMPONENT BREAKDOWN DATA  (mock values)
# Each indicator: label, value_str, contribution (points added to subscore), max_abs
# ================================================

GROWTH_COMPONENTS = {
    "Monetary Policy": {
        "weight": "25%", "score": 10, "max": 55,
        "indicators": [
            {"label": "Rate Cut Probability (3M)",  "value": "52%",           "points": +10, "note": "CME FedWatch — moderate cut expected"},
            {"label": "Real Rates (10Y TIPS)",       "value": "1.82% (↓0.3%)", "points":  0,  "note": "Stable over past 3 months"},
            {"label": "Fed Balance Sheet YoY",       "value": "$6.71T (−1.2%)","points": -10, "note": "Active QT, slight contraction"},
            {"label": "Yield Curve (10Y−2Y)",        "value": "+18 bps",       "points":  0,  "note": "Flat — not yet steepening"},
        ]
    },
    "Global Liquidity": {
        "weight": "20%", "score": 10, "max": 20,
        "indicators": [
            {"label": "Global CB Balance Sheets YoY","value": "+3.2%",         "points": +10, "note": "ECB + BOJ expanding, Fed contracting"},
        ]
    },
    "Fiscal Policy": {
        "weight": "15%", "score": 15, "max": 40,
        "indicators": [
            {"label": "Gov't Spending Growth YoY",   "value": "+6.1%",         "points": +15, "note": "Above 5% threshold"},
            {"label": "Federal Deficit Change",      "value": "−0.3% GDP",     "points":  0,  "note": "Stable, no major change"},
            {"label": "Stimulus Legislation",        "value": "None active",   "points":  0,  "note": "No major bills in pipeline"},
        ]
    },
    "Labor Market": {
        "weight": "15%", "score": 5, "max": 25,
        "indicators": [
            {"label": "Unemployment Rate",           "value": "4.1% (−0.1%)",  "points": +5,  "note": "Stable over 6 months"},
            {"label": "Initial Jobless Claims",      "value": "221K (stable)", "points":  0,  "note": "No clear trend"},
        ]
    },
    "Leading Indicators": {
        "weight": "15%", "score": 8, "max": 30,
        "indicators": [
            {"label": "ISM Manufacturing PMI",       "value": "49.8",          "points":  0,  "note": "Contractionary, but improving"},
            {"label": "ISM Services PMI",            "value": "53.5",          "points": +4,  "note": "Healthy expansion"},
            {"label": "Conference Board LEI",        "value": "−0.3% (6M)",    "points": -5,  "note": "Slight decline"},
            {"label": "Retail Sales YoY",            "value": "+3.1%",         "points": +3,  "note": "Moderate growth"},
            {"label": "Atlanta Fed GDPNow",          "value": "2.4%",          "points": +3,  "note": "Above 2% forecast"},
        ]
    },
    "Dollar Strength": {
        "weight": "10%", "score": -5, "max": 15,
        "indicators": [
            {"label": "DXY 3-Month Change",          "value": "104.2 (+2.3%)", "points": -5,  "note": "Modest dollar strength headwind"},
        ]
    },
}

INFLATION_COMPONENTS = {
    "Inflation Data": {
        "weight": "25%", "score": 10, "max": 40,
        "indicators": [
            {"label": "CPI MoM",                     "value": "+0.2%",         "points": +10, "note": "Rising 0.1–0.3% range"},
            {"label": "Core PCE",                    "value": "2.6%",          "points": +5,  "note": "Between 2–3%, mild pressure"},
            {"label": "PPI Trend",                   "value": "Falling",       "points": -10, "note": "Producer prices easing"},
        ]
    },
    "Commodity Prices": {
        "weight": "20%", "score": -5, "max": 15,
        "indicators": [
            {"label": "BCOM Index (6M Change)",      "value": "−6.2%",         "points": -5,  "note": "Moderate commodity decline"},
        ]
    },
    "Monetary Policy": {
        "weight": "20%", "score": 5, "max": 40,
        "indicators": [
            {"label": "Rate Cut Expectations",       "value": "Moderate easing","points": +5,  "note": "1–2 cuts priced in"},
            {"label": "Real Rates Trend",            "value": "Stable",        "points":  0,  "note": "No major move"},
            {"label": "Fed Balance Sheet",           "value": "Shrinking (QT)","points": -10, "note": "Deflationary pressure"},
        ]
    },
    "Labor Market (Wages)": {
        "weight": "20%", "score": 5, "max": 15,
        "indicators": [
            {"label": "Avg Hourly Earnings YoY",     "value": "+3.9%",         "points": +5,  "note": "Wage growth 3–5% range"},
        ]
    },
    "Inflation Expectations": {
        "weight": "15%", "score": -5, "max": 15,
        "indicators": [
            {"label": "5Y Breakeven Rate (3M Chg)",  "value": "2.31% (−0.18%)","points": -5,  "note": "Expectations drifting lower"},
        ]
    },
}

LIQUIDITY_COMPONENTS = {
    "Central Bank Balance Sheets": {
        "weight": "40%", "score": 30, "max": 40,
        "indicators": [
            {"label": "Federal Reserve (50%)",       "value": "$6.71T (−1.2%)","points": -10, "note": "Contraction 1–5% YoY"},
            {"label": "ECB (20%)",                   "value": "€6.4T (+4.8%)", "points": +25, "note": "Expansion 5–10% YoY"},
            {"label": "Bank of Japan (20%)",         "value": "¥760T (+6.1%)", "points": +25, "note": "Expansion 5–10% YoY"},
            {"label": "PBOC (10%)",                  "value": "¥44.8T (+2.1%)","points": +10, "note": "Expansion 1–5% YoY"},
        ]
    },
    "Treasury Liquidity (TGA/RRP)": {
        "weight": "20%", "score": 15, "max": 20,
        "indicators": [
            {"label": "Treasury Gen. Account (TGA)", "value": "$412B (↓$180B)","points": +10, "note": "Drawdown injects liquidity"},
            {"label": "Reverse Repo (RRP)",          "value": "$98B (↓ rapid)", "points": +15, "note": "RRP drainage, bullish liquidity"},
            {"label": "Net Liquidity Trend",         "value": "+3.8% (3M ROC)","points": +10, "note": "Net liquidity expanding"},
        ]
    },
    "Market Liquidity Conditions": {
        "weight": "15%", "score": 5, "max": 15,
        "indicators": [
            {"label": "Real Rates",                  "value": "1.82% (stable)","points":  0,  "note": "Flat, no clear signal"},
            {"label": "M2 Growth YoY",               "value": "+4.2%",         "points": +5,  "note": "4–8% range, mild support"},
            {"label": "Chicago Fed NFCI (ΔFCI)",     "value": "−0.08 (3M chg)","points": +5,  "note": "Slight easing conditions"},
        ]
    },
    "Dollar Liquidity (DXY)": {
        "weight": "15%", "score": -5, "max": 15,
        "indicators": [
            {"label": "DXY 3-Month ROC",             "value": "+2.3%",         "points": -10, "note": "Dollar rising, tightening"},
            {"label": "DXY vs 200-Day MA",           "value": "+1.1% above",   "points":  0,  "note": "Within ±2%, neutral"},
        ]
    },
    "Credit Liquidity": {
        "weight": "10%", "score": 5, "max": 10,
        "indicators": [
            {"label": "High Yield Spread",           "value": "312 bps (−55)", "points": +5,  "note": "Tightening 50–100 bps"},
            {"label": "Investment Grade Spread",     "value": "95 bps (−18)",  "points": +3,  "note": "Tightening 5–20 bps"},
            {"label": "Bank Lending Standards",      "value": "Net −4% easing","points": +3,  "note": "Small easing"},
        ]
    },
}

# ================================================
# HELPERS
# ================================================

def fmt_score(val):
    sign = "+" if val > 0 else ""
    if isinstance(val, float) and val == int(val):
        return sign + str(int(val))
    return sign + str(val)

def signal_text(score, label):
    if label == "Growth":     return "Expanding"  if score > 20 else ("Contracting" if score < -20 else "Neutral")
    if label == "Inflation":  return "Inflationary" if score > 20 else ("Deflationary" if score < -20 else "Neutral")
    if label == "Liquidity":  return "Abundant"   if score > 20 else ("Tight"        if score < -20 else "Neutral")
    if label == "Risk Appetite": return "Risk-On" if score > 20 else ("Risk-Off"     if score < -20 else "Neutral")
    return ""

def gauge_bar(score, color, height="6px"):
    pct   = abs(score) / 2
    left  = "50%" if score >= 0 else str(round(50 - pct, 1)) + "%"
    width = str(round(pct, 1)) + "%"
    return (
        '<div class="gauge-track" style="height:' + height + ';">'
        '<div class="gauge-mid"></div>'
        '<div class="gauge-fill" style="left:' + left + ';width:' + width + ';background:' + color + ';"></div>'
        '</div>'
    )

def mini_bar(score, max_abs, color):
    """Simple left-to-right bar for component scores (not centered)."""
    pct = round(min(100, abs(score) / max_abs * 100), 1)
    bg  = color if score >= 0 else "#FF4757"
    return (
        '<div style="height:3px;background:rgba(255,255,255,0.06);border-radius:2px;overflow:hidden;margin-top:4px;">'
        '<div style="height:100%;width:' + str(pct) + '%;background:' + bg + ';border-radius:2px;"></div>'
        '</div>'
    )

def score_pill(val):
    css = "pill-pos" if val > 0 else ("pill-neg" if val < 0 else "pill-neu")
    return '<span class="score-pill ' + css + '">' + fmt_score(val) + '</span>'

def regime_badge_html(row):
    c = row["color"]
    return '<span class="regime-badge" style="background:' + c + '22;border:1px solid ' + c + ';color:' + c + ';">' + row["regime"] + '</span>'

def points_badge(pts):
    if pts > 0:
        return '<span class="pts-badge pts-pos">' + fmt_score(pts) + '</span>'
    elif pts < 0:
        return '<span class="pts-badge pts-neg">' + fmt_score(pts) + '</span>'
    return '<span class="pts-badge pts-neu">0</span>'

def build_component_section(components, accent_color):
    """Build the full component breakdown HTML for one score category."""
    html = '<div class="comp-grid">'
    for cat_name, cat in components.items():
        cat_score = cat["score"]
        cat_max   = cat["max"]
        bar_pct   = round(min(100, abs(cat_score) / cat_max * 100), 1)
        bar_color = accent_color if cat_score >= 0 else "#FF4757"

        html += (
            '<div class="comp-card">'
            # Header row
            '<div class="comp-card-header">'
            '<div>'
            '<div class="comp-cat-name">' + cat_name + '</div>'
            '<div class="comp-cat-weight">' + cat["weight"] + ' weight</div>'
            '</div>'
            '<div class="comp-cat-score" style="color:' + bar_color + ';">' + fmt_score(cat_score) + '</div>'
            '</div>'
            # Score bar
            '<div style="height:3px;background:rgba(255,255,255,0.06);border-radius:2px;overflow:hidden;margin:10px 0 14px;">'
            '<div style="height:100%;width:' + str(bar_pct) + '%;background:' + bar_color + ';border-radius:2px;"></div>'
            '</div>'
        )

        # Individual indicators
        for ind in cat["indicators"]:
            pts = ind["points"]
            pts_color = accent_color if pts > 0 else ("#FF4757" if pts < 0 else "#555")
            html += (
                '<div class="ind-row">'
                '<div class="ind-left">'
                '<div class="ind-label">' + ind["label"] + '</div>'
                '<div class="ind-note">' + ind["note"] + '</div>'
                '</div>'
                '<div class="ind-right">'
                '<div class="ind-value">' + ind["value"] + '</div>'
                '<div class="ind-pts" style="color:' + pts_color + ';">' + fmt_score(pts) + ' pts</div>'
                '</div>'
                '</div>'
            )

        html += '</div>'  # close comp-card

    html += '</div>'  # close comp-grid
    return html

# ================================================
# AI ANALYSIS
# ================================================

def get_ai_analysis(growth, inflation, liquidity, risk_app, regime_name):
    client = anthropic.Anthropic()
    prompt = (
        "You are a macro economist and financial analyst. Analyze the following macro regime scores.\n\n"
        "Scores:\n"
        "- Growth Score: "        + str(growth)            + " (-100 to 100)\n"
        "- Inflation Score: "     + str(inflation)          + " (-100 to 100)\n"
        "- Liquidity Score: "     + str(liquidity)          + " (-100 to 100)\n"
        "- Risk Appetite Score: " + str(round(risk_app, 1)) + "\n"
        "- Current Regime: "      + regime_name             + "\n\n"
        "Return ONLY valid JSON, no markdown:\n"
        "{\n"
        '  "growth_interpretation": "2-sentence interpretation",\n'
        '  "inflation_interpretation": "2-sentence interpretation",\n'
        '  "liquidity_interpretation": "2-sentence interpretation",\n'
        '  "risk_appetite_interpretation": "2-sentence interpretation",\n'
        '  "regime_summary": "3-4 sentence macro summary for investors",\n'
        '  "key_watch": "One specific indicator to watch"\n'
        "}"
    )
    msg = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = msg.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

# ================================================
# CSS
# ================================================

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500;600&display=swap');

html, body, [class*="st-"], [data-testid] {
    font-family: 'DM Sans', sans-serif !important;
    background-color: #0A0A0F;
    color: #E8E8E8;
}
[data-testid="stAppViewContainer"] { background: #0A0A0F; }
[data-testid="stHeader"]           { background: #0A0A0F; }
section[data-testid="stMain"]      { background: #0A0A0F; }

/* ── HEADER ── */
.hdr-dot     { width:6px;height:6px;border-radius:50%;background:#00D4AA;box-shadow:0 0 8px #00D4AA;display:inline-block;margin-right:8px;vertical-align:middle; }
.hdr-eyebrow { font-size:10px;letter-spacing:0.2em;color:#555;text-transform:uppercase;font-family:'DM Mono',monospace;margin-bottom:4px; }
.hdr-title   { margin:0;font-size:28px;font-weight:600;letter-spacing:-0.02em;line-height:1.1;color:#E8E8E8; }
.hdr-sub     { margin:6px 0 0;font-size:12px;color:#555; }

/* ── QUADRANT PANEL ── */
.quad-panel {
    background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);
    border-radius:14px;padding:20px 18px 16px 18px;
}
.quad-panel-title {
    font-size:10px;letter-spacing:0.18em;text-transform:uppercase;
    color:#555;font-family:'DM Mono',monospace;margin-bottom:14px;
    display:flex;align-items:center;gap:8px;
}
.quad-panel-title::before { content:'↗';color:#00D4AA;font-size:12px; }

/* The aspect-ratio trick: 80% makes it shorter than wide */
.quad-wrap {
    position:relative;width:100%;padding-bottom:80%;
    background:rgba(255,255,255,0.02);border-radius:10px;
    border:1px solid rgba(255,255,255,0.06);overflow:hidden;
}
.quad-inner  { position:absolute;inset:0; }
.quad-q      { position:absolute; }
.quad-axis-v { position:absolute;left:50%;top:0;bottom:0;width:1px;background:rgba(255,255,255,0.08); }
.quad-axis-h { position:absolute;top:50%;left:0;right:0;height:1px;background:rgba(255,255,255,0.08); }
.quad-dot    { position:absolute;width:14px;height:14px;border-radius:50%;z-index:10; }
.quad-ring   { position:absolute;width:28px;height:28px;border-radius:50%;z-index:9; }

/* ── SIDEBAR ── */
.sidebar-card { background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:14px;padding:20px; }
.sidebar-card-title { font-size:10px;letter-spacing:0.18em;text-transform:uppercase;color:#555;font-family:'DM Mono',monospace;margin-bottom:16px; }
.mini-score-grid { display:grid;grid-template-columns:1fr 1fr;gap:8px; }
.mini-score { background:rgba(255,255,255,0.03);border:1px solid rgba(255,255,255,0.06);border-radius:8px;padding:12px 14px; }
.mini-score-lbl { font-size:9px;letter-spacing:0.15em;color:#555;font-family:'DM Mono',monospace;margin-bottom:4px; }
.mini-score-val { font-size:22px;font-weight:700;font-family:'DM Mono',monospace;line-height:1; }

/* ── ASSET TAG ── */
.asset-tag { display:inline-block;font-size:10px;padding:3px 8px;border-radius:4px;margin:2px;font-family:'DM Mono',monospace; }

/* ── SECTION LABEL ── */
.sec-label { font-size:10px;letter-spacing:0.15em;color:#555;text-transform:uppercase;font-family:'DM Mono',monospace;
    margin-bottom:14px;margin-top:32px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,0.06); }

/* ── GAUGE ── */
.gauge-track { background:rgba(255,255,255,0.06);border-radius:3px;overflow:hidden;position:relative;margin-bottom:6px; }
.gauge-mid   { position:absolute;left:50%;top:0;width:1px;height:100%;background:rgba(255,255,255,0.2);z-index:2; }
.gauge-fill  { position:absolute;height:100%;border-radius:3px; }
.gauge-foot  { display:flex;justify-content:space-between; }
.gauge-foot span { font-size:9px;color:#555;font-family:'DM Mono',monospace; }

/* ── COMPONENT BREAKDOWN TABS ── */
.tab-bar { display:flex;border-bottom:1px solid rgba(255,255,255,0.06);margin-bottom:0; }
.tab-btn {
    padding:12px 20px;background:transparent;border:none;cursor:pointer;
    font-size:11px;font-weight:400;color:#555;letter-spacing:0.08em;text-transform:uppercase;
    font-family:'DM Mono',monospace;border-bottom:2px solid transparent;
    transition:all 0.2s;
}
.tab-btn.active { color:#E8E8E8;font-weight:600; }
.tab-btn.active-growth    { border-bottom-color:#00D4AA; }
.tab-btn.active-inflation { border-bottom-color:#FF6B35; }
.tab-btn.active-liquidity { border-bottom-color:#5B8DEF; }

/* ── COMPONENT GRID ── */
.comp-grid { display:grid;grid-template-columns:repeat(3,1fr);gap:12px;padding:20px 0 4px 0; }

.comp-card {
    background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);
    border-radius:10px;padding:16px;
}
.comp-card-header { display:flex;justify-content:space-between;align-items:flex-start; }
.comp-cat-name   { font-size:11px;font-weight:600;color:#E8E8E8;margin-bottom:2px; }
.comp-cat-weight { font-size:9px;color:#555;font-family:'DM Mono',monospace;letter-spacing:0.08em; }
.comp-cat-score  { font-size:20px;font-weight:700;font-family:'DM Mono',monospace;line-height:1; }

/* ── INDICATOR ROWS ── */
.ind-row {
    display:flex;justify-content:space-between;align-items:flex-start;
    padding:8px 0;border-top:1px solid rgba(255,255,255,0.04);
}
.ind-left  { flex:1;min-width:0; }
.ind-label { font-size:11px;color:#aaa;margin-bottom:2px; }
.ind-note  { font-size:10px;color:#555;font-family:'DM Mono',monospace;line-height:1.3; }
.ind-right { text-align:right;flex-shrink:0;margin-left:12px; }
.ind-value { font-size:11px;color:#E8E8E8;font-family:'DM Mono',monospace;margin-bottom:2px; }
.ind-pts   { font-size:11px;font-weight:600;font-family:'DM Mono',monospace; }

/* ── SUMMARY / AI ── */
.summary-box { padding:14px 18px;border-radius:10px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);font-size:12px;color:#888;line-height:1.7;margin-bottom:20px; }
.ai-grid { display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:14px; }
.ai-card { padding:16px;border-radius:10px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06); }
.ai-card-lbl { font-size:9px;letter-spacing:0.15em;text-transform:uppercase;font-family:'DM Mono',monospace;margin-bottom:6px; }
.ai-card-txt { font-size:12px;color:#888;line-height:1.6; }
.watch-box { display:flex;gap:10px;align-items:flex-start;padding:12px 16px;border-radius:8px;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06); }
.watch-txt { font-size:12px;color:#aaa;line-height:1.5; }

/* ── HISTORY TABLE ── */
.hist-wrap { border-radius:12px;overflow:hidden;background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06); }
.hist-table { width:100%;border-collapse:collapse; }
.hist-table th { font-size:9px;letter-spacing:0.15em;color:#555;text-transform:uppercase;font-family:'DM Mono',monospace;padding:12px 16px;text-align:left;border-bottom:1px solid rgba(255,255,255,0.06); }
.hist-table td { padding:13px 16px;font-size:11px;color:#aaa;border-bottom:1px solid rgba(255,255,255,0.04);font-family:'DM Mono',monospace; }
.hist-table tr:last-child td { border-bottom:none; }
.hist-current td { background:rgba(255,255,255,0.015); }
.hist-current td:first-child { border-left:2px solid #00D4AA; }
.regime-badge { display:inline-flex;align-items:center;gap:5px;padding:3px 9px;border-radius:4px;font-size:10px;font-weight:600;font-family:'DM Mono',monospace; }
.score-pill   { display:inline-block;padding:2px 7px;border-radius:4px;font-size:11px;font-weight:600;font-family:'DM Mono',monospace; }
.pill-pos { background:rgba(0,212,170,0.12);color:#00D4AA; }
.pill-neg { background:rgba(255,71,87,0.12);color:#FF4757; }
.pill-neu { background:rgba(255,255,255,0.05);color:#666; }
.cur-badge { display:inline-block;font-size:8px;letter-spacing:0.1em;padding:2px 5px;border-radius:3px;background:rgba(0,212,170,0.1);border:1px solid rgba(0,212,170,0.25);color:#00D4AA;margin-left:6px;font-family:'DM Mono',monospace; }
.month-txt { color:#666; }
</style>
""", unsafe_allow_html=True)

# ================================================
# HEADER
# ================================================

st.markdown(
    '<div class="hdr-eyebrow"><span class="hdr-dot"></span>Macro Regime Monitor</div>'
    '<h1 class="hdr-title">Regime<span style="color:#555;">.</span>ai</h1>'
    '<p class="hdr-sub">Real-time macro regime detection via live economic data</p>',
    unsafe_allow_html=True
)
st.markdown("<div style='margin-bottom:24px;'></div>", unsafe_allow_html=True)

# ================================================
# TOP LAYOUT: Quadrant (left, smaller) + Sidebar (right)
# ================================================

col_q, col_r = st.columns([3, 2])

qx        = round(50 + (growth_score    / 100) * 45, 2)
qy        = round(50 - (inflation_score / 100) * 45, 2)
dot_left  = str(round(qx - 7,  2)) + "%"
dot_top   = str(round(qy - 7,  2)) + "%"
ring_left = str(round(qx - 14, 2)) + "%"
ring_top  = str(round(qy - 14, 2)) + "%"

with col_q:
    st.markdown(
        '<div class="quad-panel">'
        '<div class="quad-panel-title">CURRENT MACRO ENVIRONMENT</div>'
        '<div style="text-align:center;font-size:9px;letter-spacing:0.15em;color:#FF4757;font-family:\'DM Mono\',monospace;margin-bottom:6px;">INFLATION</div>'
        '<div style="display:flex;align-items:stretch;gap:6px;">'
        '<div style="font-size:8px;letter-spacing:0.1em;color:#FF6B35;font-family:\'DM Mono\',monospace;writing-mode:vertical-rl;transform:rotate(180deg);white-space:nowrap;display:flex;align-items:center;justify-content:center;padding:0 2px;">RISK-OFF</div>'
        '<div class="quad-wrap" style="flex:1;">'
        '<div class="quad-inner">'
        '<div class="quad-q" style="left:50%;top:0;right:0;bottom:50%;background:rgba(255,107,53,0.07);"></div>'
        '<div class="quad-q" style="left:0;top:0;right:50%;bottom:50%;background:rgba(255,71,87,0.07);"></div>'
        '<div class="quad-q" style="left:50%;top:50%;right:0;bottom:0;background:rgba(0,212,170,0.07);"></div>'
        '<div class="quad-q" style="left:0;top:50%;right:50%;bottom:0;background:rgba(91,141,239,0.07);"></div>'
        '<div class="quad-axis-v"></div>'
        '<div class="quad-axis-h"></div>'
        '<div style="position:absolute;top:10%;left:53%;font-size:9px;color:rgba(255,107,53,0.4);font-family:\'DM Mono\',monospace;">Risk-On Inflation</div>'
        '<div style="position:absolute;top:10%;left:3%;font-size:9px;color:rgba(255,71,87,0.4);font-family:\'DM Mono\',monospace;">Risk-Off Inflation</div>'
        '<div style="position:absolute;top:76%;left:53%;font-size:9px;color:rgba(0,212,170,0.4);font-family:\'DM Mono\',monospace;">Risk-On Disinflation</div>'
        '<div style="position:absolute;top:76%;left:3%;font-size:9px;color:rgba(91,141,239,0.4);font-family:\'DM Mono\',monospace;">Risk-Off Disinflation</div>'
        '<div class="quad-dot" style="left:' + dot_left + ';top:' + dot_top + ';background:' + cfg["color"] + ';box-shadow:0 0 20px ' + cfg["color"] + '90;"></div>'
        '<div class="quad-ring" style="left:' + ring_left + ';top:' + ring_top + ';border:1px solid ' + cfg["color"] + '50;"></div>'
        '</div></div>'
        '<div style="font-size:8px;letter-spacing:0.1em;color:#00D4AA;font-family:\'DM Mono\',monospace;writing-mode:vertical-rl;white-space:nowrap;display:flex;align-items:center;justify-content:center;padding:0 2px;">RISK-ON</div>'
        '</div>'
        '<div style="text-align:center;font-size:9px;letter-spacing:0.15em;color:#5B8DEF;font-family:\'DM Mono\',monospace;margin-top:6px;">DISINFLATION</div>'
        '</div>',
        unsafe_allow_html=True
    )

favor_tags = ""
for asset in cfg["favor"]:
    favor_tags += (
        '<span class="asset-tag" style="background:' + cfg["color"] + '22;border:1px solid '
        + cfg["color"] + '44;color:' + cfg["color"] + ';">' + asset + '</span>'
    )

with col_r:
    # Regime Classification
    st.markdown(
        '<div class="sidebar-card" style="margin-bottom:16px;">'
        '<div class="sidebar-card-title">REGIME CLASSIFICATION</div>'
        '<div style="display:flex;align-items:center;gap:12px;padding:14px 16px;border-radius:10px;background:' + cfg["bg"] + ';border:1px solid ' + cfg["border"] + ';margin-bottom:16px;">'
        '<span style="font-size:24px;line-height:1;">' + cfg["icon"] + '</span>'
        '<div>'
        '<div style="font-size:17px;font-weight:600;color:' + cfg["color"] + ';letter-spacing:-0.01em;">' + regime + '</div>'
        '<div style="font-size:11px;color:#666;margin-top:3px;">' + cfg["desc"] + '</div>'
        '</div></div>'
        '<div class="mini-score-grid">'
        '<div class="mini-score"><div class="mini-score-lbl">GROWTH</div><div class="mini-score-val" style="color:#00D4AA;">' + fmt_score(growth_score) + '</div></div>'
        '<div class="mini-score"><div class="mini-score-lbl">INFLATION</div><div class="mini-score-val" style="color:#FF6B35;">' + fmt_score(inflation_score) + '</div></div>'
        '<div class="mini-score"><div class="mini-score-lbl">LIQUIDITY</div><div class="mini-score-val" style="color:#5B8DEF;">' + fmt_score(liquidity_score) + '</div></div>'
        '<div class="mini-score"><div class="mini-score-lbl">RISK APPETITE</div><div class="mini-score-val" style="color:' + cfg["color"] + ';">' + fmt_score(risk_appetite_rounded) + '</div></div>'
        '</div></div>',
        unsafe_allow_html=True
    )
    # Asset Allocation
    st.markdown(
        '<div class="sidebar-card">'
        '<div class="sidebar-card-title">ASSET ALLOCATION</div>'
        '<div style="font-size:10px;letter-spacing:0.12em;text-transform:uppercase;font-family:\'DM Mono\',monospace;color:#555;margin-bottom:10px;">Favored Assets</div>'
        '<div style="margin-bottom:14px;">' + favor_tags + '</div>'
        '<div style="font-size:12px;color:#555;line-height:1.6;">' + cfg["desc"] + '. Position portfolios accordingly with emphasis on the assets above.</div>'
        '</div>',
        unsafe_allow_html=True
    )

# ================================================
# SCORE COMPONENT BREAKDOWN (tabbed)
# ================================================

st.markdown('<div class="sec-label">Score Component Breakdown</div>', unsafe_allow_html=True)

# Tab state
if "score_tab" not in st.session_state:
    st.session_state.score_tab = "growth"

tab_col1, tab_col2, tab_col3, _ = st.columns([1, 1, 1, 4])
with tab_col1:
    if st.button("Growth  " + fmt_score(growth_score), key="tab_growth", use_container_width=True):
        st.session_state.score_tab = "growth"
with tab_col2:
    if st.button("Inflation  " + fmt_score(inflation_score), key="tab_inflation", use_container_width=True):
        st.session_state.score_tab = "inflation"
with tab_col3:
    if st.button("Liquidity  " + fmt_score(liquidity_score), key="tab_liquidity", use_container_width=True):
        st.session_state.score_tab = "liquidity"

active_tab = st.session_state.score_tab

if active_tab == "growth":
    accent = "#00D4AA"
    components = GROWTH_COMPONENTS
elif active_tab == "inflation":
    accent = "#FF6B35"
    components = INFLATION_COMPONENTS
else:
    accent = "#5B8DEF"
    components = LIQUIDITY_COMPONENTS

# Active tab indicator bar
tab_label_map = {"growth": "Growth Score", "inflation": "Inflation Score", "liquidity": "Liquidity Score"}
tab_score_map = {"growth": growth_score, "inflation": inflation_score, "liquidity": liquidity_score}

st.markdown(
    '<div style="height:2px;background:rgba(255,255,255,0.04);border-radius:1px;margin-bottom:4px;">'
    '<div style="height:100%;width:100%;background:' + accent + ';border-radius:1px;opacity:0.6;"></div>'
    '</div>'
    '<div style="font-size:11px;color:#666;font-family:\'DM Mono\',monospace;margin-bottom:4px;">'
    + tab_label_map[active_tab] + ' — ' + fmt_score(tab_score_map[active_tab]) + ' / composite of components below'
    '</div>',
    unsafe_allow_html=True
)

st.markdown(build_component_section(components, accent), unsafe_allow_html=True)

# ================================================
# AI MACRO ANALYSIS
# ================================================

st.markdown('<div class="sec-label">AI Macro Analysis</div>', unsafe_allow_html=True)

if "ai_analysis" not in st.session_state:
    with st.spinner("Analyzing macro regime..."):
        try:
            st.session_state.ai_analysis = get_ai_analysis(
                growth_score, inflation_score, liquidity_score, risk_appetite, regime
            )
        except Exception as e:
            st.session_state.ai_analysis = None
            st.error("AI analysis unavailable: " + str(e))

if st.session_state.ai_analysis:
    a  = st.session_state.ai_analysis
    gi = a.get("growth_interpretation", "")
    ii = a.get("inflation_interpretation", "")
    li = a.get("liquidity_interpretation", "")
    ri = a.get("risk_appetite_interpretation", "")
    sm = a.get("regime_summary", "")
    kw = a.get("key_watch", "")

    st.markdown('<div class="summary-box">' + sm + '</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="ai-grid">'
        '<div class="ai-card"><div class="ai-card-lbl" style="color:#00D4AA;">Growth Signal</div><div class="ai-card-txt">' + gi + '</div></div>'
        '<div class="ai-card"><div class="ai-card-lbl" style="color:#FF6B35;">Inflation Signal</div><div class="ai-card-txt">' + ii + '</div></div>'
        '<div class="ai-card"><div class="ai-card-lbl" style="color:#5B8DEF;">Liquidity Signal</div><div class="ai-card-txt">' + li + '</div></div>'
        '<div class="ai-card"><div class="ai-card-lbl" style="color:#FF6B35;">Risk Appetite Signal</div><div class="ai-card-txt">' + ri + '</div></div>'
        '</div>',
        unsafe_allow_html=True
    )
    st.markdown(
        '<div class="watch-box">'
        '<span style="color:#00D4AA;font-size:14px;">◎</span>'
        '<div class="watch-txt"><span style="color:#00D4AA;font-family:\'DM Mono\',monospace;font-size:10px;letter-spacing:0.1em;">KEY WATCH &nbsp;</span>' + kw + '</div>'
        '</div>',
        unsafe_allow_html=True
    )

# ================================================
# HISTORICAL TIMELINE
# ================================================

st.markdown('<div class="sec-label">Historical Regime Shift Timeline — Last 6 Months</div>', unsafe_allow_html=True)

rows_html = ""
for i, row in enumerate(historical_data):
    is_cur   = (i == len(historical_data) - 1)
    tr_class = "hist-current" if is_cur else ""
    cur_tag  = '<span class="cur-badge">CURRENT</span>' if is_cur else ""
    rows_html += (
        '<tr class="' + tr_class + '">'
        '<td><span class="month-txt">' + row["month"] + '</span>' + cur_tag + '</td>'
        '<td>' + regime_badge_html(row) + '</td>'
        '<td>' + score_pill(row["liquidity"])     + '</td>'
        '<td>' + score_pill(row["growth"])        + '</td>'
        '<td>' + score_pill(row["inflation"])     + '</td>'
        '<td>' + score_pill(row["risk_appetite"]) + '</td>'
        '</tr>'
    )

st.markdown(
    '<div class="hist-wrap"><table class="hist-table"><thead><tr>'
    '<th>Month</th><th>Regime</th><th>Liquidity</th><th>Growth</th><th>Inflation</th><th>Risk Appetite</th>'
    '</tr></thead><tbody>' + rows_html + '</tbody></table></div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div style="text-align:right;margin-top:16px;font-size:10px;color:#444;font-family:\'DM Mono\',monospace;">Macro Regime Calculator</div>',
    unsafe_allow_html=True
)
