import streamlit as st
import anthropic
import json

st.set_page_config(layout="wide")

# ------------------------------------------------
# SAMPLE DATA
# ------------------------------------------------

growth_score = 35
inflation_score = -10
liquidity_score = 50

risk_appetite = (
    0.5 * liquidity_score +
    0.3 * growth_score +
    0.2 * inflation_score
)
risk_appetite = max(min(risk_appetite, 100), -100)
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
# DOT POSITION
# ------------------------------------------------

x_percent = round((risk_appetite + 100) / 200 * 100, 2)
y_percent = round((100 - inflation_score) / 200 * 100, 2)

# ------------------------------------------------
# HISTORICAL REGIME DATA (last 6 months)
# ------------------------------------------------

historical_data = [
    {"month": "October 2024",  "regime": "Risk-On Inflation",     "liquidity": 45,  "growth": 40,  "inflation": 30,  "risk_appetite": 46.5,  "regime_color": "#ef4444", "regime_icon": "🔥"},
    {"month": "November 2024", "regime": "Risk-On Inflation",     "liquidity": 55,  "growth": 42,  "inflation": 20,  "risk_appetite": 52.1,  "regime_color": "#ef4444", "regime_icon": "🔥"},
    {"month": "December 2024", "regime": "Risk-Off Inflation",    "liquidity": -20, "growth": 10,  "inflation": 25,  "risk_appetite": -4.0,  "regime_color": "#f97316", "regime_icon": "⚠️"},
    {"month": "January 2025",  "regime": "Risk-Off Disinflation", "liquidity": -35, "growth": -15, "inflation": -18, "risk_appetite": -26.1, "regime_color": "#3b82f6", "regime_icon": "🧊"},
    {"month": "February 2025", "regime": "Risk-On Disinflation",  "liquidity": 30,  "growth": 20,  "inflation": -5,  "risk_appetite": 21.0,  "regime_color": "#22c55e", "regime_icon": "📈"},
    {"month": "March 2025",    "regime": "Risk-On Disinflation",  "liquidity": 50,  "growth": 35,  "inflation": -10, "risk_appetite": risk_appetite_rounded, "regime_color": "#22c55e", "regime_icon": "📈"},
]

# ------------------------------------------------
# HELPER FUNCTIONS
# ------------------------------------------------

def bar_width(score):
    return round(max(0, min(100, (score + 100) / 2)), 1)

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

def fmt_score(val):
    sign = "+" if val > 0 else ""
    if val == int(val):
        return sign + str(int(val))
    return sign + str(val)

def score_pill(val):
    css = "positive" if val > 0 else ("negative" if val < 0 else "neutral")
    return '<span class="score-pill ' + css + '">' + fmt_score(val) + '</span>'

def regime_badge(row):
    c = row["regime_color"]
    bg = c + "22"
    return (
        '<span class="regime-badge" style="background:' + bg +
        ';border:1px solid ' + c + ';color:' + c + ';">' +
        row["regime_icon"] + ' ' + row["regime"] + '</span>'
    )

# ------------------------------------------------
# AI ANALYSIS FUNCTION
# ------------------------------------------------

def get_ai_analysis(growth, inflation, liquidity, risk_app, regime_name):
    client = anthropic.Anthropic()
    prompt = (
        "You are a macro economist and financial analyst. Analyze the following macro regime scores and provide a concise, insightful interpretation.\n\n"
        "Current Macro Scores:\n"
        "- Growth Score: " + str(growth) + " (range: -100 to 100, positive = expanding, negative = contracting)\n"
        "- Inflation Score: " + str(inflation) + " (range: -100 to 100, positive = inflationary, negative = deflationary)\n"
        "- Liquidity Score: " + str(liquidity) + " (range: -100 to 100, positive = abundant liquidity, negative = tight liquidity)\n"
        "- Risk Appetite Score: " + str(round(risk_app, 1)) + " (composite score)\n"
        "- Current Regime: " + regime_name + "\n\n"
        "Provide your analysis in the following JSON format ONLY (no markdown, no extra text):\n"
        "{\n"
        '  "growth_interpretation": "2-sentence interpretation of the growth score and what it signals",\n'
        '  "inflation_interpretation": "2-sentence interpretation of the inflation score and what it signals",\n'
        '  "liquidity_interpretation": "2-sentence interpretation of the liquidity score and what it signals",\n'
        '  "risk_appetite_interpretation": "2-sentence interpretation of the risk appetite score",\n'
        '  "regime_summary": "3-4 sentence overall regime summary covering what this macro environment means for investors and key risks/opportunities",\n'
        '  "key_watch": "One specific macro indicator or event to watch closely in this regime"\n'
        "}"
    )
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}]
    )
    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    return json.loads(raw.strip())

