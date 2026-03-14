import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="Macro Regime Dashboard", layout="wide")

# -----------------------------
# TITLE
# -----------------------------

st.title("Macro Regime Dashboard")

# -----------------------------
# SAMPLE SCORES
# -----------------------------

growth_score = 35
inflation_score = -10
liquidity_score = 50

# -----------------------------
# REGIME CLASSIFICATION
# -----------------------------

def classify_regime(growth, inflation):

    if growth > 0 and inflation < 0:
        return "Risk-On Disinflation"

    elif growth > 0 and inflation > 0:
        return "Risk-On Inflation"

    elif growth < 0 and inflation > 0:
        return "Risk-Off Inflation"

    else:
        return "Risk-Off Disinflation"


regime = classify_regime(growth_score, inflation_score)

# -----------------------------
# SCORE DISPLAY
# -----------------------------

col1, col2, col3 = st.columns(3)

col1.metric("Growth Score", growth_score)
col2.metric("Inflation Score", inflation_score)
col3.metric("Liquidity Score", liquidity_score)

# -----------------------------
# CURRENT REGIME
# -----------------------------

st.subheader("Current Macro Regime")
st.success(regime)

# -----------------------------
# REGIME QUADRANT MAP
# -----------------------------

st.subheader("Macro Regime Quadrant")

fig = go.Figure()

# quadrant lines
fig.add_shape(type="line", x0=0, x1=0, y0=-100, y1=100)
fig.add_shape(type="line", y0=0, y1=0, x0=-100, x1=100)

# regime point
fig.add_trace(go.Scatter(
    x=[growth_score],
    y=[inflation_score],
    mode="markers",
    marker=dict(size=16),
    name="Current Position"
))

# quadrant labels
fig.add_annotation(x=50, y=50, text="Risk-On Inflation", showarrow=False)
fig.add_annotation(x=-50, y=50, text="Risk-Off Inflation", showarrow=False)
fig.add_annotation(x=50, y=-50, text="Risk-On Disinflation", showarrow=False)
fig.add_annotation(x=-50, y=-50, text="Risk-Off Disinflation", showarrow=False)

fig.update_layout(
    xaxis_title="Growth Score",
    yaxis_title="Inflation Score",
    xaxis=dict(range=[-100,100]),
    yaxis=dict(range=[-100,100]),
    height=600
)

st.plotly_chart(fig, use_container_width=True)

# -----------------------------
# COMPONENT BREAKDOWN
# -----------------------------

st.subheader("Score Components")

growth_components = {
    "ISM PMI": 10,
    "Payroll Growth": 8,
    "Industrial Production": 7,
    "Retail Sales": 10
}

inflation_components = {
    "CPI Trend": -4,
    "PPI Trend": -2,
    "Wage Growth": -1,
    "Commodity Trend": -3
}

liquidity_components = {
    "Fed Balance Sheet": 25,
    "Treasury Liquidity": 10,
    "Credit Spreads": 8,
    "Dollar Liquidity": 7
}

col1, col2, col3 = st.columns(3)

col1.bar_chart(growth_components)
col2.bar_chart(inflation_components)
col3.bar_chart(liquidity_components)

st.caption("Macro regime framework prototype")
