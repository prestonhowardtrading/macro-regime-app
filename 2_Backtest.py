"""
Macro Regime Backtest — Leading Indicator Framework v3
=======================================================
Fixes applied:
  1. Rate shock detector    — catches 2022 (2Y yield acceleration in late 2021)
  2. Signal smoothing       — 3-month rolling average prevents whipsaw
  3. Minimum regime duration — 2 months before flipping, eliminates COVID noise
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
warnings.filterwarnings("ignore")

st.set_page_config(layout="wide", page_title="Regime Backtest v3")

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
.fix-grid  { display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:20px; }
.fix-card  { border-radius:10px;padding:14px;border:1px solid rgba(0,212,170,0.25);background:rgba(0,212,170,0.05); }
.fix-title { font-size:10px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;font-family:'DM Mono',monospace;color:#00D4AA;margin-bottom:6px; }
.fix-desc  { font-size:11px;color:#888;line-height:1.5; }
.bear-table { width:100%;border-collapse:collapse; }
.bear-table th { font-size:9px;letter-spacing:0.15em;color:#555;text-transform:uppercase;font-family:'DM Mono',monospace;padding:10px 14px;text-align:left;border-bottom:1px solid rgba(255,255,255,0.06); }
.bear-table td { font-size:12px;color:#aaa;padding:10px 14px;border-bottom:1px solid rgba(255,255,255,0.04);font-family:'DM Mono',monospace; }
.sec-label { font-size:10px;letter-spacing:0.15em;color:#555;text-transform:uppercase;font-family:'DM Mono',monospace;margin-bottom:14px;margin-top:28px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,0.06); }
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div style="font-size:10px;letter-spacing:0.2em;color:#555;text-transform:uppercase;'
    'font-family:\'DM Mono\',monospace;margin-bottom:4px;">Macro Regime Monitor</div>'
    '<h1 style="margin:0;font-size:28px;font-weight:600;letter-spacing:-0.02em;color:#E8E8E8;">'
    'Regime Backtest <span style="font-size:14px;color:#555;font-weight:400;">v3 — Rate Shock + Smoothing + Min Duration</span></h1>'
    '<p style="margin:6px 0 24px;font-size:12px;color:#555;">'
    'Three targeted fixes to catch 2022 and eliminate COVID whipsaw</p>',
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

START = "2000-01-01"
END   = date.today().strftime("%Y-%m-%d")
TODAY = str(date.today())

# ─────────────────────────────────────────────────────────────────────────────
# DATA FETCH
# ─────────────────────────────────────────────────────────────────────────────

FRED_SERIES = {
    "t10y2y":      "T10Y2Y",
    "t10y3m":      "T10Y3M",
    "t2y":         "DGS2",
    "effr":        "FEDFUNDS",
    "tips10y":     "DFII10",
    "hy_spread":   "BAMLH0A0HYM2",
    "ig_spread":   "BAMLC0A0CM",
    "ism_mfg":     "NAPM",
    "ism_svc":     "NMFSL",
    "unrate":      "UNRATE",
    "icsa":        "ICSA",
    "retail":      "RSAFS",
    "lei":         "USSLIND",
    "nfci":        "NFCI",
    "walcl":       "WALCL",
    "m2":          "M2SL",
    "rrp":         "RRPONTSYD",
    "tga":         "WTREGEN",
    "dxy_proxy":   "DTWEXBGS",
    "cpi":         "CPIAUCSL",
    "core_pce":    "PCEPILFE",
    "breakeven5y": "T5YIE",
    "ppi":         "PPIACO",
    "wages":       "CES0500000003",
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
# SCORING
# ─────────────────────────────────────────────────────────────────────────────

def pct_chg(s, n):
    return s.pct_change(n) * 100


def compute_raw_score(m):
    """
    Returns raw Risk Appetite score before smoothing/overrides.
    Four layers: Early Warning (35%), Confirmation (30%),
                 Recovery (20%), Liquidity Boost (15%)
    """

    # ── LAYER 1: EARLY WARNING (35%) ─────────────────────────────────────
    ew = pd.Series(0.0, index=m.index)

    # Yield curve 10Y-2Y level — inversion is the best recession predictor
    yc = m["t10y2y"]
    ew += np.where(yc >  1.0,  25,
          np.where(yc >  0.5,  15,
          np.where(yc >  0.0,   5,
          np.where(yc > -0.25,-10,
          np.where(yc > -0.75,-25,
                              -40)))))

    # 10Y-3M spread (Fed's preferred recession predictor)
    if "t10y3m" in m.columns and not m["t10y3m"].isna().all():
        yc2 = m["t10y3m"]
        ew += np.where(yc2 >  1.0,  15,
              np.where(yc2 >  0.0,   5,
              np.where(yc2 > -0.5, -15,
                                   -30)))

    # HY spread level (elevated = stress) + acceleration (rapid widening = warning)
    if "hy_spread" in m.columns:
        hy = m["hy_spread"]
        hy_lvl = np.where(hy < 300,  20,
                 np.where(hy < 400,  10,
                 np.where(hy < 500,   0,
                 np.where(hy < 700, -15,
                 np.where(hy < 900, -30,
                                    -45)))))
        hy_chg = m["hy_spread"].diff(3)
        hy_acc = np.where(hy_chg >  200, -30,
                 np.where(hy_chg >  100, -15,
                 np.where(hy_chg < -100,  15,
                 np.where(hy_chg <  -50,   8, 0))))
        ew += pd.Series(hy_lvl, index=m.index) * 0.5
        ew += pd.Series(hy_acc, index=m.index) * 0.5

    # IG spread change (moves earlier than HY)
    if "ig_spread" in m.columns:
        ig_chg = m["ig_spread"].diff(3)
        ew += np.where(ig_chg < -0.3,  10,
              np.where(ig_chg < -0.1,   5,
              np.where(ig_chg >  0.5,  -15,
              np.where(ig_chg >  0.25,  -8, 0))))

    ew_score = ew.clip(-100, 100)

    # ── LAYER 2: CONFIRMATION (30%) ───────────────────────────────────────
    cf = pd.Series(0.0, index=m.index)

    # ISM Manufacturing PMI — level and trend
    if "ism_mfg" in m.columns:
        pmi = m["ism_mfg"]
        cf += np.where(pmi > 55,  20,
              np.where(pmi > 52,  10,
              np.where(pmi > 50,   5,
              np.where(pmi > 48,  -5,
              np.where(pmi > 45, -15,
                                  -25)))))
        pmi_t = pmi.diff(3)
        cf += np.where(pmi_t > 3,  10,
              np.where(pmi_t > 1,   5,
              np.where(pmi_t < -3, -10,
              np.where(pmi_t < -1,  -5, 0))))

    # ISM Services PMI
    if "ism_svc" in m.columns:
        svc = m["ism_svc"]
        cf += np.where(svc > 55,  15,
              np.where(svc > 52,   8,
              np.where(svc > 50,   3,
              np.where(svc > 48,  -8,
                                  -18))))

    # Initial jobless claims — very timely
    if "icsa" in m.columns:
        ic_chg = pct_chg(m["icsa"], 3)
        cf += np.where(ic_chg < -10,  15,
              np.where(ic_chg <  -5,   8,
              np.where(ic_chg >  20,  -20,
              np.where(ic_chg >  10,  -10,
              np.where(ic_chg >   5,   -5, 0)))))

    # Conference Board LEI
    lei_chg = pct_chg(m["lei"], 6)
    cf += np.where(lei_chg >  2,  15,
          np.where(lei_chg >  0.5, 8,
          np.where(lei_chg > -0.5, 0,
          np.where(lei_chg > -2,  -10,
                               -20))))

    # NFCI financial conditions
    if "nfci" in m.columns:
        nf    = m["nfci"]
        nf_c  = nf.diff(3)
        cf += np.where(nf < -0.3,  10,
              np.where(nf <  0.0,   5,
              np.where(nf <  0.3,  -5,
                                   -15)))
        cf += np.where(nf_c < -0.3,  10,
              np.where(nf_c >  0.3, -10, 0))

    # Unemployment acceleration + Sahm Rule
    uc_3m = m["unrate"].diff(3)
    cf += np.where(uc_3m < -0.2,  10,
          np.where(uc_3m <  0.0,   5,
          np.where(uc_3m <  0.2,  -5,
          np.where(uc_3m <  0.5, -15,
                               -25))))
    sahm = m["unrate"] - m["unrate"].rolling(12).min()
    cf += np.where(sahm > 0.5, -20, np.where(sahm > 0.3, -10, 0))

    cf_score = cf.clip(-100, 100)

    # ── LAYER 3: RECOVERY SIGNAL (20%) ────────────────────────────────────
    rc = pd.Series(0.0, index=m.index)

    # 2Y Treasury direction — falling 2Y = Fed pivot priced in
    t2y_c = m["t2y"].diff(3)
    rc += np.where(t2y_c < -0.75,  25,
          np.where(t2y_c < -0.35,  15,
          np.where(t2y_c < -0.1,    5,
          np.where(t2y_c >  0.75,  -20,
          np.where(t2y_c >  0.35,  -10,
          np.where(t2y_c >  0.1,    -3, 0))))))

    # Yield curve steepening from inversion
    yc_c = m["t10y2y"].diff(3)
    rc += np.where((yc_c > 0.3) & (yc < 0.5),  15,
          np.where((yc_c > 0.5) & (yc > 0),    10,
          np.where(yc_c < -0.3,               -10, 0)))

    # HY spread peak detection — spreads rolling over = all-clear
    if "hy_spread" in m.columns:
        hy        = m["hy_spread"]
        hy_3m_max = hy.rolling(3).max()
        hy_turn   = hy < hy_3m_max * 0.92
        hy_elev   = hy > 400
        rc += np.where(hy_turn & hy_elev,   20,
              np.where(hy_turn & ~hy_elev,  10,
              np.where(hy > hy_3m_max * 0.99, -5, 0)))

    # PMI turning from below 50
    if "ism_mfg" in m.columns:
        pmi_c = m["ism_mfg"].diff(3)
        pmi_l = m["ism_mfg"]
        rc += np.where((pmi_c > 2) & (pmi_l < 52),  15,
              np.where((pmi_c > 2) & (pmi_l > 52),   8,
              np.where(pmi_c < -3,                  -10, 0)))

    rc_score = rc.clip(-100, 100)

    # ── LAYER 4: LIQUIDITY BOOST (15%) ────────────────────────────────────
    lq = pd.Series(0.0, index=m.index)

    # Fed BS: steady expansion = bullish, crisis QE = neutral, QT = bearish
    walcl_yoy = pct_chg(m["walcl"], 12)
    walcl_3m  = pct_chg(m["walcl"], 3)
    lq += np.where((walcl_yoy > 2)  & (walcl_yoy < 15),  15,
          np.where((walcl_yoy > 15) & (walcl_3m  <  5),   5,
          np.where(walcl_yoy < -2,                        -20,
          np.where(walcl_yoy < 0,                          -8, 0))))

    # ECB + BOJ
    if "ecb_assets" in m.columns and not m["ecb_assets"].isna().all():
        ecb = pct_chg(m["ecb_assets"], 12)
        lq += np.where(ecb > 5, 8, np.where(ecb > 0, 3,
              np.where(ecb < -5, -8, np.where(ecb < 0, -3, 0)))) * 0.4

    if "boj_assets" in m.columns and not m["boj_assets"].isna().all():
        boj = pct_chg(m["boj_assets"], 12)
        lq += np.where(boj > 5, 6, np.where(boj > 0, 2,
              np.where(boj < -5, -6, np.where(boj < 0, -2, 0)))) * 0.4

    # M2
    m2_yoy = pct_chg(m["m2"], 12)
    lq += np.where(m2_yoy > 8,  10,
          np.where(m2_yoy > 4,   5,
          np.where(m2_yoy > 0,   0,
          np.where(m2_yoy > -4, -8,
                               -15))))

    # Dollar (weak dollar = global liquidity)
    dxy_col = "dxy" if ("dxy" in m.columns and not m["dxy"].isna().all()) else "dxy_proxy"
    dc = pct_chg(m[dxy_col], 3)
    lq += np.where(dc < -3,  12,
          np.where(dc < -1,   6,
          np.where(dc >  3,  -12,
          np.where(dc >  1,   -6, 0))))

    # TGA / RRP plumbing
    if "tga" in m.columns:
        tga_c = m["tga"].diff(3)
        lq += np.where(tga_c < -150,  10,
              np.where(tga_c < -75,    5,
              np.where(tga_c >  150,  -10,
              np.where(tga_c >  75,    -5, 0))))

    if "rrp" in m.columns:
        rrp_c = m["rrp"].diff(3).fillna(0)
        lq += np.where(rrp_c < -150,  8,
              np.where(rrp_c < -50,   3,
              np.where(rrp_c >  150,  -8,
              np.where(rrp_c >  50,   -3, 0))))

    lq_score = lq.clip(-100, 100)

    # ── INFLATION CONTEXT ─────────────────────────────────────────────────
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
    bc_c = m["breakeven5y"].diff(3)
    inf += np.where(bc_c > 0.5, 15, np.where(bc_c > 0.1, 5,
           np.where(bc_c > -0.1, 0, -10)))
    inflation_score = inf.clip(-100, 100)

    # ── COMPOSITE (raw, before fixes) ────────────────────────────────────
    raw = (
        ew_score * 0.35 +
        cf_score * 0.30 +
        rc_score * 0.20 +
        lq_score * 0.15
    ).clip(-100, 100)

    return raw, inflation_score, ew_score, cf_score, rc_score, lq_score


def apply_fixes(raw, m):
    """
    FIX 1 — RATE SHOCK DETECTOR
        If 2Y yield rises > 1.25% in 6 months → Risk-Off override.
        If Fed funds rises > 1.0% in 6 months → Risk-Off override.
        These catch pure rate-driven bear markets like 2022.

    FIX 2 — SIGNAL SMOOTHING
        Apply 3-month rolling average to raw score before classification.
        Prevents single-month spikes from triggering regime flip.

    FIX 3 — MINIMUM REGIME DURATION
        Once regime flips, it must stay for at least 2 months
        before flipping back. Eliminates COVID-style whipsaw.
    """

    score = raw.copy()

    # ── FIX 1: Rate shock override ────────────────────────────────────────
    t2y_6m  = m["t2y"].diff(6)
    effr_6m = m["effr"].diff(6)

    # Rising rates = tightening shock = force score negative
    rate_shock = (t2y_6m > 1.25) | (effr_6m > 1.0)

    # Apply a strong negative penalty when rate shock is active
    # Scale by magnitude: bigger shock = bigger penalty
    shock_magnitude = np.where(
        t2y_6m > 2.0,  -60,
        np.where(t2y_6m > 1.5,  -45,
        np.where(t2y_6m > 1.25, -30,
        np.where(effr_6m > 2.0, -60,
        np.where(effr_6m > 1.5, -45,
        np.where(effr_6m > 1.0, -30, 0)))))
    )
    shock_series = pd.Series(shock_magnitude, index=m.index)

    # Blend shock penalty into score (not replace — blend 50/50 when active)
    score = pd.Series(
        np.where(rate_shock,
                 score * 0.4 + shock_series * 0.6,  # shock dominates
                 score),
        index=m.index
    )

    # Also: falling rates = recovery bonus (rate cuts after shock)
    rate_easing = t2y_6m < -1.0
    easing_bonus = np.where(t2y_6m < -2.0, 25,
                   np.where(t2y_6m < -1.5, 15,
                   np.where(t2y_6m < -1.0, 10, 0)))
    score = pd.Series(
        np.where(rate_easing,
                 score * 0.7 + pd.Series(easing_bonus, index=m.index) * 0.3,
                 score),
        index=m.index
    )

    score = score.clip(-100, 100)

    # ── FIX 2: Signal smoothing (3-month rolling average) ────────────────
    # This prevents a single bad month from triggering a flip
    smoothed = score.rolling(window=3, min_periods=1).mean()

    # ── FIX 3: Minimum regime duration (2 months) ─────────────────────────
    # Classify on smoothed score first
    raw_regime = pd.Series("Risk-Off", index=smoothed.index)
    raw_regime[smoothed > 0] = "Risk-On"

    # Then enforce minimum duration
    final_regime = raw_regime.copy()
    current      = raw_regime.iloc[0]
    duration     = 1
    MIN_DURATION = 2   # months before allowed to flip

    for i in range(1, len(raw_regime)):
        proposed = raw_regime.iloc[i]
        if proposed != current:
            if duration >= MIN_DURATION:
                current  = proposed
                duration = 1
            else:
                # Not enough time in current regime — stay
                duration += 1
        else:
            duration += 1
        final_regime.iloc[i] = current

    return smoothed, final_regime, shock_series


# ─────────────────────────────────────────────────────────────────────────────
# FETCH DATA
# ─────────────────────────────────────────────────────────────────────────────

pb = st.progress(0, text="Fetching FRED data...")
monthly, fred_failed = fetch_fred(TODAY, fred_key)

pb.progress(60, text="Fetching market data...")
yf_data, yf_failed = fetch_market(TODAY)

pb.progress(90, text="Calculating regime scores with v3 fixes...")

for name, series in yf_data.items():
    if series is not None and not series.empty:
        series.index = pd.to_datetime(series.index).tz_localize(None)
        monthly[name] = series.resample("ME").last().reindex(monthly.index).ffill()

# Compute raw scores
raw, inf_score, ew, cf, rc, lq = compute_raw_score(monthly)

# Apply 3 fixes
smoothed, regime, shock = apply_fixes(raw, monthly)

pb.progress(100, text="Done!")
pb.empty()

# Align S&P 500
sp_daily = yf_data.get("sp500", pd.Series(dtype=float))
if sp_daily is None or sp_daily.empty:
    st.error("Could not fetch S&P 500. Please try again.")
    st.stop()

sp_daily.index = pd.to_datetime(sp_daily.index).tz_localize(None)
sp_monthly     = sp_daily.resample("ME").last()

combined = pd.DataFrame({
    "sp500":   sp_monthly,
    "raw":     raw,
    "smooth":  smoothed,
    "regime":  regime,
    "ew":      ew,
    "cf":      cf,
    "rc":      rc,
    "lq":      lq,
    "shock":   shock,
    "infl":    inf_score,
}).dropna(subset=["sp500", "smooth"])

if combined.empty:
    st.error("No overlapping data. Please try again.")
    st.stop()

start_date   = combined.index[0]
sp_aligned   = sp_daily[sp_daily.index >= start_date].dropna()
daily_regime = regime.reindex(sp_aligned.index, method="ffill").ffill()

# ─────────────────────────────────────────────────────────────────────────────
# FIXES EXPLANATION
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="sec-label">Three Targeted Fixes Applied</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="fix-grid">'

    '<div class="fix-card">'
    '<div class="fix-title">Fix 1 — Rate Shock Detector</div>'
    '<div class="fix-desc">If 2Y Treasury rises >1.25% in 6 months OR Fed funds '
    'rises >1% in 6 months, a strong negative penalty overrides the score. '
    'Magnitude scales with shock size. Catches 2022 (2Y rose 3%+ in 6 months starting late 2021). '
    'Also adds recovery bonus when rates fall rapidly.</div>'
    '</div>'

    '<div class="fix-card">'
    '<div class="fix-title">Fix 2 — Signal Smoothing</div>'
    '<div class="fix-desc">3-month rolling average applied to raw score before '
    'regime classification. Prevents a single bad data month from triggering a flip. '
    'Eliminates the COVID whipsaw where the market crashed and recovered in 6 weeks '
    '— too fast for a monthly macro model to react cleanly.</div>'
    '</div>'

    '<div class="fix-card">'
    '<div class="fix-title">Fix 3 — Minimum Regime Duration</div>'
    '<div class="fix-desc">Once the regime flips (Risk-On → Risk-Off or vice versa), '
    'it must remain in the new regime for at least 2 months before being allowed to '
    'flip back. This enforces conviction — the model only acts on sustained signals, '
    'not momentary crosses.</div>'
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

# Bear + bull market verdicts
events = {
    "Dot-com 2000-02":     ("2000-03", "2002-10", "bear"),
    "GFC 2007-09":         ("2007-10", "2009-03", "bear"),
    "COVID crash 2020":    ("2020-02", "2020-04", "bear"),
    "COVID recovery 2020": ("2020-05", "2021-12", "bull"),
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
            pct_c   = off_p
            want    = "Risk-Off during crash"
            color   = "#00D4AA" if off_p >= 60 else ("#f59e0b" if off_p >= 40 else "#FF4757")
            verdict = "✓ Avoided"  if off_p >= 60 else ("~ Partial" if off_p >= 40 else "✗ Missed")
        else:
            pct_c   = on_p
            want    = "Risk-On during bull"
            color   = "#00D4AA" if on_p >= 60 else ("#f59e0b" if on_p >= 40 else "#FF4757")
            verdict = "✓ Captured" if on_p >= 60 else ("~ Partial" if on_p >= 40 else "✗ Missed")

        tc = "#FF4757" if kind == "bear" else "#00D4AA"
        rows += (
            '<tr>'
            '<td><span style="color:' + tc + ';font-size:9px;margin-right:6px;">'
            + ("▼" if kind == "bear" else "▲") + '</span>' + name + '</td>'
            '<td style="color:#aaa;">' + want + '</td>'
            '<td style="color:' + tc + ';">' + str(round(pct_c)) + '%</td>'
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
# CHART
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="sec-label">S&P 500 with Macro Regime Overlay</div>', unsafe_allow_html=True)

fig = plt.figure(figsize=(18, 14), facecolor="#0A0A0F")
gs  = fig.add_gridspec(3, 1, height_ratios=[3, 1, 1], hspace=0.05)
ax1 = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1])
ax3 = fig.add_subplot(gs[2])

for ax in [ax1, ax2, ax3]:
    ax.set_facecolor("#0A0A0F")
    ax.tick_params(colors="#555", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#1a1a2e")

# Regime shading
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

# S&P price
ax1.plot(sp_aligned.index, sp_aligned.values, color="#E8E8E8", linewidth=1.1, zorder=5)
ax1.set_yscale("log")
ax1.set_ylabel("S&P 500 (log)", color="#666", fontsize=8, labelpad=8)
ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))
ax1.set_xlim(sp_aligned.index[0], sp_aligned.index[-1])
ax1.set_xticklabels([])
ax1.grid(axis="y", color="#111122", linewidth=0.5)
ax1.xaxis.set_major_locator(mdates.YearLocator(2))

# Event markers
for ds, lbl in [("2007-06","GFC lead-up"), ("2009-03","GFC bottom"),
                ("2020-02","COVID"), ("2021-11","2021 peak"),
                ("2022-10","2022 bottom")]:
    try:
        ed = pd.Timestamp(ds)
        if sp_aligned.index[0] <= ed <= sp_aligned.index[-1]:
            ax1.axvline(ed, color="#2a2a3a", linewidth=0.8, linestyle="--", zorder=3)
            ax1.text(ed, sp_aligned.max() * 0.88, lbl, color="#555", fontsize=6.5,
                     ha="center", bbox=dict(boxstyle="round,pad=0.2",
                     facecolor="#0A0A0F", edgecolor="#2a2a3a", alpha=0.9))
    except Exception:
        pass

p1 = mpatches.Patch(color="#00D4AA", alpha=0.5, label="Risk-On")
p2 = mpatches.Patch(color="#FF4757", alpha=0.5, label="Risk-Off")
ax1.legend(handles=[p1, p2], loc="upper left", framealpha=0, fontsize=8, labelcolor="#aaa")
ax1.set_title(
    "S&P 500 — Leading Indicator Framework v3  |  Rate Shock + Smoothing + Min Duration",
    color="#E8E8E8", fontsize=11, fontweight="bold", pad=10, loc="left"
)

# Smoothed Risk Appetite
sm = combined["smooth"]
ax2.fill_between(sm.index, sm, 0, where=sm >= 0, color="#00D4AA", alpha=0.3, interpolate=True)
ax2.fill_between(sm.index, sm, 0, where=sm < 0,  color="#FF4757", alpha=0.3, interpolate=True)
ax2.plot(sm.index, sm.values, color="#aaa", linewidth=0.9, zorder=5)
# Also plot raw as thin line for comparison
ax2.plot(combined["raw"].index, combined["raw"].values,
         color="#444", linewidth=0.6, linestyle="--", zorder=4, label="Raw (unsmoothed)")
ax2.axhline(0, color="#333", linewidth=0.8)
ax2.set_ylim(-100, 100)
ax2.set_xlim(sm.index[0], sm.index[-1])
ax2.set_ylabel("Risk Appetite\n(smoothed)", color="#666", fontsize=7, labelpad=6)
ax2.set_xticklabels([])
ax2.xaxis.set_major_locator(mdates.YearLocator(2))
ax2.grid(axis="y", color="#111122", linewidth=0.5)
ax2.legend(loc="upper right", framealpha=0, fontsize=6.5, labelcolor="#666")

# Rate shock overlay on ax2
shock_nonzero = combined["shock"] != 0
if shock_nonzero.any():
    ax2_twin = ax2.twinx()
    ax2_twin.set_facecolor("#0A0A0F")
    ax2_twin.fill_between(combined.index, combined["shock"], 0,
                          where=combined["shock"] < 0,
                          color="#FF6B35", alpha=0.15, interpolate=True)
    ax2_twin.set_ylim(-100, 100)
    ax2_twin.set_ylabel("Rate Shock", color="#FF6B35", fontsize=6.5)
    ax2_twin.tick_params(colors="#FF6B35", labelsize=6)
    for spine in ax2_twin.spines.values():
        spine.set_edgecolor("#1a1a2e")

# Layer sub-scores
for lname, lcolor, llabel in [
    ("ew", "#FF4757",  "Early Warn"),
    ("cf", "#f59e0b",  "Confirm"),
    ("rc", "#00D4AA",  "Recovery"),
    ("lq", "#5B8DEF",  "Liquidity"),
]:
    ax3.plot(combined.index, combined[lname].values,
             color=lcolor, linewidth=0.8, alpha=0.85, label=llabel)

ax3.axhline(0, color="#333", linewidth=0.8)
ax3.set_ylim(-100, 100)
ax3.set_xlim(combined.index[0], combined.index[-1])
ax3.set_ylabel("Layer Scores", color="#666", fontsize=7, labelpad=6)
ax3.xaxis.set_major_locator(mdates.YearLocator(2))
ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax3.grid(axis="y", color="#111122", linewidth=0.5)
ax3.legend(loc="upper left", framealpha=0, fontsize=7, labelcolor="#aaa", ncol=4)

fig.text(0.99, 0.005,
         "Generated " + TODAY + "  ·  FRED + yfinance  ·  v3: Rate Shock + Smoothing + Min Duration",
         ha="right", va="bottom", color="#333", fontsize=7, fontfamily="monospace")

plt.tight_layout(rect=[0, 0.01, 1, 1])
st.pyplot(fig, use_container_width=True)

# PDF
pdf_buf = io.BytesIO()
with PdfPages(pdf_buf) as pdf:
    pdf.savefig(fig, facecolor="#0A0A0F", dpi=180)
plt.close(fig)
pdf_buf.seek(0)

st.download_button(
    label="Download PDF",
    data=pdf_buf,
    file_name="regime_backtest_v3_" + TODAY + ".pdf",
    mime="application/pdf",
)