# ------------------------------------------------
# GLOBAL CSS
# ------------------------------------------------

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Syne:wght@700;800&display=swap');
* { font-family: 'IBM Plex Mono', monospace; }
body { background: #0b1220; color: white; }

.header { display:flex; align-items:center; gap:15px; margin-bottom:30px; }
.pulse { width:18px; height:18px; border-radius:50%; background:#00e0ff; position:relative; }
.pulse::after { content:''; position:absolute; width:18px; height:18px; border-radius:50%; background:#00e0ff; animation:pulse 2s infinite; }
@keyframes pulse { 0%{transform:scale(1);opacity:1;} 70%{transform:scale(2.2);opacity:0;} 100%{opacity:0;} }
.header-title { font-family:'Syne',sans-serif; font-size:22px; font-weight:800; letter-spacing:2px; }

.panel { background:#111827; border-radius:14px; padding:25px; border:1px solid #1f2937; }
.panel-title { color:#9ca3af; font-size:11px; letter-spacing:3px; margin-bottom:20px; }

.quadrant-wrapper { position:relative; width:100%; padding-bottom:100%; }
.quadrant-inner { position:absolute; top:0; left:0; right:0; bottom:0; }
.grid { display:grid; grid-template-columns:1fr 1fr; grid-template-rows:1fr 1fr; width:100%; height:100%; }
.box { border:1px solid #1f2937; background:#0f172a; }
.axis-x { position:absolute; top:50%; width:100%; height:1px; background:#374151; }
.dot { position:absolute; width:16px; height:16px; background:white; border-radius:50%; box-shadow:0 0 15px rgba(255,255,255,.7); }
.q-label { position:absolute; font-size:11px; color:#9ca3af; letter-spacing:1px; }
.q1 { top:10%; left:55%; }
.q2 { top:10%; left:5%; }
.q3 { top:75%; left:5%; }
.q4 { top:75%; left:55%; }

.regime-box { background:#2a1b0d; border:1px solid #f59e0b; padding:15px; border-radius:10px; color:#f59e0b; font-weight:600; margin-bottom:15px; }
.metric-grid { display:grid; grid-template-columns:1fr 1fr; gap:10px; }
.metric { background:#1f2937; padding:15px; border-radius:10px; text-align:center; }
.asset-box { background:#2a1b0d; border:1px solid #f59e0b; padding:20px; border-radius:10px; }
.tag { display:inline-block; background:#111827; border:1px solid #374151; padding:6px 12px; border-radius:20px; margin:5px; font-size:13px; }

.section-header { color:#9ca3af; font-size:11px; letter-spacing:3px; margin-bottom:20px; padding-bottom:10px; border-bottom:1px solid #1f2937; margin-top:40px; }

.scores-grid { display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:30px; }
.score-card { background:#111827; border:1px solid #1f2937; border-radius:12px; padding:20px 16px; position:relative; overflow:hidden; }
.score-card::before { content:''; position:absolute; top:0; left:0; right:0; height:3px; }
.score-card.growth::before  { background:#22c55e; }
.score-card.inflation::before { background:#ef4444; }
.score-card.liquidity::before { background:#3b82f6; }
.score-card.risk::before    { background:#f59e0b; }
.score-label { color:#6b7280; font-size:10px; letter-spacing:2px; margin-bottom:10px; }
.score-value { font-family:'Syne',sans-serif; font-size:36px; font-weight:800; line-height:1; margin-bottom:12px; }
.score-card.growth   .score-value { color:#22c55e; }
.score-card.inflation .score-value { color:#ef4444; }
.score-card.liquidity .score-value { color:#3b82f6; }
.score-card.risk     .score-value { color:#f59e0b; }
.score-bar-track { height:4px; background:#1f2937; border-radius:2px; overflow:hidden; margin-bottom:8px; }
.score-bar-fill { height:100%; border-radius:2px; }
.score-card.growth   .score-bar-fill { background:#22c55e; }
.score-card.inflation .score-bar-fill { background:#ef4444; }
.score-card.liquidity .score-bar-fill { background:#3b82f6; }
.score-card.risk     .score-bar-fill { background:#f59e0b; }
.score-signal { font-size:10px; color:#6b7280; }

.ai-analysis-grid { display:grid; grid-template-columns:repeat(2,1fr); gap:16px; margin-bottom:20px; }
.ai-card { background:#0f172a; border:1px solid #1f2937; border-radius:12px; padding:18px; }
.ai-card-label { font-size:10px; letter-spacing:2px; margin-bottom:8px; }
.ai-card.growth-ai   .ai-card-label { color:#22c55e; }
.ai-card.inflation-ai .ai-card-label { color:#ef4444; }
.ai-card.liquidity-ai .ai-card-label { color:#3b82f6; }
.ai-card.risk-ai     .ai-card-label { color:#f59e0b; }
.ai-card-text { color:#d1d5db; font-size:12px; line-height:1.6; }
.regime-summary-box { background:#0f172a; border:1px solid #374151; border-radius:12px; padding:24px; margin-bottom:16px; }
.regime-summary-text { color:#e5e7eb; font-size:13px; line-height:1.8; margin-bottom:16px; }
.watch-box { background:#1c1f2e; border:1px solid rgba(245,158,11,0.27); border-radius:8px; padding:12px 16px; display:flex; align-items:flex-start; gap:10px; }
.watch-icon { color:#f59e0b; font-size:14px; }
.watch-text { color:#fcd34d; font-size:12px; line-height:1.5; }

.history-table { width:100%; border-collapse:separate; border-spacing:0 6px; }
.history-table th { color:#6b7280; font-size:10px; letter-spacing:2px; padding:0 16px 12px 16px; text-align:left; border-bottom:1px solid #1f2937; }
.history-row td { padding:14px 16px; font-size:12px; color:#d1d5db; border-top:1px solid #1f2937; border-bottom:1px solid #1f2937; background:#0f172a; }
.history-row td:first-child { border-left:1px solid #1f2937; border-radius:8px 0 0 8px; }
.history-row td:last-child  { border-right:1px solid #1f2937; border-radius:0 8px 8px 0; }
.current-row td { background:#141d2e !important; border-color:#374151 !important; }
.current-row td:first-child { border-left:2px solid #00e0ff !important; }
.regime-badge { display:inline-flex; align-items:center; gap:6px; padding:4px 10px; border-radius:20px; font-size:11px; font-weight:600; }
.score-pill { display:inline-block; padding:3px 8px; border-radius:4px; font-size:11px; font-weight:600; }
.positive { background:#052e16; color:#4ade80; }
.negative { background:#2d0e0e; color:#f87171; }
.neutral  { background:#1c1f2e; color:#9ca3af; }
.current-badge { display:inline-block; background:rgba(0,224,255,0.13); border:1px solid rgba(0,224,255,0.33); color:#00e0ff; font-size:9px; letter-spacing:1px; padding:2px 6px; border-radius:4px; margin-left:8px; }
.month-cell { color:#9ca3af; font-size:11px; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------
# HEADER
# ------------------------------------------------

st.markdown(
    '<div class="header"><div class="pulse"></div>'
    '<div class="header-title">MACRO REGIME CALCULATOR</div></div>',
    unsafe_allow_html=True
)

# ------------------------------------------------
# DASHBOARD
# ------------------------------------------------

col_left, col_right = st.columns([2, 1])

with col_left:
    st.markdown(
        '<div class="panel">'
        '<div class="panel-title">CURRENT MACRO ENVIRONMENT</div>'
        '<div class="quadrant-wrapper"><div class="quadrant-inner">'
        '<div class="grid">'
        '<div class="box"></div><div class="box"></div>'
        '<div class="box"></div><div class="box"></div>'
        '</div>'
        '<div class="axis-x"></div>'
        '<div class="q-label q1">Risk-On Inflation</div>'
        '<div class="q-label q2">Risk-Off Inflation</div>'
        '<div class="q-label q3">Risk-Off Disinflation</div>'
        '<div class="q-label q4">Risk-On Disinflation</div>'
        '<div class="dot" style="left:' + str(x_percent) + '%;top:' + str(y_percent) + '%;transform:translate(-50%,-50%);"></div>'
        '</div></div>'
        '</div>',
        unsafe_allow_html=True
    )

with col_right:
    st.markdown(
        '<div class="panel" style="margin-bottom:25px;">'
        '<div class="panel-title">REGIME CLASSIFICATION</div>'
        '<div class="regime-box">🔥 ' + regime + '</div>'
        '<div class="metric-grid">'
        '<div class="metric">Growth<br><b>' + str(growth_score) + '</b></div>'
        '<div class="metric">Inflation<br><b>' + str(inflation_score) + '</b></div>'
        '<div class="metric">Liquidity<br><b>' + str(liquidity_score) + '</b></div>'
        '<div class="metric">Risk Appetite<br><b>' + str(risk_appetite_rounded) + '</b></div>'
        '</div>'
        '</div>'
        '<div class="panel">'
        '<div class="panel-title">ASSET ALLOCATION</div>'
        '<div class="asset-box">'
        '<div style="margin-bottom:10px;color:#f59e0b;">Favored Assets</div>'
        '<span class="tag">⭐ Commodities</span>'
        '<span class="tag">⭐ Value Stocks</span>'
        '<span class="tag">⭐ TIPS</span>'
        '<span class="tag">⭐ Real Estate</span>'
        '</div></div>',
        unsafe_allow_html=True
    )

# ------------------------------------------------
# SCORE BREAKDOWN
# ------------------------------------------------

st.markdown('<div class="section-header">INDIVIDUAL SCORE BREAKDOWN</div>', unsafe_allow_html=True)

st.markdown(
    '<div class="scores-grid">'

    '<div class="score-card growth">'
    '<div class="score-label">GROWTH</div>'
    '<div class="score-value">' + fmt_score(growth_score) + '</div>'
    '<div class="score-bar-track"><div class="score-bar-fill" style="width:' + str(bar_width(growth_score)) + '%"></div></div>'
    '<div class="score-signal">' + signal_text(growth_score, "Growth") + '</div>'
    '</div>'

    '<div class="score-card inflation">'
    '<div class="score-label">INFLATION</div>'
    '<div class="score-value">' + fmt_score(inflation_score) + '</div>'
    '<div class="score-bar-track"><div class="score-bar-fill" style="width:' + str(bar_width(inflation_score)) + '%"></div></div>'
    '<div class="score-signal">' + signal_text(inflation_score, "Inflation") + '</div>'
    '</div>'

    '<div class="score-card liquidity">'
    '<div class="score-label">LIQUIDITY</div>'
    '<div class="score-value">' + fmt_score(liquidity_score) + '</div>'
    '<div class="score-bar-track"><div class="score-bar-fill" style="width:' + str(bar_width(liquidity_score)) + '%"></div></div>'
    '<div class="score-signal">' + signal_text(liquidity_score, "Liquidity") + '</div>'
    '</div>'

    '<div class="score-card risk">'
    '<div class="score-label">RISK APPETITE</div>'
    '<div class="score-value">' + fmt_score(risk_appetite_rounded) + '</div>'
    '<div class="score-bar-track"><div class="score-bar-fill" style="width:' + str(bar_width(risk_appetite)) + '%"></div></div>'
    '<div class="score-signal">' + signal_text(risk_appetite, "Risk Appetite") + '</div>'
    '</div>'

    '</div>',
    unsafe_allow_html=True
)

# ------------------------------------------------
# AI ANALYSIS — auto-runs on load, cached
# ------------------------------------------------

st.markdown('<div class="section-header">AI MACRO ANALYSIS</div>', unsafe_allow_html=True)

if "ai_analysis" not in st.session_state:
    with st.spinner("Generating AI macro analysis..."):
        try:
            st.session_state.ai_analysis = get_ai_analysis(
                growth_score, inflation_score, liquidity_score, risk_appetite, regime
            )
        except Exception as e:
            st.session_state.ai_analysis = None
            st.error("AI analysis unavailable: " + str(e))

if st.session_state.ai_analysis:
    a = st.session_state.ai_analysis
    gi  = a.get("growth_interpretation", "")
    ii  = a.get("inflation_interpretation", "")
    li  = a.get("liquidity_interpretation", "")
    ri  = a.get("risk_appetite_interpretation", "")
    sm  = a.get("regime_summary", "")
    kw  = a.get("key_watch", "")

    st.markdown(
        '<div class="ai-analysis-grid">'
        '<div class="ai-card growth-ai"><div class="ai-card-label">📗 GROWTH SIGNAL</div><div class="ai-card-text">' + gi + '</div></div>'
        '<div class="ai-card inflation-ai"><div class="ai-card-label">📕 INFLATION SIGNAL</div><div class="ai-card-text">' + ii + '</div></div>'
        '<div class="ai-card liquidity-ai"><div class="ai-card-label">📘 LIQUIDITY SIGNAL</div><div class="ai-card-text">' + li + '</div></div>'
        '<div class="ai-card risk-ai"><div class="ai-card-label">📙 RISK APPETITE SIGNAL</div><div class="ai-card-text">' + ri + '</div></div>'
        '</div>'
        '<div class="regime-summary-box">'
        '<div class="panel-title">REGIME SUMMARY</div>'
        '<div class="regime-summary-text">' + sm + '</div>'
        '<div class="watch-box">'
        '<span class="watch-icon">👁</span>'
        '<div class="watch-text"><b>Key Watch:</b> ' + kw + '</div>'
        '</div></div>',
        unsafe_allow_html=True
    )

# ------------------------------------------------
# HISTORICAL REGIME TIMELINE
# ------------------------------------------------

st.markdown('<div class="section-header">HISTORICAL REGIME SHIFT TIMELINE — LAST 6 MONTHS</div>', unsafe_allow_html=True)

rows_html = ""
for i, row in enumerate(historical_data):
    is_current = (i == len(historical_data) - 1)
    row_class = "history-row current-row" if is_current else "history-row"
    current_tag = '<span class="current-badge">CURRENT</span>' if is_current else ""
    rows_html += (
        '<tr class="' + row_class + '">'
        '<td><span class="month-cell">' + row["month"] + '</span>' + current_tag + '</td>'
        '<td>' + regime_badge(row) + '</td>'
        '<td>' + score_pill(row["liquidity"]) + '</td>'
        '<td>' + score_pill(row["growth"]) + '</td>'
        '<td>' + score_pill(row["inflation"]) + '</td>'
        '<td>' + score_pill(row["risk_appetite"]) + '</td>'
        '</tr>'
    )

st.markdown(
    '<div class="panel" style="padding:0;overflow:hidden;">'
    '<table class="history-table">'
    '<thead><tr>'
    '<th>MONTH</th><th>REGIME</th><th>LIQUIDITY</th><th>GROWTH</th><th>INFLATION</th><th>RISK APPETITE</th>'
    '</tr></thead>'
    '<tbody>' + rows_html + '</tbody>'
    '</table></div>',
    unsafe_allow_html=True
)
