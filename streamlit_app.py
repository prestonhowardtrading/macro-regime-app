import streamlit as st

st.set_page_config(layout="wide")

# ------------------------------------------------
# SAMPLE SCORES (we'll replace with real data later)
# ------------------------------------------------

growth_score = 35
inflation_score = -10
liquidity_score = 50

# ------------------------------------------------
# RISK APPETITE CALCULATION
# ------------------------------------------------

risk_appetite = (
    0.5 * liquidity_score +
    0.3 * growth_score +
    0.2 * inflation_score
)

risk_appetite = max(min(risk_appetite, 100), -100)

# ------------------------------------------------
# DETERMINE REGIME
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

x_percent = (risk_appetite + 100) / 200 * 100
y_percent = (100 - inflation_score) / 200 * 100


# ------------------------------------------------
# HEADER
# ------------------------------------------------

st.title("Macro Regime Dashboard")

c1, c2, c3, c4 = st.columns(4)

c1.metric("Growth Score", growth_score)
c2.metric("Inflation Score", inflation_score)
c3.metric("Liquidity Score", liquidity_score)
c4.metric("Risk Appetite", round(risk_appetite,1))

st.subheader("Current Macro Regime")
st.success(regime)


# ------------------------------------------------
# QUADRANT UI
# ------------------------------------------------

st.markdown(f"""

<style>

body {{
background-color:#0b1220;
color:white;
}}

.quadrant-wrapper {{
position:relative;
width:650px;
height:650px;
margin:auto;
}}

.grid {{
display:grid;
grid-template-columns:1fr 1fr;
grid-template-rows:1fr 1fr;
width:100%;
height:100%;
border-radius:14px;
overflow:hidden;
}}

.box {{
display:flex;
align-items:center;
justify-content:center;
font-size:18px;
color:#9ca3af;
border:1px solid #1f2937;
background:#0f172a;
}}

.axis-x {{
position:absolute;
top:50%;
width:100%;
height:1px;
background:#374151;
}}

.axis-y {{
position:absolute;
left:50%;
height:100%;
width:1px;
background:#374151;
}}

.dot {{
position:absolute;
width:16px;
height:16px;
background:white;
border-radius:50%;
box-shadow:0 0 14px 5px rgba(255,255,255,0.6);
transition: all 0.6s ease;
}}

.label-top {{
position:absolute;
top:-35px;
left:50%;
transform:translateX(-50%);
color:#9ca3af;
font-size:14px;
}}

.label-bottom {{
position:absolute;
bottom:-35px;
left:50%;
transform:translateX(-50%);
color:#9ca3af;
font-size:14px;
}}

.label-left {{
position:absolute;
left:-110px;
top:50%;
transform:translateY(-50%);
color:#9ca3af;
font-size:14px;
}}

.label-right {{
position:absolute;
right:-110px;
top:50%;
transform:translateY(-50%);
color:#9ca3af;
font-size:14px;
}}

.quadrant-label {{
position:absolute;
font-size:15px;
color:#9ca3af;
}}

.q1 {{
top:18%;
left:65%;
}}

.q2 {{
top:18%;
left:15%;
}}

.q3 {{
top:70%;
left:15%;
}}

.q4 {{
top:70%;
left:65%;
}}

</style>


<div class="quadrant-wrapper">

<div class="grid">

<div class="box"></div>
<div class="box"></div>

<div class="box"></div>
<div class="box"></div>

</div>

<div class="axis-x"></div>
<div class="axis-y"></div>

<div class="label-top">Inflation</div>
<div class="label-bottom">Disinflation</div>
<div class="label-left">Risk-Off</div>
<div class="label-right">Risk-On</div>

<div class="quadrant-label q1">Risk-On Inflation</div>
<div class="quadrant-label q2">Risk-Off Inflation</div>
<div class="quadrant-label q3">Risk-Off Disinflation</div>
<div class="quadrant-label q4">Risk-On Disinflation</div>

<div class="dot"
style="
left:{x_percent}%;
top:{y_percent}%;
transform:translate(-50%,-50%);
"></div>

</div>

""", unsafe_allow_html=True)
