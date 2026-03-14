import streamlit as st
import anthropic
import json

st.set_page_config(layout="wide", page_title="Regime.ai")

# ------------------------------------------------
# SAMPLE DATA
# ------------------------------------------------

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

# ------------------------------------------------
# REGIME LOGIC
# ------------------------------------------------

if risk_appetite > 0 and inflation_score > 0:
    regime = "Risk-On Inflation"
elif risk_appetite < 0 and inflation_score > 0:
    regime = "Risk-Off Inflation"
elif risk_appetite > 0 and inflation_score < 0:
    regime = "Risk-On Disinflation"
else:
    regime = "Risk-Off Disinflation"

# ------------------------------------------------
# REGIME CONFIG  (mirrors JS REGIME_CONFIG)
# ------------------------------------------------

REGIME_CONFIG = {
    "Risk-On Inflation": {
        "color":  "#FF6B35",
        "bg":     "rgba(255,107,53,0.12)",
        "border": "rgba(255,107,53,0.4)",
        "icon":   "↗",
        "desc":   "Growth accelerating + Prices rising",
        "favor":  ["Commodities", "Energy", "Financials", "TIPS", "EM equities"],
    },
    "Risk-On Disinflation": {
        "color":  "#00D4AA",
        "bg":     "rgba(0,212,170,0.12)",
        "border": "rgba(0,212,170,0.4)",
        "icon":   "↗",
        "desc":   "Growth accelerating + Prices cooling",
        "favor":  ["Growth equities", "Tech", "Small caps", "Corp bonds", "Crypto"],
    },
    "Risk-Off Inflation": {
        "color":  "#FF4757",
        "bg":     "rgba(255,71,87,0.12)",
        "border": "rgba(255,71,87,0.4)",
        "icon":   "↘",
        "desc":   "Growth slowing + Prices rising",
        "favor":  ["Gold", "Commodities", "Short-dur bonds", "Cash", "Defensives"],
    },
    "Risk-Off Disinflation": {
        "color":  "#5B8DEF",
        "bg":     "rgba(91,141,239,0.12)",
        "border": "rgba(91,141,239,0.4)",
        "icon":   "↘",
        "desc":   "Growth slowing + Prices cooling",
        "favor":  ["Long-duration Treasuries", "Gold", "Cash", "Utilities", "REITs"],
    },
}

cfg = REGIME_CONFIG.get(regime, REGIME_CONFIG["Risk-On Disinflation"])

# ------------------------------------------------
# HISTORICAL REGIME DATA (last 6 months)
# ------------------------------------------------

historical_data = [
    {"month": "October 2024",  "regime": "Risk-On Inflation",     "liquidity": 45,  "growth": 40,  "inflation": 30,  "risk_appetite": 46.5,  "color": "#FF6B35"},
    {"month": "November 2024", "regime": "Risk-On Inflation",     "liquidity": 55,  "growth": 42,  "inflation": 20,  "risk_appetite": 52.1,  "color": "#FF6B35"},
    {"month": "December 2024", "regime": "Risk-Off Inflation",    "liquidity": -20, "growth": 10,  "inflation": 25,  "risk_appetite": -4.0,  "color": "#FF4757"},
    {"month": "January 2025",  "regime": "Risk-Off Disinflation", "liquidity": -35, "growth": -15, "inflation": -18, "risk_appetite": -26.1, "color": "#5B8DEF"},
    {"month": "February 2025", "regime": "Risk-On Disinflation",  "liquidity": 30,  "growth": 20,  "inflation": -5,  "risk_appetite": 21.0,  "color": "#00D4AA"},
    {"month": "March 2025",    "regime": "Risk-On Disinflation",  "liquidity": 50,  "growth": 35,  "inflation": -10, "risk_appetite": risk_appetite_rounded, "color": "#00D4AA"},
]

# ------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------

def fmt_score(val):
    sign = "+" if val > 0 else ""
    if isinstance(val, float) and val == int(val):
        return sign + str(int(val))
    return sign + str(val)

def signal_text(score, label):
    if label == "Growth":
        return "Expanding" if score > 20 else ("Contracting" if score < -20 else "Neutral")
    if label == "Inflation":
        return "Inflationary" if score > 20 else ("Deflationary" if score < -20 else "Neutral")
    if label == "Liquidity":
        return "Abundant" if score > 20 else ("Tight" if score < -20 else "Neutral")
    if label == "Risk Appetite":
        return "Risk-On" if score > 20 else ("Risk-Off" if score < -20 else "Neutral")
    return ""

