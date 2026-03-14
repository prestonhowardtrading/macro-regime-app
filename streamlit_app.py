import streamlit as st
import pandas as pd

st.set_page_config(page_title="Macro Regime Dashboard", layout="wide")

# -----------------------------
# TITLE
# -----------------------------

st.title("Macro Regime Dashboard")

# -----------------------------
# SAMPLE SCORES (Replace later)
# -----------------------------

growth_score = 35
inflation_score = -10
liquidity_score = 50

# -----------------------------
# REGIME CLASSIFICATION
# -----------------------------

def classify_regime(growth, inflation):

    if growth > 0 and inflation < 0:
        return "Goldilocks Expansion"

    elif growth > 0 and inflation > 0:
        return "Reflation Boom"

    elif growth < 0 and inflation > 0:
        return "Stagflation"

    else:
        return "Deflationary Bust"


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
# REGIME QUADRANT CHART
# -----------------------------

st.subheader("Growth vs Inflation Regime Map")

data = pd.DataFrame({
    "Growth":[growth_score],
    "Inflation":[inflation_score]
})

st.scatter_chart(data, x="Growth", y="Inflation")

# -----------------------------
# SCORE BREAKDOWN (placeholder)
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

col1.write("Growth Components")
col1.bar_chart(pd.DataFrame.from_dict(growth_components, orient="index"))

col2.write("Inflation Components")
col2.bar_chart(pd.DataFrame.from_dict(inflation_components, orient="index"))

col3.write("Liquidity Components")
col3.bar_chart(pd.DataFrame.from_dict(liquidity_components, orient="index"))

# -----------------------------
# FOOTER
# -----------------------------

st.caption("Macro regime framework prototype")
