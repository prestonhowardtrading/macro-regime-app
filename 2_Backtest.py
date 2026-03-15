"""
Macro Regime Backtest — Leading Indicator Framework
=====================================================
Revised scoring organized by SIGNAL TIMING not policy categories.

EARLY WARNING  (6-12 month lead) — gets you out before the crash
CONFIRMATION   (1-3 month lead)  — confirms the regime
RECOVERY SIGNAL (1-3 month lead) — gets you back in early
LIQUIDITY BOOST (confirms bull)  — QE/M2 as confirmation not trigger
"""

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.dates as mdates
from matplotlib.backends.backend_pdf import PdfPages
from datetime import date
import io
import warnings
import requests
import re
warnings.filterwarnings("ignore")

st.set_page_config(layout="wide", page_title="Regime Backtest")

# ─────────────────────────────────────────────────────────────────────────────
# STYLING
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500;600&display=swap');
html, body, [class*="st-"], [data-testid] {
    font-family: 'DM Sans', sans-serif !important;
    background-color: #0A0A0F; color: #E8E8E8;
}
[data-testid="stAppViewContainer"] { background: #0A0A0F; }
[data-testid="stHeader"]           { background: #0A0A0F; }
section[data-testid="stMain"]      { background: #0A0A0F; }
.stat-grid { display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px; }
.stat-card { background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:16px; }
.stat-lbl  { font-size:9px;letter-spacing:0.15em;color:#555;font-family:'DM Mono',monospace;margin-bottom:6px;text-transform:uppercase; }
.stat-val  { font-size:22px;font-weight:700;font-family:'DM Mono',monospace;line-height:1; }
.bear-table { width:100%;border-collapse:collapse; }
.bear-table th { font-size:9px;letter-spacing:0.15em;color:#555;text-transform:uppercase;font-family:'DM Mono',monospace;padding:10px 14px;text-align:left;border-bottom:1px solid rgba(255,255,255,0.06); }
.bear-table td { font-size:12px;color:#aaa;padding:10px 14px;border-bottom:1px solid rgba(255,255,255,0.04);font-family:'DM Mono',monospace; }
.sec-label { font-size:10px;letter-spacing:0.15em;color:#555;text-transform:uppercase;font-family:'DM Mono',monospace;margin-bottom:14px;margin-top:28px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,0.06); }
.framework-grid { display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px; }
.fw-card { border-radius:10px;padding:14px;border:1px solid; }
.fw-title { font-size:10px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;font-family:'DM Mono',monospace;margin-bottom:6px; }
.fw-desc  { font-size:11px;color:#888;line-height:1.5; }
.fw-lead  { font-size:9px;font-family:'DM Mono',monospace;margin-top:6px; }
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div style="font-size:10px;letter-spacing:0.2em;color:#555;text-transform:uppercase;'
    'font-family:\'DM Mono\',monospace;margin-bottom:4px;">Macro Regime Monitor</div>'
    '<h1 style="margin:0;font-size:28px;font-weight:600;letter-spacing:-0.02em;color:#E8E8E8;">'
    'Regime Backtest <span style="font-size:14px;color:#555;font-weight:400;">— Leading Indicator Framework</span></h1>'
    '<p style="margin:6px 0 24px;font-size:12px;color:#555;">'
    'Reorganized by signal timing: Early Warning → Confirmation → Recovery → Liquidity Boost</p>',
    unsafe_allow_html=True
)

# ─────────────────────────────────────────────────────────────────────────────
# FRED KEY
# ─────────────────────────────────────────────────────────────────────────────

fred_key = st.secrets.get("FRED_API_KEY", None)
if not fred_key:
    fred_key = st.text_input("Enter your FRED API Key", type="password",
                              placeholder="fred.stlouisfed.org/docs/api/api_key.html")
if not fred_key:
    st.markdown(
        '<div style="padding:20px;border-radius:12px;background:rgba(255,255,255,0.02);'
        'border:1px dashed rgba(255,255,255,0.08);text-align:center;color:#555;">'
        'Enter your FRED API key above to run the backtest.</div>',
        unsafe_allow_html=True
    )
    st.stop()

START = "2000-01-01"   # go back to 2000 to capture dot-com + GFC lead-up
END   = date.today().strftime("%Y-%m-%d")
TODAY = str(date.today())

# ─────────────────────────────────────────────────────────────────────────────
# DATA FETCH
# ─────────────────────────────────────────────────────────────────────────────

FRED_SERIES = {
    # Early warning
    "t10y2y":      "T10Y2Y",         # Yield curve 10Y-2Y (inversion = leading recession signal)
    "t10y3m":      "T10Y3M",         # 10Y-3M spread (even better recession predictor)
    "hy_spread":   "BAMLH0A0HYM2",   # HY credit spreads (leading crash signal)
    "ig_spread":   "BAMLC0A0CM",     # IG credit spreads
    "ism_mfg":     "NAPM",           # ISM Manufacturing PMI (leading economic signal)
    "ism_svc":     "NMFSL",          # ISM Services PMI
    # Confirmation
    "unrate":      "UNRATE",         # Unemployment rate
    "icsa":        "ICSA",           # Initial jobless claims (weekly, very leading)
    "retail":      "RSAFS",          # Retail sales
    "lei":         "USSLIND",        # Conference Board LEI (composite leading index)
    "nfci":        "NFCI",           # Chicago Fed NFCI (financial conditions)
    "tips10y":     "DFII10",         # 10Y TIPS real yield
    "t2y":         "DGS2",           # 2Y Treasury (leading rate expectations)
    "effr":        "FEDFUNDS",       # Fed funds rate
    # Recovery signals
    "t10y2y_lvl":  "T10Y2Y",         # Same series, used for steepening signal
    # Liquidity boost (confirmation, not trigger)
    "walcl":       "WALCL",          # Fed balance sheet
    "m2":          "M2SL",           # M2 money supply
    "rrp":         "RRPONTSYD",      # Reverse repo
    "tga":         "WTREGEN",        # TGA
    "dxy_proxy":   "DTWEXBGS",       # Dollar (trade-weighted)
    # Inflation context
    "cpi":         "CPIAUCSL",       # CPI
    "core_pce":    "PCEPILFE",       # Core PCE
    "breakeven5y": "T5YIE",          # 5Y breakeven
    "ppi":         "PPIACO",         # PPI
    "wages":       "CES0500000003",  # Average hourly earnings
    # CB balance sheets
    "ecb_assets":  "ECBASSETSW",
    "boj_assets":  "JPNASSETS",
    "gdpc1":       "GDPC1",
    "lending_std": "DRTSCILM",
}


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_fred(today_str, api_key):
    from fredapi import Fred
    fred = Fred(api_key=api_key)
    frames = {}
    failed = []
    for name, sid in FRED_SERIES.items():
        try:
            s = fred.get_series(sid, observation_start=START, observation_end=END)
            s.index = pd.to_datetime(s.index).tz_localize(None)
            frames[name] = s
        except Exception:
            failed.append(sid)
    df = pd.DataFrame(frames)
    df.index = pd.to_datetime(df.index)
    return df.resample("ME").last().ffill().bfill(), failed


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_market(today_str):
    import yfinance as yf
    results = {}
    failed = []
    tickers = {"sp500": "^GSPC", "dxy": "DX-Y.NYB", "bcom": "^BCOM"}
    for name, ticker in tickers.items():
        try:
            raw = yf.download(ticker, start=START, end=END,
                              progress=False, auto_adjust=True)
            s = raw["Close"][ticker] if isinstance(raw.columns, pd.MultiIndex) else raw["Close"]
            s = s.squeeze()
            s.index = pd.to_datetime(s.index).tz_localize(None)
            results[name] = s
        except Exception:
            failed.append(ticker)
    return results, failed


# ─────────────────────────────────────────────────────────────────────────────
# REVISED SCORING — ORGANIZED BY SIGNAL TIMING
#
# PHILOSOPHY:
#   Early Warning  — gets you OUT before the crash (leading by 6-12 months)
#   Confirmation   — confirms the regime (leading by 1-3 months)
#   Recovery       — gets you BACK IN early (leading by 1-3 months)
#   Liquidity      — confirms bull market continuation (coincident/lagging)
#
# KEY CHANGES vs old framework:
#   - Yield curve LEVEL is bearish when inverted (not just direction)
#   - Credit spreads: WIDENING = bearish, NARROWING = bullish (leading signal)
#   - Fed QE treated as CONFIRMATION of recovery, not initial trigger
#   - PMI uses level (above/below 50) as primary signal, not just trend
#   - Unemployment rate of CHANGE used (acceleration), not just level
# ─────────────────────────────────────────────────────────────────────────────

def pct_chg(s, n):
    return s.pct_change(n) * 100


def compute_risk_appetite(m):
    """
    Returns a single Risk Appetite score (-100 to +100) per month
    built from four timed layers.
    """

    # =========================================================================
    # LAYER 1: EARLY WARNING  (weight: 35%)
    # Signals that lead recessions/crashes by 6-12 months
    # =========================================================================
    ew = pd.Series(0.0, index=m.index)

    # ── 1a. Yield Curve LEVEL (10Y-2Y) — inversion is the single best
    #        recession predictor, historically leads by 12-18 months
    yc = m["t10y2y"]
    ew += np.where(yc >  1.0,  25,   # steep: strong growth signal
          np.where(yc >  0.5,  15,
          np.where(yc >  0.0,   5,
          np.where(yc > -0.25, -10,  # flat/slightly inverted
          np.where(yc > -0.75, -25,  # inverted: recession warning
                               -40)))))  # deeply inverted: strong warning

    # ── 1b. 10Y-3M spread (Federal Reserve's preferred recession predictor)
    if "t10y3m" in m.columns and not m["t10y3m"].isna().all():
        yc2 = m["t10y3m"]
        ew += np.where(yc2 >  1.0,  15,
              np.where(yc2 >  0.0,   5,
              np.where(yc2 > -0.5, -15,
                                   -30)))

    # ── 1c. HY Credit Spread LEVEL — elevated spreads = stress in system
    #        This leads market turns by 3-6 months
    if "hy_spread" in m.columns:
        hy = m["hy_spread"]
        hy_lvl = np.where(hy < 300,  20,   # very tight: risk-on
                 np.where(hy < 400,  10,
                 np.where(hy < 500,   0,
                 np.where(hy < 700, -15,   # elevated: caution
                 np.where(hy < 900, -30,   # stress: risk-off
                                    -45))))) # crisis: strong risk-off
        # HY spread ACCELERATION (rapid widening = early warning)
        hy_chg_3m = m["hy_spread"].diff(3)
        hy_accel = np.where(hy_chg_3m > 200, -30,  # rapid widening: crisis signal
                   np.where(hy_chg_3m > 100, -15,  # widening: caution
                   np.where(hy_chg_3m <  -100,  15, # rapid tightening: recovery
                   np.where(hy_chg_3m <  -50,    8, 0))))
        ew += pd.Series(hy_lvl, index=m.index) * 0.5
        ew += pd.Series(hy_accel, index=m.index) * 0.5

    # ── 1d. IG Credit Spread — earlier signal than HY (investment grade moves first)
    if "ig_spread" in m.columns:
        ig = m["ig_spread"]
        ig_chg = ig.diff(3)
        ew += np.where(ig_chg < -0.3, 10,   # tightening: bullish
              np.where(ig_chg < -0.1,  5,
              np.where(ig_chg >  0.5, -15,  # widening fast: warning
              np.where(ig_chg >  0.25,-8,   0))))

    # ── Scale Early Warning
    ew_score = ew.clip(-100, 100)

    # =========================================================================
    # LAYER 2: CONFIRMATION  (weight: 30%)
    # Confirms the regime direction, leads by 1-3 months
    # =========================================================================
    cf = pd.Series(0.0, index=m.index)

    # ── 2a. ISM Manufacturing PMI — level AND direction
    #        Below 50 = contraction, above 50 = expansion
    if "ism_mfg" in m.columns:
        pmi = m["ism_mfg"]
        pmi_trend = pmi.diff(3)
        cf += np.where(pmi > 55,  20,
              np.where(pmi > 52,  10,
              np.where(pmi > 50,   5,
              np.where(pmi > 48,  -5,
              np.where(pmi > 45, -15,
                                 -25)))))
        cf += np.where(pmi_trend > 3,  10,
              np.where(pmi_trend > 1,   5,
              np.where(pmi_trend < -3, -10,
              np.where(pmi_trend < -1,  -5, 0))))

    # ── 2b. ISM Services PMI
    if "ism_svc" in m.columns:
        svc = m["ism_svc"]
        cf += np.where(svc > 55,  15,
              np.where(svc > 52,   8,
              np.where(svc > 50,   3,
              np.where(svc > 48,  -8,
                                  -18))))

    # ── 2c. Initial Jobless Claims — weekly, very timely
    #        Rising claims = labor market deteriorating
    if "icsa" in m.columns:
        ic_chg = pct_chg(m["icsa"], 3)
        ic_lvl = m["icsa"]
        cf += np.where(ic_chg < -10,  15,  # claims falling fast: bullish
              np.where(ic_chg <  -5,   8,
              np.where(ic_chg >  20,  -20, # claims spiking: crisis
              np.where(ic_chg >  10,  -10,
              np.where(ic_chg >   5,   -5, 0)))))

    # ── 2d. Conference Board LEI — composite of 10 leading indicators
    lei_chg = pct_chg(m["lei"], 6)
    cf += np.where(lei_chg >  2,  15,
          np.where(lei_chg >  0.5, 8,
          np.where(lei_chg > -0.5, 0,
          np.where(lei_chg > -2,  -10,
                               -20))))

    # ── 2e. Financial Conditions (NFCI) — tightening = headwind
    if "nfci" in m.columns:
        nf = m["nfci"]
        nf_chg = nf.diff(3)
        cf += np.where(nf < -0.3,  10,  # easy conditions: bullish
              np.where(nf <  0.0,   5,
              np.where(nf <  0.3,  -5,
                                  -15)))  # very tight: bearish
        cf += np.where(nf_chg < -0.3,  10,  # rapidly easing
              np.where(nf_chg >  0.3,  -10, 0))  # rapidly tightening

    # ── 2f. Unemployment rate of change (acceleration)
    uc_3m = m["unrate"].diff(3)   # 3-month change
    uc_6m = m["unrate"].diff(6)   # 6-month change
    cf += np.where(uc_3m < -0.2,  10,  # improving fast
          np.where(uc_3m <  0.0,   5,
          np.where(uc_3m <  0.2,  -5,
          np.where(uc_3m <  0.5, -15,
                               -25))))  # rising fast: recession confirmed
    # Sahm Rule proxy: if unemployment rises 0.5% from 12M low = recession
    unrate_12m_min = m["unrate"].rolling(12).min()
    sahm = m["unrate"] - unrate_12m_min
    cf += np.where(sahm > 0.5, -20, np.where(sahm > 0.3, -10, 0))

    cf_score = cf.clip(-100, 100)

    # =========================================================================
    # LAYER 3: RECOVERY SIGNAL  (weight: 20%)
    # Detects when the worst is over and recovery is starting
    # =========================================================================
    rc = pd.Series(0.0, index=m.index)

    # ── 3a. 2Y Treasury yield direction — when 2Y starts falling, Fed pivot
    #        is being priced in. This is LEADING by 1-3 months.
    t2y_chg = m["t2y"].diff(3)
    rc += np.where(t2y_chg < -0.75,  25,  # rapid fall: Fed pivot priced in
          np.where(t2y_chg < -0.35,  15,
          np.where(t2y_chg < -0.1,    5,
          np.where(t2y_chg >  0.75,  -20, # rapid rise: tightening ahead
          np.where(t2y_chg >  0.35,  -10,
          np.where(t2y_chg >  0.1,   -3, 0))))))

    # ── 3b. Yield curve STEEPENING from inversion — recovery signal
    #        When the curve steepens WHILE still somewhat inverted = recovery starting
    yc_chg = m["t10y2y"].diff(3)
    yc_lvl = m["t10y2y"]
    rc += np.where((yc_chg > 0.3) & (yc_lvl < 0.5),  15,  # steepening from inversion
          np.where((yc_chg > 0.5) & (yc_lvl > 0),    10,   # steepening in normal terrain
          np.where(yc_chg < -0.3,                     -10, 0)))  # flattening

    # ── 3c. HY spread PEAK detection — when spreads stop widening and turn
    #        This is the single best "all clear" signal for risk assets
    if "hy_spread" in m.columns:
        hy = m["hy_spread"]
        # Rolling 3-month max to detect peaks
        hy_3m_max = hy.rolling(3).max()
        hy_turning = hy < hy_3m_max * 0.92  # spreads down 8% from recent peak
        hy_still_elevated = hy > 400
        # Falling from elevated = early recovery signal
        rc += np.where(hy_turning & hy_still_elevated,  20,
              np.where(hy_turning & ~hy_still_elevated,  10,
              np.where(hy > hy_3m_max * 0.99,            -5, 0)))  # still at peak

    # ── 3d. PMI new orders proxy — manufacturing orders leading production
    if "ism_mfg" in m.columns:
        pmi_chg = m["ism_mfg"].diff(3)
        pmi_lvl = m["ism_mfg"]
        # Rising from below 50 = recovery starting
        rc += np.where((pmi_chg > 2) & (pmi_lvl < 52),  15,
              np.where((pmi_chg > 2) & (pmi_lvl > 52),   8,
              np.where(pmi_chg < -3,                     -10, 0)))

    rc_score = rc.clip(-100, 100)

    # =========================================================================
    # LAYER 4: LIQUIDITY BOOST  (weight: 15%)
    # QE, money printing, dollar weakness — CONFIRMS bull market
    # NOT a trigger, but adds fuel once recovery is underway
    # =========================================================================
    lq = pd.Series(0.0, index=m.index)

    # ── 4a. Fed balance sheet — RATE OF CHANGE matters, not YoY
    #        Fast expansion = emergency (neutral/bearish context-dependent)
    #        Slow steady expansion = accommodative = bullish
    #        Contraction (QT) = tightening = headwind
    walcl_yoy  = pct_chg(m["walcl"], 12)
    walcl_3m   = pct_chg(m["walcl"], 3)
    # Normal accommodative expansion (2-15% YoY) = bullish
    # Crisis QE (>15% YoY) = neutral (emergency mode, not inherently bullish yet)
    # QT (negative) = bearish headwind
    lq += np.where((walcl_yoy > 2)  & (walcl_yoy < 15),  15,  # steady accommodation
          np.where((walcl_yoy > 15) & (walcl_3m < 5),     5,   # big QE but slowing
          np.where(walcl_yoy < -2,                        -20,  # QT: headwind
          np.where(walcl_yoy < 0,                          -8, 0))))

    # ── 4b. Global CB balance sheets (ECB + BOJ)
    if "ecb_assets" in m.columns and not m["ecb_assets"].isna().all():
        ecb_yoy = pct_chg(m["ecb_assets"], 12)
        lq += np.where(ecb_yoy > 5, 10, np.where(ecb_yoy > 0, 5,
              np.where(ecb_yoy < -5, -10, np.where(ecb_yoy < 0, -5, 0)))) * 0.4

    if "boj_assets" in m.columns and not m["boj_assets"].isna().all():
        boj_yoy = pct_chg(m["boj_assets"], 12)
        lq += np.where(boj_yoy > 5, 8, np.where(boj_yoy > 0, 3,
              np.where(boj_yoy < -5, -8, np.where(boj_yoy < 0, -3, 0)))) * 0.4

    # ── 4c. M2 growth — money supply acceleration
    m2_yoy = pct_chg(m["m2"], 12)
    lq += np.where(m2_yoy > 8,  10,
          np.where(m2_yoy > 4,   5,
          np.where(m2_yoy > 0,   0,
          np.where(m2_yoy > -4, -8,
                               -15))))

    # ── 4d. Dollar direction — weak dollar = global liquidity boost
    dxy_col = "dxy" if ("dxy" in m.columns and not m["dxy"].isna().all()) else "dxy_proxy"
    if dxy_col in m.columns:
        dc = pct_chg(m[dxy_col], 3)
        lq += np.where(dc < -3,  12,
              np.where(dc < -1,   6,
              np.where(dc >  3,  -12,
              np.where(dc >  1,   -6, 0))))

    # ── 4e. TGA / RRP (Treasury liquidity plumbing)
    if "tga" in m.columns:
        tga_chg = m["tga"].diff(3)
        lq += np.where(tga_chg < -150,  10,
              np.where(tga_chg < -75,    5,
              np.where(tga_chg >  150,  -10,
              np.where(tga_chg >  75,    -5, 0))))

    if "rrp" in m.columns:
        rrp_chg = m["rrp"].diff(3).fillna(0)
        lq += np.where(rrp_chg < -150,  8,
              np.where(rrp_chg < -50,   3,
              np.where(rrp_chg >  150,  -8,
              np.where(rrp_chg >  50,   -3, 0))))

    lq_score = lq.clip(-100, 100)

    # =========================================================================
    # INFLATION CONTEXT  (used for regime quadrant, not risk appetite)
    # =========================================================================
    inf = pd.Series(0.0, index=m.index)
    cm = m["cpi"].pct_change(1) * 100
    inf += np.where(cm > 0.3, 20, np.where(cm > 0.1, 10,
           np.where(cm > -0.1, 0, np.where(cm > -0.3, -10, -20))))
    py = pct_chg(m["core_pce"], 12)
    inf += np.where(py > 3, 10, np.where(py > 2, 5, np.where(py > 1.5, 0, -10)))
    bcom_col = "bcom" if ("bcom" in m.columns and not m["bcom"].isna().all()) else "ppi"
    bc = pct_chg(m[bcom_col], 6)
    inf += np.where(bc > 10, 15, np.where(bc > 5, 5,
           np.where(bc > -5, 0, np.where(bc > -10, -5, -10))))
    if "wages" in m.columns:
        wy = pct_chg(m["wages"], 12)
        inf += np.where(wy > 5, 15, np.where(wy > 3, 5, np.where(wy > 2, 0, -10)))
    bc_chg = m["breakeven5y"].diff(3)
    inf += np.where(bc_chg > 0.5, 15, np.where(bc_chg > 0.1, 5,
           np.where(bc_chg > -0.1, 0, -10)))
    inflation_score = inf.clip(-100, 100)

    # =========================================================================
    # COMPOSITE RISK APPETITE
    # Weighted combination of all four layers
    # =========================================================================
    risk_appetite = (
        ew_score  * 0.35 +
        cf_score  * 0.30 +
        rc_score  * 0.20 +
        lq_score  * 0.15
    ).clip(-100, 100)

    return risk_appetite, inflation_score, ew_score, cf_score, rc_score, lq_score


# ─────────────────────────────────────────────────────────────────────────────
# FETCH DATA
# ─────────────────────────────────────────────────────────────────────────────

pb = st.progress(0, text="Fetching FRED data...")
monthly, fred_failed = fetch_fred(TODAY, fred_key)

pb.progress(60, text="Fetching market data (DXY, BCOM, S&P 500)...")
yf_data, yf_failed = fetch_market(TODAY)

pb.progress(90, text="Calculating regime scores...")

# Merge yfinance into monthly
for name, series in yf_data.items():
    if series is not None and not series.empty:
        series.index = pd.to_datetime(series.index).tz_localize(None)
        monthly[name] = series.resample("ME").last().reindex(monthly.index).ffill()

# Calculate scores
ra, inf_score, ew, cf, rc, lq = compute_risk_appetite(monthly)

regime = pd.Series("Risk-Off", index=monthly.index)
regime[ra > 0] = "Risk-On"

pb.progress(100, text="Done!")
pb.empty()

# Align S&P 500
sp_daily = yf_data.get("sp500", pd.Series(dtype=float))
if sp_daily is None or sp_daily.empty:
    st.error("Could not fetch S&P 500 from yfinance. Please try again.")
    st.stop()

sp_daily.index = pd.to_datetime(sp_daily.index).tz_localize(None)
sp_monthly = sp_daily.resample("ME").last()

combined = pd.DataFrame({
    "sp500":   sp_monthly,
    "ra":      ra,
    "ew":      ew,
    "cf":      cf,
    "rc":      rc,
    "lq":      lq,
    "regime":  regime,
    "infl":    inf_score,
}).dropna(subset=["sp500", "ra"])

if combined.empty:
    st.error("No overlapping data. Please try again.")
    st.stop()

start_date   = combined.index[0]
sp_aligned   = sp_daily[sp_daily.index >= start_date].dropna()
daily_regime = regime.reindex(sp_aligned.index, method="ffill").ffill()

# ─────────────────────────────────────────────────────────────────────────────
# FRAMEWORK EXPLANATION
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="sec-label">Framework Architecture</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="framework-grid">'

    '<div class="fw-card" style="background:rgba(255,71,87,0.08);border-color:rgba(255,71,87,0.3);">'
    '<div class="fw-title" style="color:#FF4757;">Early Warning — 35%</div>'
    '<div class="fw-desc">Gets you OUT before the crash. Leads by 6-12 months.</div>'
    '<div class="fw-lead" style="color:#FF4757;">Yield curve level · HY spread level + acceleration · IG spread widening</div>'
    '</div>'

    '<div class="fw-card" style="background:rgba(245,158,11,0.08);border-color:rgba(245,158,11,0.3);">'
    '<div class="fw-title" style="color:#f59e0b;">Confirmation — 30%</div>'
    '<div class="fw-desc">Confirms the regime direction. Leads by 1-3 months.</div>'
    '<div class="fw-lead" style="color:#f59e0b;">ISM PMI level · Jobless claims · LEI · NFCI · Sahm Rule</div>'
    '</div>'

    '<div class="fw-card" style="background:rgba(0,212,170,0.08);border-color:rgba(0,212,170,0.3);">'
    '<div class="fw-title" style="color:#00D4AA;">Recovery Signal — 20%</div>'
    '<div class="fw-desc">Gets you BACK IN early. Leads market by 1-3 months.</div>'
    '<div class="fw-lead" style="color:#00D4AA;">2Y yield turning · Curve steepening · HY spread peak · PMI turning</div>'
    '</div>'

    '<div class="fw-card" style="background:rgba(91,141,239,0.08);border-color:rgba(91,141,239,0.3);">'
    '<div class="fw-title" style="color:#5B8DEF;">Liquidity Boost — 15%</div>'
    '<div class="fw-desc">Confirms bull market fuel. QE as confirmation not trigger.</div>'
    '<div class="fw-lead" style="color:#5B8DEF;">Fed BS (steady expansion) · ECB/BOJ · M2 · Dollar · TGA/RRP</div>'
    '</div>'

    '</div>',
    unsafe_allow_html=True
)

# ─────────────────────────────────────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────────────────────────────────────

on_pct      = (combined["regime"] == "Risk-On").mean() * 100
off_pct     = 100 - on_pct
transitions = int((combined["regime"] != combined["regime"].shift()).sum() - 1)
date_range  = combined.index[0].strftime("%b %Y") + " — " + combined.index[-1].strftime("%b %Y")

st.markdown('<div class="sec-label">Regime Statistics</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="stat-grid">'
    '<div class="stat-card"><div class="stat-lbl">Date Range</div>'
    '<div class="stat-val" style="font-size:14px;color:#aaa;">' + date_range + '</div></div>'
    '<div class="stat-card"><div class="stat-lbl">Risk-On</div>'
    '<div class="stat-val" style="color:#00D4AA;">' + str(round(on_pct)) + '%</div></div>'
    '<div class="stat-card"><div class="stat-lbl">Risk-Off</div>'
    '<div class="stat-val" style="color:#FF4757;">' + str(round(off_pct)) + '%</div></div>'
    '<div class="stat-card"><div class="stat-lbl">Regime Switches</div>'
    '<div class="stat-val" style="color:#E8E8E8;">' + str(transitions) + '</div></div>'
    '</div>',
    unsafe_allow_html=True
)

# Bear market + bull market verdicts
events = {
    "Dot-com 2000-02":     ("2000-03", "2002-10", "bear"),
    "GFC 2007-09":         ("2007-10", "2009-03", "bear"),
    "COVID crash 2020":    ("2020-02", "2020-04", "bear"),
    "COVID recovery 2020": ("2020-04", "2021-12", "bull"),
    "Bear Market 2022":    ("2022-01", "2022-10", "bear"),
    "Bull 2023-present":   ("2022-10", "2024-12", "bull"),
}

st.markdown('<div class="sec-label">Key Market Periods — Model Accuracy</div>', unsafe_allow_html=True)
rows = ""
for name, (bs, be, kind) in events.items():
    try:
        window = combined.loc[bs:be, "regime"]
        if len(window) == 0:
            continue
        off_p = (window == "Risk-Off").mean() * 100
        on_p  = 100 - off_p
        if kind == "bear":
            pct_correct = off_p
            want = "Risk-Off during crash"
            color = "#00D4AA" if off_p >= 60 else ("#f59e0b" if off_p >= 40 else "#FF4757")
            verdict = "✓ Avoided" if off_p >= 60 else ("~ Partial" if off_p >= 40 else "✗ Missed")
        else:
            pct_correct = on_p
            want = "Risk-On during bull"
            color = "#00D4AA" if on_p >= 60 else ("#f59e0b" if on_p >= 40 else "#FF4757")
            verdict = "✓ Captured" if on_p >= 60 else ("~ Partial" if on_p >= 40 else "✗ Missed")

        type_color = "#FF4757" if kind == "bear" else "#00D4AA"
        rows += (
            '<tr>'
            '<td><span style="color:' + type_color + ';font-size:9px;margin-right:6px;">'
            + ("▼" if kind == "bear" else "▲") + '</span>' + name + '</td>'
            '<td style="color:#aaa;">' + want + '</td>'
            '<td style="color:' + type_color + ';">' + str(round(pct_correct)) + '%</td>'
            '<td style="color:' + color + ';font-weight:600;">' + verdict + '</td>'
            '</tr>'
        )
    except Exception:
        pass

st.markdown(
    '<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);'
    'border-radius:12px;overflow:hidden;">'
    '<table class="bear-table"><thead><tr>'
    '<th>Period</th><th>Target</th><th>Correct %</th><th>Verdict</th>'
    '</tr></thead><tbody>' + rows + '</tbody></table></div>',
    unsafe_allow_html=True
)

# ─────────────────────────────────────────────────────────────────────────────
# CHART — Main + 4 layer sub-scores
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="sec-label">S&P 500 with Macro Regime Overlay</div>', unsafe_allow_html=True)

fig = plt.figure(figsize=(18, 14), facecolor="#0A0A0F")
gs  = fig.add_gridspec(3, 1, height_ratios=[3, 1, 1], hspace=0.06)

ax1 = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1])
ax3 = fig.add_subplot(gs[2])

for ax in [ax1, ax2, ax3]:
    ax.set_facecolor("#0A0A0F")
    ax.tick_params(colors="#555", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#1a1a2e")

# ── Regime shading ────────────────────────────────────────────────────────
in_regime, span_start = None, None
for d, r in zip(daily_regime.index, daily_regime.values):
    if r != in_regime:
        if in_regime is not None:
            c = "#00D4AA" if in_regime == "Risk-On" else "#FF4757"
            ax1.axvspan(span_start, d, alpha=0.15, color=c, linewidth=0)
        in_regime, span_start = r, d
if in_regime:
    c = "#00D4AA" if in_regime == "Risk-On" else "#FF4757"
    ax1.axvspan(span_start, daily_regime.index[-1], alpha=0.15, color=c, linewidth=0)

# ── S&P line ──────────────────────────────────────────────────────────────
ax1.plot(sp_aligned.index, sp_aligned.values, color="#E8E8E8", linewidth=1.1, zorder=5)
ax1.set_yscale("log")
ax1.set_ylabel("S&P 500 (log)", color="#666", fontsize=8, labelpad=8)
ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))
ax1.set_xlim(sp_aligned.index[0], sp_aligned.index[-1])
ax1.set_xticklabels([])
ax1.grid(axis="y", color="#111122", linewidth=0.5)
ax1.xaxis.set_major_locator(mdates.YearLocator(2))

# Event lines
for ds, lbl in [("2007-07", "GFC start"), ("2020-02", "COVID"), ("2021-11", "Top"), ("2022-10", "Bottom")]:
    try:
        ed = pd.Timestamp(ds)
        if sp_aligned.index[0] <= ed <= sp_aligned.index[-1]:
            ax1.axvline(ed, color="#333", linewidth=0.7, linestyle="--", zorder=3)
            ax1.text(ed, sp_aligned.max() * 0.9, lbl, color="#555", fontsize=7,
                     ha="center", bbox=dict(boxstyle="round,pad=0.2",
                     facecolor="#0A0A0F", edgecolor="#333", alpha=0.8))
    except Exception:
        pass

p1 = mpatches.Patch(color="#00D4AA", alpha=0.5, label="Risk-On")
p2 = mpatches.Patch(color="#FF4757", alpha=0.5, label="Risk-Off")
ax1.legend(handles=[p1, p2], loc="upper left", framealpha=0, fontsize=8, labelcolor="#aaa")
ax1.set_title("S&P 500 — Leading Indicator Macro Regime Framework",
              color="#E8E8E8", fontsize=11, fontweight="bold", pad=10, loc="left")

# ── Risk Appetite composite ───────────────────────────────────────────────
ra_m = combined["ra"]
ax2.fill_between(ra_m.index, ra_m, 0, where=ra_m >= 0, color="#00D4AA", alpha=0.3, interpolate=True)
ax2.fill_between(ra_m.index, ra_m, 0, where=ra_m < 0,  color="#FF4757", alpha=0.3, interpolate=True)
ax2.plot(ra_m.index, ra_m.values, color="#aaa", linewidth=0.9, zorder=5)
ax2.axhline(0, color="#333", linewidth=0.8)
ax2.set_ylim(-100, 100)
ax2.set_xlim(ra_m.index[0], ra_m.index[-1])
ax2.set_ylabel("Risk Appetite", color="#666", fontsize=7, labelpad=6)
ax2.set_xticklabels([])
ax2.xaxis.set_major_locator(mdates.YearLocator(2))
ax2.grid(axis="y", color="#111122", linewidth=0.5)

# ── Layer sub-scores ──────────────────────────────────────────────────────
layer_colors = {
    "ew": "#FF4757", "cf": "#f59e0b", "rc": "#00D4AA", "lq": "#5B8DEF"
}
layer_labels = {
    "ew": "Early Warn", "cf": "Confirm", "rc": "Recovery", "lq": "Liquidity"
}

for lname, lcolor in layer_colors.items():
    ls = combined[lname]
    ax3.plot(ls.index, ls.values, color=lcolor, linewidth=0.8,
             alpha=0.8, label=layer_labels[lname])

ax3.axhline(0, color="#333", linewidth=0.8)
ax3.set_ylim(-100, 100)
ax3.set_xlim(combined.index[0], combined.index[-1])
ax3.set_ylabel("Layer Scores", color="#666", fontsize=7, labelpad=6)
ax3.xaxis.set_major_locator(mdates.YearLocator(2))
ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax3.grid(axis="y", color="#111122", linewidth=0.5)
ax3.legend(loc="upper left", framealpha=0, fontsize=7, labelcolor="#aaa", ncol=4)

fig.text(0.99, 0.005,
         "Generated " + TODAY + "  ·  FRED + yfinance  ·  Leading Indicator Framework",
         ha="right", va="bottom", color="#333", fontsize=7, fontfamily="monospace")

plt.tight_layout(rect=[0, 0.01, 1, 1])
st.pyplot(fig, use_container_width=True)

# PDF download
pdf_buf = io.BytesIO()
with PdfPages(pdf_buf) as pdf:
    pdf.savefig(fig, facecolor="#0A0A0F", dpi=180)
plt.close(fig)
pdf_buf.seek(0)

st.download_button(
    label="Download PDF",
    data=pdf_buf,
    file_name="regime_backtest_leading_" + TODAY + ".pdf",
    mime="application/pdf",
)