def gauge_bar(score, color):
    """Renders the JS-style centered gauge bar: zero in middle, fills left or right."""
    pct     = abs(score) / 2          # half of abs value (bar is 0-50% from center)
    left    = "50%" if score >= 0 else str(round(50 - pct, 1)) + "%"
    width   = str(round(pct, 1)) + "%"
    return (
        '<div class="gauge-track">'
        '<div class="gauge-mid"></div>'
        '<div class="gauge-fill" style="left:' + left + ';width:' + width + ';background:' + color + ';"></div>'
        '</div>'
    )

def score_pill(val):
    css = "pill-pos" if val > 0 else ("pill-neg" if val < 0 else "pill-neu")
    return '<span class="score-pill ' + css + '">' + fmt_score(val) + '</span>'

def regime_badge_html(row):
    c  = row["color"]
    bg = c + "22"
    return (
        '<span class="regime-badge" style="background:' + bg +
        ';border:1px solid ' + c + ';color:' + c + ';">' +
        row["regime"] + '</span>'
    )

# ------------------------------------------------
# AI ANALYSIS
# ------------------------------------------------

def get_ai_analysis(growth, inflation, liquidity, risk_app, regime_name):
    client = anthropic.Anthropic()
    prompt = (
        "You are a macro economist and financial analyst. Analyze the following macro regime scores.\n\n"
        "Scores:\n"
        "- Growth Score: "       + str(growth)            + " (-100 to 100)\n"
        "- Inflation Score: "    + str(inflation)          + " (-100 to 100)\n"
        "- Liquidity Score: "    + str(liquidity)          + " (-100 to 100)\n"
        "- Risk Appetite Score: "+ str(round(risk_app, 1)) + "\n"
        "- Current Regime: "     + regime_name             + "\n\n"
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

# ------------------------------------------------
# CSS  —  matches JS aesthetic exactly
# ------------------------------------------------

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
[data-testid="stSidebar"]          { background: #0A0A0F; }
section[data-testid="stMain"]      { background: #0A0A0F; }

/* ── HEADER ── */
.hdr-wrap    { display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:28px; }
.hdr-dot     { width:6px; height:6px; border-radius:50%; background:#00D4AA; box-shadow:0 0 8px #00D4AA; display:inline-block; margin-right:8px; vertical-align:middle; }
.hdr-eyebrow { font-size:10px; letter-spacing:0.2em; color:#555; text-transform:uppercase; font-family:'DM Mono',monospace; margin-bottom:4px; }
.hdr-title   { margin:0; font-size:28px; font-weight:600; letter-spacing:-0.02em; line-height:1.1; color:#E8E8E8; }
.hdr-sub     { margin:6px 0 0; font-size:12px; color:#555; }

/* ── REGIME BANNER ── */
.regime-banner {
    display:flex; align-items:center; gap:20px; flex-wrap:wrap;
    padding:20px 24px; border-radius:16px; margin-bottom:20px;
}
.regime-icon   { font-size:36px; line-height:1; }
.regime-label  { font-size:10px; letter-spacing:0.15em; text-transform:uppercase; font-family:'DM Mono',monospace; margin-bottom:2px; }
.regime-name   { font-size:22px; font-weight:600; letter-spacing:-0.01em; }
.regime-desc   { font-size:12px; color:#777; margin-top:2px; }
.regime-assets { border-left:1px solid rgba(255,255,255,0.08); padding-left:20px; }
.assets-label  { font-size:10px; letter-spacing:0.1em; color:#555; text-transform:uppercase; margin-bottom:6px; font-family:'DM Mono',monospace; }
.asset-tag     { display:inline-block; font-size:10px; padding:3px 8px; border-radius:4px; margin:2px; font-family:'DM Mono',monospace; }

/* ── CARDS ── */
.card {
    padding:20px; border-radius:12px;
    background:rgba(255,255,255,0.02);
    border:1px solid rgba(255,255,255,0.06);
}
.card-label {
    font-size:11px; letter-spacing:0.12em; text-transform:uppercase;
    color:#888; font-family:'DM Mono',monospace; margin-bottom:10px;
}

/* ── GAUGE ── */
.gauge-score {
    font-size:28px; font-weight:700; font-family:'DM Mono',monospace;
    line-height:1; margin-bottom:10px;
}
.gauge-track {
    height:6px; background:rgba(255,255,255,0.06);
    border-radius:3px; overflow:hidden; position:relative; margin-bottom:6px;
}
.gauge-mid {
    position:absolute; left:50%; top:0; width:1px; height:100%;
    background:rgba(255,255,255,0.2); z-index:2;
}
.gauge-fill {
    position:absolute; height:100%; border-radius:3px;
}
.gauge-foot {
    display:flex; justify-content:space-between;
}
.gauge-foot span {
    font-size:9px; color:#555; font-family:'DM Mono',monospace;
}

/* ── QUADRANT ── */
.quad-wrap {
    position:relative; width:100%; padding-bottom:100%;
    background:rgba(255,255,255,0.02); border-radius:12px;
    border:1px solid rgba(255,255,255,0.06); overflow:hidden;
}
.quad-inner   { position:absolute; inset:0; }
.quad-q       { position:absolute; }
.quad-axis-v  { position:absolute; left:50%; top:0; bottom:0; width:1px; background:rgba(255,255,255,0.08); }
.quad-axis-h  { position:absolute; top:50%; left:0; right:0; height:1px; background:rgba(255,255,255,0.08); }
.quad-lbl     { position:absolute; font-size:8px; letter-spacing:0.1em; font-family:'DM Mono',monospace; }
.quad-dot     { position:absolute; width:14px; height:14px; border-radius:50%; z-index:10; }
.quad-ring    { position:absolute; width:28px; height:28px; border-radius:50%; z-index:9; }

/* ── SUMMARY ── */
.summary-box {
    padding:14px 18px; border-radius:10px;
    background:rgba(255,255,255,0.02);
    border:1px solid rgba(255,255,255,0.06);
    font-size:12px; color:#888; line-height:1.7;
    margin-bottom:20px;
}

/* ── SECTION LABEL ── */
.sec-label {
    font-size:10px; letter-spacing:0.15em; color:#555;
    text-transform:uppercase; font-family:'DM Mono',monospace;
    margin-bottom:14px; margin-top:32px;
    padding-bottom:10px; border-bottom:1px solid rgba(255,255,255,0.06);
}

/* ── AI GRID ── */
.ai-grid { display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:14px; }
.ai-card {
    padding:16px; border-radius:10px;
    background:rgba(255,255,255,0.02);
    border:1px solid rgba(255,255,255,0.06);
}
.ai-card-lbl { font-size:9px; letter-spacing:0.15em; text-transform:uppercase; font-family:'DM Mono',monospace; margin-bottom:6px; }
.ai-card-txt { font-size:12px; color:#888; line-height:1.6; }

.watch-box {
    display:flex; gap:10px; align-items:flex-start;
    padding:12px 16px; border-radius:8px;
    background:rgba(255,255,255,0.02);
    border:1px solid rgba(255,255,255,0.06);
}
.watch-txt { font-size:12px; color:#aaa; line-height:1.5; }

/* ── SCORE CARDS ── */
.scores-row { display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin-bottom:8px; }
.sc-card {
    padding:18px 14px; border-radius:10px;
    background:rgba(255,255,255,0.02);
    border:1px solid rgba(255,255,255,0.06);
    position:relative; overflow:hidden;
}
.sc-card::before { content:''; position:absolute; top:0; left:0; right:0; height:2px; }
.sc-growth::before   { background:#00D4AA; }
.sc-inflation::before { background:#FF6B35; }
.sc-liquidity::before { background:#5B8DEF; }
.sc-risk::before     { background:#FF6B35; }
.sc-lbl  { font-size:9px; letter-spacing:0.15em; color:#555; text-transform:uppercase; font-family:'DM Mono',monospace; margin-bottom:8px; }
.sc-val  { font-size:26px; font-weight:700; font-family:'DM Mono',monospace; line-height:1; margin-bottom:10px; }
.sc-sig  { font-size:10px; color:#555; font-family:'DM Mono',monospace; }
.sc-growth   .sc-val { color:#00D4AA; }
.sc-inflation .sc-val { color:#FF6B35; }
.sc-liquidity .sc-val { color:#5B8DEF; }
.sc-risk     .sc-val { color:#FF6B35; }

/* ── HISTORY TABLE ── */
.hist-wrap { border-radius:12px; overflow:hidden; background:rgba(255,255,255,0.02); border:1px solid rgba(255,255,255,0.06); }
.hist-table { width:100%; border-collapse:collapse; }
.hist-table th {
    font-size:9px; letter-spacing:0.15em; color:#555; text-transform:uppercase;
    font-family:'DM Mono',monospace; padding:12px 16px; text-align:left;
    border-bottom:1px solid rgba(255,255,255,0.06);
}
.hist-table td {
    padding:13px 16px; font-size:11px; color:#aaa;
    border-bottom:1px solid rgba(255,255,255,0.04);
    font-family:'DM Mono',monospace;
}
.hist-table tr:last-child td { border-bottom:none; }
.hist-current td { background:rgba(255,255,255,0.015); }
.hist-current td:first-child { border-left:2px solid #00D4AA; }

.regime-badge {
    display:inline-flex; align-items:center; gap:5px;
    padding:3px 9px; border-radius:4px; font-size:10px;
    font-weight:600; font-family:'DM Mono',monospace;
}
.score-pill  { display:inline-block; padding:2px 7px; border-radius:4px; font-size:11px; font-weight:600; font-family:'DM Mono',monospace; }
.pill-pos    { background:rgba(0,212,170,0.12); color:#00D4AA; }
.pill-neg    { background:rgba(255,71,87,0.12);  color:#FF4757; }
.pill-neu    { background:rgba(255,255,255,0.05); color:#666; }
.cur-badge   { display:inline-block; font-size:8px; letter-spacing:0.1em; padding:2px 5px; border-radius:3px; background:rgba(0,212,170,0.1); border:1px solid rgba(0,212,170,0.25); color:#00D4AA; margin-left:6px; font-family:'DM Mono',monospace; }
.month-txt   { color:#666; }
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
# TOP SECTION: Quadrant (left) + Regime info (right)
# ================================================

col_q, col_r = st.columns([1, 2])

# Pre-compute quadrant dot positions
qx        = round(50 + (growth_score   / 100) * 45, 2)
qy        = round(50 - (inflation_score / 100) * 45, 2)
dot_left  = str(round(qx - 7,  2)) + "%"
dot_top   = str(round(qy - 7,  2)) + "%"
ring_left = str(round(qx - 14, 2)) + "%"
ring_top  = str(round(qy - 14, 2)) + "%"

with col_q:
    st.markdown(
        '<div class="quad-wrap">'
        '<div class="quad-inner">'
        '<div class="quad-q" style="left:50%;top:0;right:0;bottom:50%;background:rgba(255,107,53,0.04);"></div>'
        '<div class="quad-q" style="left:0;top:0;right:50%;bottom:50%;background:rgba(255,71,87,0.04);"></div>'
        '<div class="quad-q" style="left:50%;top:50%;right:0;bottom:0;background:rgba(0,212,170,0.04);"></div>'
        '<div class="quad-q" style="left:0;top:50%;right:50%;bottom:0;background:rgba(91,141,239,0.04);"></div>'
        '<div class="quad-axis-v"></div>'
        '<div class="quad-axis-h"></div>'
        '<div class="quad-lbl" style="top:6px;left:50%;transform:translateX(-50%);color:#FF4757;">INFLATION</div>'
        '<div class="quad-lbl" style="bottom:6px;left:50%;transform:translateX(-50%);color:#5B8DEF;">DISINFLATION</div>'
        '<div class="quad-lbl" style="right:4px;top:50%;transform:translateY(-50%) rotate(90deg);color:#00D4AA;transform-origin:center;">RISK-ON</div>'
        '<div class="quad-lbl" style="left:4px;top:50%;transform:translateY(-50%) rotate(-90deg);color:#FF6B35;transform-origin:center;">RISK-OFF</div>'
        '<div class="quad-dot" style="left:' + dot_left + ';top:' + dot_top + ';background:' + cfg["color"] + ';box-shadow:0 0 16px ' + cfg["color"] + '80;"></div>'
        '<div class="quad-ring" style="left:' + ring_left + ';top:' + ring_top + ';border:1px solid ' + cfg["color"] + '40;"></div>'
        '</div>'
        '</div>',
        unsafe_allow_html=True
    )

# Build favored asset tags
favor_tags = ""
for asset in cfg["favor"]:
    favor_tags += (
        '<span class="asset-tag" style="background:' + cfg["color"] + '22;'
        'border:1px solid ' + cfg["color"] + '44;color:' + cfg["color"] + ';">'
        + asset + '</span>'
    )

with col_r:
    st.markdown(
        '<div style="padding:24px;border-radius:16px;background:' + cfg["bg"] + ';border:1px solid ' + cfg["border"] + ';height:100%;box-sizing:border-box;">'

        # Eyebrow
        '<div style="font-size:10px;letter-spacing:0.15em;text-transform:uppercase;font-family:\'DM Mono\',monospace;color:' + cfg["color"] + '99;margin-bottom:6px;">Current Regime</div>'

        # Big regime name
        '<div style="font-size:32px;font-weight:600;letter-spacing:-0.02em;color:' + cfg["color"] + ';line-height:1.1;margin-bottom:6px;">'
        + cfg["icon"] + ' ' + regime +
        '</div>'

        # Description
        '<div style="font-size:13px;color:#777;margin-bottom:24px;">' + cfg["desc"] + '</div>'

        # Divider
        '<div style="height:1px;background:rgba(255,255,255,0.06);margin-bottom:20px;"></div>'

        # Favored assets
        '<div style="font-size:10px;letter-spacing:0.12em;text-transform:uppercase;font-family:\'DM Mono\',monospace;color:#555;margin-bottom:10px;">Favored Assets</div>'
        '<div>' + favor_tags + '</div>'

        '</div>',
        unsafe_allow_html=True
    )

# ================================================
# INDIVIDUAL SCORE BREAKDOWN
# ================================================

st.markdown('<div class="sec-label">Individual Score Breakdown</div>', unsafe_allow_html=True)

liq_color  = "#00D4AA" if liquidity_score >= 0 else "#FF4757"
risk_color = "#00D4AA" if risk_appetite   >= 0 else "#FF4757"

st.markdown(
    '<div class="scores-row">'

    '<div class="sc-card sc-growth">'
    '<div class="sc-lbl">Growth</div>'
    '<div class="sc-val">' + fmt_score(growth_score) + '</div>'
    + gauge_bar(growth_score, "#00D4AA" if growth_score >= 0 else "#FF4757") +
    '<div class="sc-sig">' + signal_text(growth_score, "Growth") + '</div>'
    '</div>'

    '<div class="sc-card sc-inflation">'
    '<div class="sc-lbl">Inflation</div>'
    '<div class="sc-val">' + fmt_score(inflation_score) + '</div>'
    + gauge_bar(inflation_score, "#FF6B35" if inflation_score >= 0 else "#5B8DEF") +
    '<div class="sc-sig">' + signal_text(inflation_score, "Inflation") + '</div>'
    '</div>'

    '<div class="sc-card sc-liquidity">'
    '<div class="sc-lbl">Liquidity</div>'
    '<div class="sc-val">' + fmt_score(liquidity_score) + '</div>'
    + gauge_bar(liquidity_score, liq_color) +
    '<div class="sc-sig">' + signal_text(liquidity_score, "Liquidity") + '</div>'
    '</div>'

    '<div class="sc-card sc-risk">'
    '<div class="sc-lbl">Risk Appetite</div>'
    '<div class="sc-val">' + fmt_score(risk_appetite_rounded) + '</div>'
    + gauge_bar(risk_appetite, risk_color) +
    '<div class="sc-sig">' + signal_text(risk_appetite, "Risk Appetite") + '</div>'
    '</div>'

    '</div>',
    unsafe_allow_html=True
)

# ================================================
# AI MACRO ANALYSIS  (auto-runs, cached)
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

    # Summary box
    st.markdown(
        '<div class="summary-box">' + sm + '</div>',
        unsafe_allow_html=True
    )

    # 2x2 signal cards
    st.markdown(
        '<div class="ai-grid">'
        '<div class="ai-card"><div class="ai-card-lbl" style="color:#00D4AA;">Growth Signal</div><div class="ai-card-txt">' + gi + '</div></div>'
        '<div class="ai-card"><div class="ai-card-lbl" style="color:#FF6B35;">Inflation Signal</div><div class="ai-card-txt">' + ii + '</div></div>'
        '<div class="ai-card"><div class="ai-card-lbl" style="color:#5B8DEF;">Liquidity Signal</div><div class="ai-card-txt">' + li + '</div></div>'
        '<div class="ai-card"><div class="ai-card-lbl" style="color:#FF6B35;">Risk Appetite Signal</div><div class="ai-card-txt">' + ri + '</div></div>'
        '</div>',
        unsafe_allow_html=True
    )

    # Key watch
    st.markdown(
        '<div class="watch-box">'
        '<span style="color:#00D4AA;font-size:14px;">◎</span>'
        '<div class="watch-txt"><span style="color:#00D4AA;font-family:\'DM Mono\',monospace;font-size:10px;letter-spacing:0.1em;">KEY WATCH &nbsp;</span>' + kw + '</div>'
        '</div>',
        unsafe_allow_html=True
    )

# ================================================
# HISTORICAL REGIME TIMELINE
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
    '<div class="hist-wrap">'
    '<table class="hist-table">'
    '<thead><tr>'
    '<th>Month</th><th>Regime</th><th>Liquidity</th><th>Growth</th><th>Inflation</th><th>Risk Appetite</th>'
    '</tr></thead>'
    '<tbody>' + rows_html + '</tbody>'
    '</table></div>',
    unsafe_allow_html=True
)

st.markdown(
    '<div style="text-align:right;margin-top:16px;font-size:10px;color:#444;font-family:\'DM Mono\',monospace;">'
    'Macro Regime Calculator</div>',
    unsafe_allow_html=True
)
