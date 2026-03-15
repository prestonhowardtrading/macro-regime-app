import streamlit as st
import anthropic
import json
from datetime import date

st.set_page_config(layout="wide", page_title="Regime.ai")

# ================================================
# LIVE DATA FETCH  — cached for 24 hours
# Every user hitting the app shares this one result.
# Claude uses web_search to pull all indicators live,
# scores them per the framework, and returns JSON.
# ================================================

SCORING_SYSTEM_PROMPT = """You are a macroeconomic analyst. Research current economic data and calculate Growth, Inflation, and Liquidity scores using the exact scoring frameworks below.

Use web search to find the LATEST available values for every indicator listed. Always search for real current data.

────────────────────────────────────────
GROWTH SCORE FRAMEWORK (range: -100 to +100)
────────────────────────────────────────
MONETARY POLICY (25% weight, max raw ±55):
- Rate cut prob >70% next 3M = +20 | 40-70% = +10 | neutral = 0 | hike 40-70% = -10 | hike >70% = -20
- Real rates (10Y TIPS) falling >0.5% over 3M = +10 | stable = 0 | rising >0.5% = -10
- Fed balance sheet expanding >2% YoY = +10 | stable = 0 | shrinking (QT) = -10
- Yield curve (10Y-2Y): steepening >50bps = +5 | flat = 0 | inverted >25bps = -10

GLOBAL LIQUIDITY (20% weight, max raw ±20):
- Global CB balance sheets YoY: >5% = +20 | 2-5% = +10 | stable = 0 | -2 to -5% = -10 | <-5% = -20

FISCAL POLICY (15% weight, max raw ±40):
- Gov spending growth YoY: >5% = +15 | 2-5% = +5 | flat = 0 | contracting = -10
- Federal deficit change: increasing >1% GDP = +10 | stable = 0 | shrinking >1% GDP = -10
- Stimulus legislation: major >2% GDP = +20 | moderate = +10 | tightening = -10

LABOR MARKET (15% weight, max raw ±25):
- Unemployment 6M change: falling >0.3% = +15 | stable = +5 | rising 0.3-0.7% = -10 | rising >0.7% = -20
- Initial jobless claims trend: falling = +5 | stable = 0 | rising = -10

LEADING INDICATORS (15% weight, clamp ±30):
- ISM Mfg PMI: >55=+10 | 52-55=+5 | 48-52=0 | 45-48=-5 | <45=-10; trend ±5
- ISM Services PMI: >55=+8 | 52-55=+4 | 48-52=0 | 45-48=-4 | <45=-8
- Conference Board LEI 6M: >1%=+8 | rising slightly=+3 | flat=0 | falling slightly=-5 | <-1%=-10
- Retail sales YoY: >4%=+6 | 2-4%=+3 | 0-2%=0 | contracting=-5 | <-2%=-8; momentum ±3
- GDPNow forecast: >3%=+6 | 2-3%=+3 | 1-2%=0 | 0-1%=-3 | <0%=-6

DOLLAR STRENGTH (10% weight, max raw ±15):
- DXY 3M change: falling >5%=+15 | falling 2-5%=+5 | stable=0 | rising 2-5%=-5 | rising >5%=-15

Growth Score = (MonPol×0.25 + GlobalLiq×0.20 + Fiscal×0.15 + Labor×0.15 + Leading_clamped×0.15 + DXY×0.10), scaled ±100, clamped.

────────────────────────────────────────
INFLATION SCORE FRAMEWORK (range: -100 to +100)
────────────────────────────────────────
INFLATION DATA (25% weight):
- CPI MoM: accelerating >0.3% = +20 | 0.1-0.3% = +10 | stable = 0 | declining = -10 | sharply declining = -20
- Core PCE: >3%=+10 | 2-3%=+5 | near 2%=0 | <2%=-10
- PPI trend: rising rapidly=+10 | falling=-10

COMMODITY PRICES (20% weight):
- BCOM 6M change: >10%=+15 | 5-10%=+5 | flat=0 | -5 to -10%=-5 | <-10%=-10

MONETARY POLICY - INFLATION LENS (20% weight):
- Rate cut expectations: aggressive cuts=+15 | moderate easing=+5 | neutral=0 | moderate tightening=-10 | aggressive tightening=-20
- Real rates: rising >0.5%=-10 | falling >0.5%=+10
- Fed balance sheet: expanding=+10 | shrinking=-10

LABOR MARKET WAGES (20% weight):
- Wage growth YoY: >5%=+15 | 3-5%=+5 | 2-3%=0 | <2%=-10

INFLATION EXPECTATIONS (15% weight):
- 5Y breakeven 3M change: rising >0.5%=+15 | rising slightly=+5 | stable=0 | falling=-10

────────────────────────────────────────
LIQUIDITY SCORE FRAMEWORK (range: -100 to +100)
────────────────────────────────────────
CENTRAL BANK BALANCE SHEETS (40% weight):
Fed (50%), ECB (20%), BOJ (20%), PBOC (10%)
Each CB: >10% YoY=+40 | 5-10%=+25 | 1-5%=+10 | flat=0 | -1 to -5%=-10 | -5 to -10%=-25 | <-10%=-40

TREASURY LIQUIDITY TGA/RRP (20% weight):
- TGA falling >$200B=+20 | $100-200B=+10 | flat=0 | rising $100-200B=-10 | rising >$200B=-20
- RRP falling rapidly=+15 | moderate decline=+5 | flat=0 | moderate increase=-5 | sharp increase=-15
- Net Liquidity ROC 3M: >5%=+20 | 2-5%=+10 | -2 to 2%=0 | -2 to -5%=-10 | <-5%=-20

MARKET LIQUIDITY CONDITIONS (15% weight):
- Real rates: falling >0.75%=+15 | falling 0.25-0.75%=+10 | flat=0 | rising 0.25-0.75%=-10 | rising >0.75%=-15
- M2 YoY: >8%=+10 | 4-8%=+5 | 0-4%=0 | -4 to 0%=-5 | <-4%=-10
- Chicago NFCI ΔFCI 3M: <=-0.40=+15 | -0.20 to -0.40=+10 | -0.05 to -0.20=+5 | ±0.05=0 | 0.05-0.20=-5 | 0.20-0.40=-10 | >=0.40=-15

DOLLAR LIQUIDITY (15% weight):
- DXY 3M ROC: falling >5%=+15 | 2-5%=+10 | 0-2%=+5 | flat=0 | rising 0-2%=-5 | 2-5%=-10 | >5%=-15
- DXY vs 200DMA: >5% below=+10 | 2-5% below=+5 | ±2%=0 | 2-5% above=-5 | >5% above=-10

CREDIT LIQUIDITY (10% weight):
- HY spreads: tightening >100bps=+10 | 50-100=+5 | flat=0 | widening 50-100=-5 | >100=-10
- IG spreads: tightening >40bps=+10 | 20-40=+6 | 5-20=+3 | flat=0 | widening 5-20=-3 | 20-40=-6 | >40=-10
- Bank lending standards: large easing >10%=+10 | moderate 5-10%=+6 | small 1-5%=+3 | stable=0 | small tightening=-3 | moderate=-6 | large >10%=-10

────────────────────────────────────────
RESPONSE FORMAT
────────────────────────────────────────
Return ONLY valid JSON, no markdown, no extra text:
{
  "as_of_date": "YYYY-MM-DD",
  "growth_score": <-100 to 100>,
  "inflation_score": <-100 to 100>,
  "liquidity_score": <-100 to 100>,
  "growth_components": {
    "Monetary Policy":     {"weight": "25%", "score": <int>, "max": 55, "indicators": [{"label": "...", "value": "...", "points": <int>, "note": "..."}]},
    "Global Liquidity":    {"weight": "20%", "score": <int>, "max": 20, "indicators": [...]},
    "Fiscal Policy":       {"weight": "15%", "score": <int>, "max": 40, "indicators": [...]},
    "Labor Market":        {"weight": "15%", "score": <int>, "max": 25, "indicators": [...]},
    "Leading Indicators":  {"weight": "15%", "score": <int>, "max": 30, "indicators": [...]},
    "Dollar Strength":     {"weight": "10%", "score": <int>, "max": 15, "indicators": [...]}
  },
  "inflation_components": {
    "Inflation Data":          {"weight": "25%", "score": <int>, "max": 40, "indicators": [...]},
    "Commodity Prices":        {"weight": "20%", "score": <int>, "max": 15, "indicators": [...]},
    "Monetary Policy":         {"weight": "20%", "score": <int>, "max": 40, "indicators": [...]},
    "Labor Market (Wages)":    {"weight": "20%", "score": <int>, "max": 15, "indicators": [...]},
    "Inflation Expectations":  {"weight": "15%", "score": <int>, "max": 15, "indicators": [...]}
  },
  "liquidity_components": {
    "Central Bank Balance Sheets":    {"weight": "40%", "score": <int>, "max": 40, "indicators": [...]},
    "Treasury Liquidity (TGA/RRP)":   {"weight": "20%", "score": <int>, "max": 20, "indicators": [...]},
    "Market Liquidity Conditions":    {"weight": "15%", "score": <int>, "max": 15, "indicators": [...]},
    "Dollar Liquidity (DXY)":         {"weight": "15%", "score": <int>, "max": 15, "indicators": [...]},
    "Credit Liquidity":               {"weight": "10%", "score": <int>, "max": 10, "indicators": [...]}
  },
  "ai_analysis": {
    "growth_interpretation": "2-sentence interpretation",
    "inflation_interpretation": "2-sentence interpretation",
    "liquidity_interpretation": "2-sentence interpretation",
    "risk_appetite_interpretation": "2-sentence interpretation",
    "regime_summary": "3-4 sentence macro summary for investors",
    "key_watch": "One specific indicator to watch"
  }
}"""

