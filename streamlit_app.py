import streamlit as st

st.title("Macro Regime Dashboard")

growth_score = 12
inflation_score = -5
liquidity_score = 18

st.metric("Growth Score", growth_score)
st.metric("Inflation Score", inflation_score)
st.metric("Liquidity Score", liquidity_score)

if growth_score > 0 and inflation_score < 0:
    regime = "Goldilocks Expansion"
elif growth_score > 0 and inflation_score > 0:
    regime = "Reflation Boom"
elif growth_score < 0 and inflation_score > 0:
    regime = "Stagflation"
else:
    regime = "Deflationary Bust"

st.subheader("Current Macro Regime")
st.write(regime)
