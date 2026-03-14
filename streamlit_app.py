import streamlit as st

st.set_page_config(layout="wide")

# -----------------------------
# SAMPLE DATA
# -----------------------------

growth_score = 35
inflation_score = -10
liquidity_score = 50

risk_appetite = (
    0.5 * liquidity_score +
    0.3 * growth_score +
    0.2 * inflation_score
)

risk_appetite = max(min(risk_appetite,100),-100)

# -----------------------------
# REGIME LOGIC
# -----------------------------

if risk_appetite > 0 and inflation_score > 0:
    regime = "Risk-On Inflation"
elif risk_appetite < 0 and inflation_score > 0:
    regime = "Risk-Off Inflation"
elif risk_appetite > 0 and inflation_score < 0:
    regime = "Risk-On Disinflation"
else:
    regime = "Risk-Off Disinflation"

# -----------------------------
# DOT POSITION
# -----------------------------

x_percent = (risk_appetite + 100) / 200 * 100
y_percent = (100 - inflation_score) / 200 * 100


# -----------------------------
# GLOBAL CSS
# -----------------------------

st.markdown("""
<style>

body {
background:#0b1220;
color:white;
}

.panel {
background:#111827;
border-radius:14px;
padding:25px;
border:1px solid #1f2937;
}

.panel-title{
color:#9ca3af;
font-size:14px;
letter-spacing:2px;
margin-bottom:20px;
}

.dashboard {
display:grid;
grid-template-columns: 2fr 1fr;
gap:30px;
}

.right-column{
display:flex;
flex-direction:column;
gap:25px;
}

.quadrant-wrapper{
position:relative;
width:500px;
height:500px;
margin:auto;
}

.grid{
display:grid;
grid-template-columns:1fr 1fr;
grid-template-rows:1fr 1fr;
width:100%;
height:100%;
border-radius:10px;
overflow:hidden;
}

.box{
border:1px solid #1f2937;
display:flex;
align-items:center;
justify-content:center;
color:#6b7280;
font-size:15px;
background:#0f172a;
}

.axis-x{
position:absolute;
top:50%;
width:100%;
height:1px;
background:#374151;
}

.axis-y{
position:absolute;
left:50%;
height:100%;
width:1px;
background:#374151;
}

.dot{
position:absolute;
width:16px;
height:16px;
background:white;
border-radius:50%;
box-shadow:0 0 12px rgba(255,255,255,0.7);
transition:all .5s ease;
}

.q-label{
position:absolute;
font-size:14px;
color:#9ca3af;
}

.q1{top:15%;left:65%;}
.q2{top:15%;left:10%;}
.q3{top:70%;left:10%;}
.q4{top:70%;left:65%;}

.regime-box{
background:#2a1b0d;
border:1px solid #f59e0b;
padding:15px;
border-radius:10px;
color:#f59e0b;
font-weight:600;
}

.metric-grid{
display:grid;
grid-template-columns:1fr 1fr;
gap:10px;
margin-top:15px;
}

.metric{
background:#1f2937;
padding:15px;
border-radius:10px;
text-align:center;
}

.asset-box{
background:#2a1b0d;
border:1px solid #f59e0b;
padding:20px;
border-radius:10px;
}

.tag{
display:inline-block;
background:#111827;
border:1px solid #374151;
padding:6px 12px;
border-radius:20px;
margin:5px;
font-size:13px;
}

</style>
""", unsafe_allow_html=True)

# -----------------------------
# DASHBOARD LAYOUT
# -----------------------------

st.markdown(f"""
<div class="dashboard">

<div class="panel">

<div class="panel-title">CURRENT MACRO ENVIRONMENT</div>

<div class="quadrant-wrapper">

<div class="grid">

<div class="box"></div>
<div class="box"></div>

<div class="box"></div>
<div class="box"></div>

</div>

<div class="axis-x"></div>
<div class="axis-y"></div>

<div class="q-label q1">Risk-On Inflation</div>
<div class="q-label q2">Risk-Off Inflation</div>
<div class="q-label q3">Risk-Off Disinflation</div>
<div class="q-label q4">Risk-On Disinflation</div>

<div class="dot"
style="
left:{x_percent}%;
top:{y_percent}%;
transform:translate(-50%,-50%);
"></div>

</div>

</div>


<div class="right-column">

<div class="panel">

<div class="panel-title">REGIME CLASSIFICATION</div>

<div class="regime-box">
🔥 {regime}
</div>

<div class="metric-grid">

<div class="metric">
Growth<br>
<b>{growth_score}</b>
</div>

<div class="metric">
Inflation<br>
<b>{inflation_score}</b>
</div>

</div>

</div>


<div class="panel">

<div class="panel-title">ASSET ALLOCATION</div>

<div class="asset-box">

<div style="margin-bottom:10px;color:#f59e0b;">Favored Assets</div>

<span class="tag">⭐ Commodities</span>
<span class="tag">⭐ Value Stocks</span>
<span class="tag">⭐ TIPS</span>
<span class="tag">⭐ Real Estate</span>

</div>

</div>

</div>

</div>
""", unsafe_allow_html=True)