SCORING_USER_PROMPT = """Today is {today}. Search for the latest values for ALL indicators below and calculate all three scores.

Search for:
1. CME FedWatch — rate cut probability next 3 months
2. 10Y TIPS real yield — current level and 3-month change
3. Federal Reserve balance sheet — size and YoY % change
4. 10Y-2Y Treasury yield spread
5. Global central bank balance sheets aggregate YoY change (Fed + ECB + BOJ + PBOC)
6. ECB balance sheet YoY change
7. Bank of Japan balance sheet YoY change
8. PBOC balance sheet YoY change
9. US government spending YoY growth
10. US federal deficit as % of GDP and recent trend
11. Recent major fiscal legislation
12. US unemployment rate — current and 6-month change
13. Initial jobless claims — recent trend
14. ISM Manufacturing PMI — latest reading and 3-month trend
15. ISM Services PMI — latest reading
16. Conference Board LEI — latest 6-month change
17. US Retail Sales — latest YoY and 3-month momentum
18. Atlanta Fed GDPNow — latest forecast
19. DXY US Dollar Index — current level and 3-month % change
20. CPI MoM — latest reading
21. Core PCE — latest YoY reading
22. PPI — latest trend
23. Bloomberg Commodity Index (BCOM) — 6-month change
24. Average hourly earnings YoY
25. 5-Year breakeven inflation rate — current and 3-month change
26. US Treasury General Account (TGA) — current balance and recent change
27. Federal Reserve Reverse Repo (RRP) — current balance and trend
28. M2 money supply YoY growth
29. Chicago Fed NFCI — current level and 3-month change
30. DXY vs 200-day moving average
31. High yield credit spreads — current and 3-month change
32. Investment grade credit spreads — current and 3-month change
33. Fed Senior Loan Officer Survey — latest bank lending standards

Return only the JSON."""


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_live_regime(today_str: str) -> dict:
    """
    Called once per calendar day. today_str forces cache to reset at midnight.
    Uses Claude with web_search to pull all 33 indicators and score them.
    """
    api_key = st.secrets.get("ANTHROPIC_API_KEY", None)
    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4000,
        system=SCORING_SYSTEM_PROMPT,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{
            "role": "user",
            "content": SCORING_USER_PROMPT.format(today=today_str)
        }]
    )

    # Extract text blocks (may have tool_use blocks interspersed)
    json_text = ""
    for block in response.content:
        if block.type == "text":
            json_text += block.text

    # Parse JSON — strip any accidental markdown fences
    json_text = json_text.strip()
    if json_text.startswith("```"):
        json_text = json_text.split("```")[1]
        if json_text.startswith("json"):
            json_text = json_text[4:]
    json_text = json_text.strip()

    # Find the first { ... } block
    start = json_text.find("{")
    end   = json_text.rfind("}") + 1
    return json.loads(json_text[start:end])


