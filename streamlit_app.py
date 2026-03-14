import streamlit as st

st.set_page_config(layout="wide")

# -----------------------------
# SAMPLE SCORES (replace later)
# -----------------------------
growth_score = 35
inflation_score = -10
liquidity_score = 50

# -----------------------------
# DETERMINE REGIME
# -----------------------------
if growth_score > 0 and inflation_score > 0:
    regime = "Risk-On Inflation"
elif growth_score < 0 and inflation_score > 0:
    regime = "Risk-Off Inflation"
elif growth_score > 0 and inflation_score < 0:
    regime = "Risk-On Disinflation"
else:
    regime = "Risk-Off Disinflation"


# -----------------------------
# HEADER
# -----------------------------
st.title("Macro Regime Dashboard")

col1, col2, col3 = st.columns(3)

col1.metric("Growth Score", growth_score)
col2.metric("Inflation Score", inflation_score)
col3.metric("Liquidity Score", liquidity_score)

st.subheader("Current Macro Regime")
st.success(regime)

# -----------------------------
# QUADRANT DISPLAY
# -----------------------------
highlight = {
    "Risk-On Inflation": ["active","","",""],
    "Risk-Off Inflation": ["","active","",""],
    "Risk-Off Disinflation": ["","","active",""],
    "Risk-On Disinflation": ["","","","active"],
}

q = highlight[regime]

st.markdown(
f"""
<style>

.grid {{
display:grid;
grid-template-columns: 1fr 1fr;
grid-template-rows: 1fr 1fr;
width:600px;
height:600px;
margin:auto;
border:1px solid #333;
}}

.box {{
display:flex;
align-items:center;
justify-content:center;
font-size:20px;
color:white;
border:1px solid #333;
background:#111;
}}

.active {{
background:#9b5b00;
color:white;
font-weight:bold;
}}

.center-dot {{
width:12px;
height:12px;
background:white;
border-radius:50%;
position:absolute;
top:50%;
left:50%;
transform:translate(-50%,-50%);
}}

.wrapper {{
position:relative;
width:600px;
margin:auto;
}}

</style>

<div class="wrapper">

<div class="grid">

<div class="box {q[1]}">Risk-Off Inflation</div>
<div class="box {q[0]}">Risk-On Inflation</div>

<div class="box {q[2]}">Risk-Off Disinflation</div>
<div class="box {q[3]}">Risk-On Disinflation</div>

</div>

<div class="center-dot"></div>

</div>

""",
unsafe_allow_html=True
)