# ── Load data (from cache or fresh fetch) ──────────────────────────────────
today_str = str(date.today())   # e.g. "2025-03-14" — changes daily, busting cache

with st.spinner("Loading macro regime data..."):
    try:
        live = fetch_live_regime(today_str)
        data_source = "live"
    except Exception as e:
        st.warning("Live data unavailable — showing last known values. Error: " + str(e))
        live = None
        data_source = "fallback"

# ── Unpack scores ───────────────────────────────────────────────────────────
if live:
    growth_score    = int(round(live.get("growth_score",    35)))
    inflation_score = int(round(live.get("inflation_score", -10)))
    liquidity_score = int(round(live.get("liquidity_score",  50)))
    GROWTH_COMPONENTS    = live.get("growth_components",    {})
    INFLATION_COMPONENTS = live.get("inflation_components", {})
    LIQUIDITY_COMPONENTS = live.get("liquidity_components", {})
    AI_ANALYSIS          = live.get("ai_analysis",          {})
    as_of_date           = live.get("as_of_date", today_str)
else:
    # Fallback hardcoded values if API fails
    growth_score    = 35
    inflation_score = -10
    liquidity_score = 50
    GROWTH_COMPONENTS    = {}
    INFLATION_COMPONENTS = {}
    LIQUIDITY_COMPONENTS = {}
    AI_ANALYSIS          = {}
    as_of_date           = today_str

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
# HISTORICAL DATA (static — will be replaced with live data later)
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

/* aspect-ratio: ~45% keeps the chart compact so it aligns with sidebar */
.quad-wrap {
    position:relative;width:100%;padding-bottom:45%;
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

# Render tab selector as mini-score cards (same style as regime classification)
tab_col1, tab_col2, tab_col3, _ = st.columns([1, 1, 1, 4])

with tab_col1:
    is_active = st.session_state.score_tab == "growth"
    border_style = "border:1px solid rgba(0,212,170,0.5);" if is_active else "border:1px solid rgba(255,255,255,0.06);"
    bg_style = "background:rgba(0,212,170,0.08);" if is_active else "background:rgba(255,255,255,0.02);"
    st.markdown(
        '<div style="' + bg_style + border_style + 'border-radius:8px;padding:12px 14px;cursor:pointer;">'
        '<div style="font-size:9px;letter-spacing:0.15em;color:#555;font-family:\'DM Mono\',monospace;margin-bottom:4px;">GROWTH</div>'
        '<div style="font-size:22px;font-weight:700;font-family:\'DM Mono\',monospace;line-height:1;color:#00D4AA;">' + fmt_score(growth_score) + '</div>'
        '</div>',
        unsafe_allow_html=True
    )
    if st.button("Select", key="tab_growth", use_container_width=True):
        st.session_state.score_tab = "growth"
        st.rerun()

with tab_col2:
    is_active = st.session_state.score_tab == "inflation"
    border_style = "border:1px solid rgba(255,107,53,0.5);" if is_active else "border:1px solid rgba(255,255,255,0.06);"
    bg_style = "background:rgba(255,107,53,0.08);" if is_active else "background:rgba(255,255,255,0.02);"
    st.markdown(
        '<div style="' + bg_style + border_style + 'border-radius:8px;padding:12px 14px;cursor:pointer;">'
        '<div style="font-size:9px;letter-spacing:0.15em;color:#555;font-family:\'DM Mono\',monospace;margin-bottom:4px;">INFLATION</div>'
        '<div style="font-size:22px;font-weight:700;font-family:\'DM Mono\',monospace;line-height:1;color:#FF6B35;">' + fmt_score(inflation_score) + '</div>'
        '</div>',
        unsafe_allow_html=True
    )
    if st.button("Select", key="tab_inflation", use_container_width=True):
        st.session_state.score_tab = "inflation"
        st.rerun()

with tab_col3:
    is_active = st.session_state.score_tab == "liquidity"
    border_style = "border:1px solid rgba(91,141,239,0.5);" if is_active else "border:1px solid rgba(255,255,255,0.06);"
    bg_style = "background:rgba(91,141,239,0.08);" if is_active else "background:rgba(255,255,255,0.02);"
    st.markdown(
        '<div style="' + bg_style + border_style + 'border-radius:8px;padding:12px 14px;cursor:pointer;">'
        '<div style="font-size:9px;letter-spacing:0.15em;color:#555;font-family:\'DM Mono\',monospace;margin-bottom:4px;">LIQUIDITY</div>'
        '<div style="font-size:22px;font-weight:700;font-family:\'DM Mono\',monospace;line-height:1;color:#5B8DEF;">' + fmt_score(liquidity_score) + '</div>'
        '</div>',
        unsafe_allow_html=True
    )
    if st.button("Select", key="tab_liquidity", use_container_width=True):
        st.session_state.score_tab = "liquidity"
        st.rerun()

# Hide the "Select" button text visually — we only need the click area
st.markdown("""
<style>
[data-testid="stColumns"] .stButton button {
    background: transparent !important;
    border: none !important;
    color: transparent !important;
    height: 4px !important;
    min-height: 0 !important;
    padding: 0 !important;
    margin-top: -6px !important;
    cursor: pointer !important;
    box-shadow: none !important;
}
[data-testid="stColumns"] .stButton button:hover {
    background: transparent !important;
}
</style>
""", unsafe_allow_html=True)

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
# AI MACRO ANALYSIS  (from live fetch, already cached)
# ================================================

st.markdown('<div class="sec-label">AI Macro Analysis</div>', unsafe_allow_html=True)

if AI_ANALYSIS:
    gi = AI_ANALYSIS.get("growth_interpretation", "")
    ii = AI_ANALYSIS.get("inflation_interpretation", "")
    li = AI_ANALYSIS.get("liquidity_interpretation", "")
    ri = AI_ANALYSIS.get("risk_appetite_interpretation", "")
    sm = AI_ANALYSIS.get("regime_summary", "")
    kw = AI_ANALYSIS.get("key_watch", "")

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
else:
    st.markdown(
        '<div class="summary-box" style="color:#555;">AI analysis unavailable — live data fetch may have failed.</div>',
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

# ── Footer: cache status + timestamp ───────────────────────────────────────
cache_note = "Live data" if data_source == "live" else "Fallback data (live fetch failed)"
footer_html = (
    '<div style="display:flex;justify-content:space-between;margin-top:16px;">'
    '<div style="font-size:10px;color:#444;font-family:\'DM Mono\',monospace;">'
    '<span style="color:#00D4AA;">●</span> ' + cache_note + ' · cached 24h · next refresh ' + today_str +
    '</div>'
    '<div style="font-size:10px;color:#444;font-family:\'DM Mono\',monospace;">As of ' + as_of_date + '</div>'
    '</div>'
)
st.markdown(footer_html, unsafe_allow_html=True)
