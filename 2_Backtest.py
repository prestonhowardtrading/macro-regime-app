"""
Macro Regime — Business Cycle Framework
=========================================
Built from first principles based on:
  - Ben Cowen's ITC Business Cycle (S&P/unemployment²×rates×inflation/M2)
  - Luke Davis's Global Liquidity framework
  - The fundamental distinction between flash crashes and prolonged bears

THE KEY QUESTION: Is this a FLASH CRASH or a PROLONGED BEAR?

FLASH CRASH (buy the dip):
  COVID Mar 2020, April 2025
  - Exogenous shock (pandemic, geopolitical)
  - Oil FALLS or stays flat (deflationary, not inflationary)
  - Fed CAN respond immediately — no inflation preventing cuts
  - Business cycle NOT already late stage
  → Stay invested or add aggressively

PROLONGED BEAR (sell and stay out):
  2022, potentially 2026
  - Business cycle at late stage (overvaluation + sticky inflation)
  - Fed TIGHTENING or CONSTRAINED by oil/inflation
  - Oil RISING (inflation stays sticky = Fed can't cut)
  - Labor market weakening
  - Dollar strengthening
  → Sell near highs, stay out until macro clears

FIVE SCORED COMPONENTS (0-100, higher = more bearish):
  1. Business Cycle Position  25%  (employment, LEI, Sahm, ISM)
  2. Monetary Policy Regime   25%  (Fed direction, M2, real rates)
  3. Oil / Inflation Shock    20%  (oil ROC, CPI, breakevens)
  4. Dollar Strength          15%  (DXY vs 200DMA, trend)
  5. Equity Structure         15%  (vs 200DMA, death cross)

FLASH CRASH OVERRIDE:
  When score > 50 BUT oil is deflationary AND M2 growing AND Fed easing
  → Classify as "Flash Crash — Buy Dip" not "Prolonged Bear"
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

st.set_page_config(layout="wide", page_title="Macro Regime — Business Cycle")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500;600&display=swap');
html, body, [class*="st-"], [data-testid] {
    font-family: 'DM Sans', sans-serif !important;
    background-color: #0A0A0F; color: #E8E8E8;
}
[data-testid="stAppViewContainer"], [data-testid="stHeader"],
section[data-testid="stMain"] { background: #0A0A0F; }
.stat-grid { display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:24px; }
.stat-card { background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);
             border-radius:10px;padding:18px; }
.stat-lbl  { font-size:9px;letter-spacing:0.15em;color:#555;font-family:'DM Mono',monospace;
             margin-bottom:8px;text-transform:uppercase; }
.stat-val  { font-size:22px;font-weight:700;font-family:'DM Mono',monospace;line-height:1; }
.stat-sub  { font-size:10px;color:#666;margin-top:6px; }
.bear-table { width:100%;border-collapse:collapse; }
.bear-table th { font-size:9px;letter-spacing:0.15em;color:#555;text-transform:uppercase;
                 font-family:'DM Mono',monospace;padding:10px 14px;text-align:left;
                 border-bottom:1px solid rgba(255,255,255,0.06); }
.bear-table td { font-size:12px;color:#aaa;padding:10px 14px;
                 border-bottom:1px solid rgba(255,255,255,0.04);
                 font-family:'DM Mono',monospace; }
.sec-label { font-size:10px;letter-spacing:0.15em;color:#555;text-transform:uppercase;
             font-family:'DM Mono',monospace;margin-bottom:14px;margin-top:28px;
             padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,0.06); }
.component-bar { height:6px;border-radius:3px;margin-top:8px; }
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div style="font-size:10px;letter-spacing:0.2em;color:#555;text-transform:uppercase;'
    'font-family:\'DM Mono\',monospace;margin-bottom:4px;">Macro Regime Monitor</div>'
    '<h1 style="margin:0;font-size:28px;font-weight:600;letter-spacing:-0.02em;">'
    'Business Cycle Regime</h1>'
    '<p style="margin:6px 0 24px;font-size:12px;color:#555;">'
    'Flash Crash vs Prolonged Bear · '
    'Business Cycle · Monetary Policy · Oil/Inflation · Dollar · Equity Structure</p>',
    unsafe_allow_html=True
)

# ─────────────────────────────────────────────────────────────────────────────
# FRED KEY
# ─────────────────────────────────────────────────────────────────────────────

fred_key = st.secrets.get("FRED_API_KEY", None)
if not fred_key:
    fred_key = st.text_input("Enter your FRED API Key", type="password")
if not fred_key:
    st.markdown(
        '<div style="padding:20px;border-radius:12px;background:rgba(255,255,255,0.02);'
        'border:1px dashed rgba(255,255,255,0.08);text-align:center;color:#555;">'
        'Enter your FRED API key above.</div>', unsafe_allow_html=True)
    st.stop()

FETCH_START   = "2015-01-01"
DISPLAY_START = "2019-01-01"
END           = date.today().strftime("%Y-%m-%d")
TODAY         = str(date.today())

FRED_SERIES = {
    # Business Cycle
    "payems":     "PAYEMS",       # Nonfarm payrolls
    "unrate":     "UNRATE",       # Unemployment rate
    "icsa":       "ICSA",         # Initial jobless claims
    "lei":        "USSLIND",      # Conference Board LEI
    "ism_mfg":    "NAPM",         # ISM Manufacturing PMI
    # Monetary Policy
    "effr":       "FEDFUNDS",     # Fed funds rate
    "m2":         "M2SL",         # M2 money supply
    "tips10y":    "DFII10",       # 10Y real yield (TIPS)
    "t10y2y":     "T10Y2Y",       # Yield curve
    "t2y":        "DGS2",         # 2Y Treasury
    # Oil / Inflation
    "oil":        "DCOILWTICO",   # WTI crude oil
    "cpi":        "CPIAUCSL",     # CPI
    "core_pce":   "PCEPILFE",     # Core PCE
    "breakeven5y":"T5YIE",        # 5Y inflation breakeven
    "ppi":        "PPIACO",       # PPI
    # Dollar
    "dxy":        "DTWEXBGS",     # Trade-weighted dollar
    # Credit (for flash crash detection)
    "hy_spread":  "BAMLH0A0HYM2", # HY spread
    # Liquidity
    "walcl":      "WALCL",        # Fed balance sheet
    "ecb_assets": "ECBASSETSW",   # ECB balance sheet
    "boj_assets": "JPNASSETS",    # BOJ balance sheet
}


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_all(today_str, api_key):
    from fredapi import Fred
    fred   = Fred(api_key=api_key)
    frames = {}
    failed = []
    for name, sid in FRED_SERIES.items():
        try:
            s = fred.get_series(sid, observation_start=FETCH_START, observation_end=END)
            s.index = pd.to_datetime(s.index).tz_localize(None)
            frames[name] = s
        except Exception:
            failed.append(name)
    df = pd.DataFrame(frames)
    df.index = pd.to_datetime(df.index)
    return df.resample("ME").last().ffill().bfill(), failed


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_sp500(today_str):
    import yfinance as yf
    for _ in range(3):
        try:
            raw = yf.download("^GSPC", start=FETCH_START, end=END,
                              progress=False, auto_adjust=True)
            if raw.empty:
                continue
            s = raw["Close"].iloc[:, 0] if isinstance(raw.columns, pd.MultiIndex) \
                else raw["Close"]
            s = s.squeeze().dropna()
            s.index = pd.to_datetime(s.index)
            if hasattr(s.index, "tz") and s.index.tz:
                s.index = s.index.tz_localize(None)
            if not s.empty:
                return s
        except Exception:
            pass
    return pd.Series(dtype=float)


# ─────────────────────────────────────────────────────────────────────────────
# FIVE COMPONENT SCORES  (0 = bullish, 100 = bearish)
# ─────────────────────────────────────────────────────────────────────────────

def score_business_cycle(m):
    """
    How late are we in the business cycle?
    Cowen: "In late cycle, oil spiking = beginning of the end"
    Signals: employment trend, LEI, ISM, jobless claims
    """
    s = pd.Series(50.0, index=m.index)  # neutral starting point

    # Employment level YoY — Cowen: "going negative = recession"
    if "payems" in m.columns:
        pay_yoy = m["payems"].pct_change(12) * 100
        s += np.where(pay_yoy > 2.5,  -20,   # strong job growth = early cycle
             np.where(pay_yoy > 1.5,  -10,
             np.where(pay_yoy > 0.5,    0,
             np.where(pay_yoy > 0.0,   10,   # barely positive = warning
             np.where(pay_yoy > -0.5,  20,   # near zero = late cycle
                                        35))))) # negative = recession

    # Unemployment rate direction (3M change)
    if "unrate" in m.columns:
        ur_3m = m["unrate"].diff(3)
        s += np.where(ur_3m < -0.3, -10,
             np.where(ur_3m < 0,     -5,
             np.where(ur_3m < 0.3,    5,
             np.where(ur_3m < 0.6,   12,
                                      20))))

    # LEI 6-month trend
    if "lei" in m.columns:
        lei_6m = m["lei"].pct_change(6) * 100
        s += np.where(lei_6m > 2,   -15,
             np.where(lei_6m > 0.5, -8,
             np.where(lei_6m > -0.5,  0,
             np.where(lei_6m > -2,   10,
                                      20))))

    # ISM Manufacturing
    if "ism_mfg" in m.columns:
        pmi    = m["ism_mfg"]
        pmi_3m = pmi.diff(3)
        s += np.where(pmi > 55,   -12,
             np.where(pmi > 52,    -6,
             np.where(pmi > 50,     0,
             np.where(pmi > 48,     6,
             np.where(pmi > 45,    12,
                                    20)))))
        s += np.where(pmi_3m < -3,  8,
             np.where(pmi_3m > 3,  -8, 0))

    # Jobless claims trend
    if "icsa" in m.columns:
        ic_13w = m["icsa"].pct_change(3) * 100
        s += np.where(ic_13w > 20,  15,
             np.where(ic_13w > 10,   8,
             np.where(ic_13w < -10, -8,
             np.where(ic_13w < -5,  -4, 0))))

    return s.clip(0, 100)


def score_monetary_regime(m):
    """
    Is the Fed tightening or easing? Can it ease?
    Key: M2 contraction = QT regime = bearish
    Real rates highly positive = very restrictive
    """
    s = pd.Series(50.0, index=m.index)

    # Fed Funds Rate direction — are they hiking or cutting?
    if "effr" in m.columns:
        effr      = m["effr"]
        effr_6m   = effr.diff(6)
        effr_12m  = effr.diff(12)
        # Hiking cycle = very bearish
        s += np.where(effr_6m > 2.0,   25,
             np.where(effr_6m > 1.0,   15,
             np.where(effr_6m > 0.25,   8,
             np.where(effr_6m < -1.0,  -20,
             np.where(effr_6m < -0.5,  -12,
             np.where(effr_6m < -0.25,  -6, 0))))))

    # M2 YoY — CRITICAL: negative M2 = QT regime
    if "m2" in m.columns:
        m2_yoy = m["m2"].pct_change(12) * 100
        m2_3m  = m["m2"].pct_change(3) * 100
        s += np.where(m2_yoy < -2,   25,   # 2022 = M2 went negative
             np.where(m2_yoy < -1,   15,
             np.where(m2_yoy < 0,     8,
             np.where(m2_yoy < 3,     0,
             np.where(m2_yoy < 7,    -8,
             np.where(m2_yoy < 12,  -15,
                                     -25)))))) # 2020 = M2 +25% = very bullish
        s += np.where(m2_3m < -1,   10,
             np.where(m2_3m < 0,     5,
             np.where(m2_3m > 2,    -8,
             np.where(m2_3m > 1,    -4, 0))))

    # Real 10Y yield (TIPS) — positive real rates = restrictive
    if "tips10y" in m.columns:
        tips = m["tips10y"]
        s += np.where(tips > 2.0,   20,
             np.where(tips > 1.0,   12,
             np.where(tips > 0.5,    6,
             np.where(tips > 0.0,    2,
             np.where(tips > -0.5,  -5,
             np.where(tips > -1.5, -12,
                                    -18))))))

    # 2Y yield vs Fed Funds — market pricing cuts or hikes?
    if "t2y" in m.columns and "effr" in m.columns:
        gap = m["t2y"] - m["effr"]
        # 2Y well below EFFR = cuts priced in = monetary easing coming
        s += np.where(gap < -1.5,  -15,
             np.where(gap < -0.75, -8,
             np.where(gap < 0,     -3,
             np.where(gap < 0.5,    3,
             np.where(gap < 1.5,    8,
                                    15)))))

    return s.clip(0, 100)


def score_oil_inflation(m, market_data):
    """
    Oil rate of change is THE key signal.
    Cowen: "Oil spiking in LATE cycle = beginning of the end"
    "In early cycle, oil up = demand = bullish. In late cycle = catastrophic"
    The FED CANNOT CUT when oil spikes = checkmate
    """
    s = pd.Series(50.0, index=m.index)

    # WTI Crude — RATE OF CHANGE is what matters
    oil_col = None
    for c in ["oil_yf", "oil"]:
        if c in m.columns and not m[c].isna().all():
            oil_col = c
            break

    if oil_col:
        oil    = m[oil_col]
        oil_1m = oil.pct_change(1) * 100   # monthly
        oil_3m = oil.pct_change(3) * 100   # 3-month
        oil_6m = oil.pct_change(6) * 100   # 6-month
        oil_vs_avg = oil / oil.rolling(12).mean()

        # 1M spike — "largest weekly spike since 1983" = catastrophic in late cycle
        s += np.where(oil_1m > 25,   30,
             np.where(oil_1m > 15,   18,
             np.where(oil_1m > 8,     8,
             np.where(oil_1m < -20,  -20,  # oil crashing = deflationary = bullish
             np.where(oil_1m < -10,  -12,
             np.where(oil_1m < -5,    -6, 0))))))

        # 3M trend
        s += np.where(oil_3m > 30,   25,
             np.where(oil_3m > 20,   15,
             np.where(oil_3m > 10,    8,
             np.where(oil_3m < -30,  -18,
             np.where(oil_3m < -20,  -12,
             np.where(oil_3m < -10,   -6, 0))))))

        # Level vs 12M average
        s += np.where(oil_vs_avg > 1.3,  15,
             np.where(oil_vs_avg > 1.1,   8,
             np.where(oil_vs_avg > 0.9,   0,
             np.where(oil_vs_avg > 0.7,   -8,
                                           -15))))

    # CPI YoY — sticky inflation = Fed constrained
    if "cpi" in m.columns:
        cpi_yoy = m["cpi"].pct_change(12) * 100
        cpi_3m  = m["cpi"].pct_change(3) * 100 * 4  # annualized
        s += np.where(cpi_yoy > 6,    20,
             np.where(cpi_yoy > 4,    12,
             np.where(cpi_yoy > 3,     5,
             np.where(cpi_yoy > 2,     0,
             np.where(cpi_yoy > 1.5,  -5,
                                       -10)))))
        # Acceleration
        s += np.where(cpi_3m > 5,   12,
             np.where(cpi_3m > 3,    6,
             np.where(cpi_3m < 1,   -6,
             np.where(cpi_3m < 0,  -10, 0))))

    # 5Y Breakeven inflation expectations
    if "breakeven5y" in m.columns:
        be    = m["breakeven5y"]
        be_3m = be.diff(3)
        s += np.where(be > 3.0,   15,
             np.where(be > 2.5,    8,
             np.where(be > 2.0,    0,
             np.where(be > 1.5,   -5,
                                   -10))))
        s += np.where(be_3m > 0.4,  10,
             np.where(be_3m > 0.2,   5,
             np.where(be_3m < -0.3,  -8,
             np.where(be_3m < -0.1,  -4, 0))))

    return s.clip(0, 100)


def score_dollar(m, market_data):
    """
    Dollar strength = global liquidity tightening.
    Luke: "Dollar strengthening = siphons global liquidity = bearish for risk"
    DXY above 200DMA = risk-off environment globally
    """
    s = pd.Series(50.0, index=m.index)

    dxy_col = "dxy" if ("dxy" in m.columns and not m["dxy"].isna().all()) else None
    if dxy_col is None:
        return s

    dxy      = m[dxy_col]
    dxy_3m   = dxy.pct_change(3) * 100
    dxy_6m   = dxy.pct_change(6) * 100
    dxy_200  = dxy.rolling(12).mean()  # 12M monthly ≈ 200DMA
    vs_200   = (dxy / dxy_200 - 1) * 100
    dxy_max  = dxy.rolling(6).max()

    # 3M trend — direction is primary
    s += np.where(dxy_3m > 5,    25,
         np.where(dxy_3m > 3,    15,
         np.where(dxy_3m > 1,     7,
         np.where(dxy_3m < -5,  -25,
         np.where(dxy_3m < -3,  -15,
         np.where(dxy_3m < -1,   -7, 0))))))

    # Position vs 200DMA
    s += np.where(vs_200 > 4,    15,
         np.where(vs_200 > 2,     8,
         np.where(vs_200 > 0,     3,
         np.where(vs_200 < -3,  -12,
         np.where(vs_200 < -1,   -6, 0)))))

    # Peak detection — dollar reversing from 6M high = bullish for risk
    turning = (dxy < dxy_max * 0.97).values
    s += pd.Series(np.where(turning, -10, 0), index=m.index)

    # GL: Fed + ECB + BOJ combined
    gl = pd.Series(0.0, index=m.index)
    n  = 0
    for col, threshold in [("walcl", 8), ("ecb_assets", 6)]:
        if col in m.columns and not m[col].isna().all():
            roc3 = m[col].pct_change(3) * 100
            roc1 = m[col].pct_change(1) * 100
            cqe  = (roc1 > threshold).values
            _g   = np.where(roc3 > 4,  -15, np.where(roc3 > 1,  -8,
                   np.where(roc3 > 0,   -3, np.where(roc3 > -2,  5,
                   np.where(roc3 > -5,  12,                       20)))))
            gl  += pd.Series(np.where(cqe, 0, _g), index=m.index)
            n   += 1
    if n > 0:
        # Use current GL (no shift — avoids trailing NaN bug)
        s += (gl / n).clip(-20, 20)

    return s.clip(0, 100)


def score_equity_structure(m):
    """
    Price vs 200DMA + death cross + distribution pattern.
    Luke: "Nothing good happens below the 50DMA"
    "When bull market support band is lost = regime shifts fast"
    Cowen: "S&P sideways 6 months at highs + divergence = topping pattern"
    """
    s = pd.Series(50.0, index=m.index)

    if "sp500" not in m.columns or m["sp500"].isna().all():
        return s

    sp    = m["sp500"]
    ma200 = sp.rolling(12).mean()   # 12M monthly ≈ 200DMA
    ma50  = sp.rolling(4).mean()    # 4M monthly ≈ 50DMA (approx)
    ma21w = sp.rolling(5).mean()    # 5M monthly ≈ 21W (bull market support band)

    # Position vs 200DMA
    vs200 = (sp / ma200 - 1) * 100
    s += np.where(vs200 > 12,  -20,
         np.where(vs200 > 6,   -12,
         np.where(vs200 > 2,    -5,
         np.where(vs200 > 0,     0,
         np.where(vs200 > -5,   12,
         np.where(vs200 > -10,  22,
                                 30))))))

    # Death cross: 50DMA below 200DMA
    cross = ((ma50 / ma200 - 1) * 100).values
    s += pd.Series(np.where(cross < -1,   18,
                   np.where(cross < 0,    8,
                   np.where(cross > 2,   -12,
                   np.where(cross > 0.5,  -5, 0)))), index=m.index)

    # Bull market support band (21W EMA proxy)
    vs_band = ((sp / ma21w - 1) * 100).values
    s += pd.Series(np.where(vs_band < -3,  15,
                   np.where(vs_band < 0,    5,
                   np.where(vs_band > 5,   -8,
                   np.where(vs_band > 0,   -3, 0)))), index=m.index)

    # 6-month momentum (distribution pattern = topping)
    sp_6m = (sp.pct_change(6) * 100).values
    s += pd.Series(np.where(sp_6m > 15,  -15,
                   np.where(sp_6m > 8,    -8,
                   np.where(sp_6m > 2,    -3,
                   np.where(sp_6m < -15,  15,
                   np.where(sp_6m < -8,    8,
                   np.where(sp_6m < -2,    3, 0)))))), index=m.index)

    return s.clip(0, 100)


def detect_flash_crash(m, bear_score):
    """
    Override: is this a flash crash (buy the dip) vs prolonged bear?

    Flash crash requires ALL of:
    1. HY spread SPIKE fast (>100bps 2M) — credit shock
    2. Oil is NOT causing it (oil flat or falling)
    3. M2 is growing (Fed can respond, not in QT)
    4. Bear score was LOW before the shock (<55)
    """
    if "hy_spread" not in m.columns:
        return pd.Series(False, index=m.index)

    hy     = m["hy_spread"]
    hy_2m  = hy.diff(2)

    # Credit spike
    credit_shock = hy_2m > 100

    # Oil NOT spiking (deflationary crash, not inflationary)
    oil_not_spiking = pd.Series(True, index=m.index)
    for c in ["oil_yf", "oil"]:
        if c in m.columns and not m[c].isna().all():
            oil_1m = m[c].pct_change(1) * 100
            oil_not_spiking = oil_1m < 15
            break

    # M2 growing (Fed has room to respond)
    m2_ok = pd.Series(True, index=m.index)
    if "m2" in m.columns:
        m2_yoy = m["m2"].pct_change(12) * 100
        m2_ok  = m2_yoy > 2

    # Bear score was low before shock (not already in late cycle bear)
    was_not_bear = bear_score.shift(2) < 58

    flash = credit_shock & oil_not_spiking & m2_ok & was_not_bear
    return flash.fillna(False)


def classify_regime(bear_score, flash_crash, min_months=2):
    """
    PROLONGED BEAR: bear_score > 58 AND NOT flash crash
    FLASH CRASH: credit shock but fundamentals okay
    RISK-ON: bear_score < 45
    CAUTION: bear_score 45-58
    """
    raw = pd.Series("Risk-On", index=bear_score.index)
    raw[bear_score > 45] = "Caution"
    raw[(bear_score > 58) & (~flash_crash)] = "Risk-Off"
    raw[(flash_crash)] = "Flash-Crash"

    # Minimum hold — don't whipsaw
    final   = raw.copy()
    current = raw.iloc[0]
    dur     = 1
    for i in range(1, len(raw)):
        p = raw.iloc[i]
        if p != current:
            # Flash crashes can flip immediately (fast)
            # Prolonged bears need 2M confirmation
            min_dur = 1 if ("Flash" in p or "Flash" in current) else min_months
            if dur >= min_dur:
                current = p
                dur = 1
            else:
                dur += 1
        else:
            dur += 1
        final.iloc[i] = current

    return final


# ─────────────────────────────────────────────────────────────────────────────
# FETCH + COMPUTE
# ─────────────────────────────────────────────────────────────────────────────

pb = st.progress(0, text="Fetching FRED data...")
monthly, failed = fetch_all(TODAY, fred_key)

pb.progress(55, text="Fetching S&P 500...")
sp_daily = fetch_sp500(TODAY)

pb.progress(85, text="Computing regime...")

if sp_daily.empty:
    st.error("Could not fetch S&P 500.")
    st.stop()

monthly["sp500"] = sp_daily.resample("ME").last().reindex(monthly.index).ffill()

# Score all five components
c1 = score_business_cycle(monthly)
c2 = score_monetary_regime(monthly)
c3 = score_oil_inflation(monthly, {})
c4 = score_dollar(monthly, {})
c5 = score_equity_structure(monthly)

# Weighted bear score (0-100)
bear_score = (c1*0.25 + c2*0.25 + c3*0.20 + c4*0.15 + c5*0.15).clip(0, 100)

# Flash crash detection
flash = detect_flash_crash(monthly, bear_score)

# Classify
regime = classify_regime(bear_score, flash, min_months=2)

pb.progress(100, text="Done!")
pb.empty()

# Display range
sp_disp    = sp_daily[sp_daily.index >= DISPLAY_START]
m_disp     = monthly[monthly.index >= DISPLAY_START]
reg_disp   = regime[regime.index >= DISPLAY_START]
bs_disp    = bear_score[bear_score.index >= DISPLAY_START]
c1d = c1[c1.index >= DISPLAY_START]
c2d = c2[c2.index >= DISPLAY_START]
c3d = c3[c3.index >= DISPLAY_START]
c4d = c4[c4.index >= DISPLAY_START]
c5d = c5[c5.index >= DISPLAY_START]

daily_regime = regime.reindex(sp_disp.index, method="ffill").ffill()

# ─────────────────────────────────────────────────────────────────────────────
# CURRENT STATUS
# ─────────────────────────────────────────────────────────────────────────────

cur_reg   = reg_disp.iloc[-1]
cur_score = round(float(bs_disp.iloc[-1]), 1)

regime_colors = {
    "Risk-On":    "#00D4AA",
    "Caution":    "#f59e0b",
    "Risk-Off":   "#FF4757",
    "Flash-Crash":"#a78bfa",
}
regime_labels = {
    "Risk-On":    "RISK-ON — Invest",
    "Caution":    "CAUTION — Defensive",
    "Risk-Off":   "RISK-OFF — Stay Out",
    "Flash-Crash":"FLASH CRASH — Buy Dip",
}
cur_color = regime_colors.get(cur_reg, "#E8E8E8")
cur_label = regime_labels.get(cur_reg, cur_reg)

st.markdown(
    '<div style="text-align:center;margin-bottom:28px;padding:24px;border-radius:14px;'
    'background:' + cur_color + '10;border:1px solid ' + cur_color + '33;">'
    '<div style="font-size:10px;letter-spacing:0.2em;color:#555;text-transform:uppercase;'
    'font-family:\'DM Mono\',monospace;margin-bottom:8px;">Current Macro Regime</div>'
    '<div style="font-size:32px;font-weight:700;color:' + cur_color + ';'
    'font-family:\'DM Mono\',monospace;letter-spacing:-0.02em;">' + cur_label + '</div>'
    '<div style="font-size:12px;color:#666;margin-top:8px;">'
    'Bear Score: ' + str(cur_score) + ' / 100  ·  '
    'Threshold: 45 = Caution, 58 = Risk-Off</div>'
    '</div>',
    unsafe_allow_html=True
)

# Component scores
def bar_color(score):
    if score < 35: return "#00D4AA"
    if score < 55: return "#f59e0b"
    return "#FF4757"

labels = ["Business Cycle", "Monetary Policy", "Oil / Inflation", "Dollar Strength", "Equity Structure"]
scores = [c1d.iloc[-1], c2d.iloc[-1], c3d.iloc[-1], c4d.iloc[-1], c5d.iloc[-1]]
weights = ["25%", "25%", "20%", "15%", "15%"]

st.markdown('<div class="sec-label">Component Scores (0 = Bullish, 100 = Bearish)</div>',
            unsafe_allow_html=True)

cards = ""
for lbl, sc, wt in zip(labels, scores, weights):
    sc   = round(float(sc), 0)
    bc   = bar_color(sc)
    desc = "Bullish" if sc < 35 else ("Neutral" if sc < 55 else "Bearish")
    cards += (
        '<div class="stat-card">'
        '<div class="stat-lbl">' + lbl + ' (' + wt + ')</div>'
        '<div class="stat-val" style="color:' + bc + ';">' + str(int(sc)) + '</div>'
        '<div class="stat-sub">' + desc + '</div>'
        '<div class="component-bar" style="background:' + bc + ';width:' + str(sc) + '%;opacity:0.6;"></div>'
        '</div>'
    )
st.markdown('<div class="stat-grid" style="grid-template-columns:repeat(5,1fr);">' + cards + '</div>',
            unsafe_allow_html=True)

# Accuracy table
events = {
    "Pre-COVID 2020":        ("2019-10", "2020-01", "bull",  "Risk-On"),
    "COVID crash":           ("2020-02", "2020-05", "flash", "Flash-Crash"),
    "COVID bull 2020-21":    ("2020-06", "2021-11", "bull",  "Risk-On"),
    "Bear 2022 (full)":      ("2022-01", "2022-10", "bear",  "Risk-Off"),
    "Recovery 2023":         ("2022-11", "2023-12", "bull",  "Risk-On"),
    "Bull 2024":             ("2024-01", "2024-12", "bull",  "Risk-On"),
    "April 2025 dip":        ("2025-03", "2025-06", "flash", "Flash-Crash"),
    "2026 current":          ("2026-01", END,       "bear",  "Risk-Off"),
}

st.markdown('<div class="sec-label">Historical Accuracy</div>', unsafe_allow_html=True)
rows = ""
for name, (bs, be, kind, want) in events.items():
    try:
        w = reg_disp.loc[bs:be]
        if len(w) < 1:
            continue
        # For flash crash periods, check how many months were Flash-Crash or Risk-On
        if kind == "flash":
            pct = (w.isin(["Flash-Crash", "Risk-On"])).mean() * 100
        elif kind == "bear":
            pct = (w == "Risk-Off").mean() * 100
        else:
            pct = (w.isin(["Risk-On", "Caution"])).mean() * 100

        color   = "#00D4AA" if pct >= 60 else ("#f59e0b" if pct >= 40 else "#FF4757")
        verdict = "✓" if pct >= 60 else ("~" if pct >= 40 else "✗")
        tc      = regime_colors.get(want, "#aaa")
        rows += (
            '<tr><td>' + name + '</td>'
            '<td style="color:' + tc + ';">' + want + '</td>'
            '<td style="color:' + tc + ';">' + str(round(pct)) + '%</td>'
            '<td style="color:' + color + ';font-weight:600;">' + verdict + '</td></tr>'
        )
    except Exception:
        pass

st.markdown(
    '<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);'
    'border-radius:12px;overflow:hidden;">'
    '<table class="bear-table"><thead><tr>'
    '<th>Period</th><th>Target</th><th>Correct %</th><th></th>'
    '</tr></thead><tbody>' + rows + '</tbody></table></div>',
    unsafe_allow_html=True
)

# ─────────────────────────────────────────────────────────────────────────────
# CHART
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="sec-label">S&P 500 — Regime Overlay (2019–Present)</div>',
            unsafe_allow_html=True)

fig = plt.figure(figsize=(18, 13), facecolor="#0A0A0F")
gs  = fig.add_gridspec(3, 1, height_ratios=[3, 1, 1], hspace=0.06)
ax1 = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1])
ax3 = fig.add_subplot(gs[2])

for ax in [ax1, ax2, ax3]:
    ax.set_facecolor("#0A0A0F")
    ax.tick_params(colors="#555", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#1a1a2e")

# Regime shading with 4 colors
color_map = {
    "Risk-On":    "#00D4AA",
    "Caution":    "#f59e0b",
    "Risk-Off":   "#FF4757",
    "Flash-Crash":"#a78bfa",
}
in_reg, span_start = None, None
for d, r in zip(daily_regime.index, daily_regime.values):
    if r != in_reg:
        if in_reg is not None:
            c = color_map.get(in_reg, "#00D4AA")
            ax1.axvspan(span_start, d, alpha=0.22, color=c, linewidth=0)
        in_reg, span_start = r, d
if in_reg:
    c = color_map.get(in_reg, "#00D4AA")
    ax1.axvspan(span_start, daily_regime.index[-1], alpha=0.22, color=c, linewidth=0)

ax1.plot(sp_disp.index, sp_disp.values, color="#E8E8E8", linewidth=1.2, zorder=5)
ma200_d = sp_disp.rolling(200).mean()
ma50_d  = sp_disp.rolling(50).mean()
ax1.plot(ma200_d.index, ma200_d.values, color="#f59e0b", linewidth=0.9,
         alpha=0.7, linestyle="--", zorder=4, label="200DMA")
ax1.plot(ma50_d.index,  ma50_d.values,  color="#5B8DEF", linewidth=0.7,
         alpha=0.6, zorder=4, label="50DMA")
ax1.set_yscale("log")
ax1.set_ylabel("S&P 500 (log)", color="#666", fontsize=8, labelpad=8)
ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))
ax1.set_xlim(sp_disp.index[0], sp_disp.index[-1])
ax1.set_xticklabels([])
ax1.grid(axis="y", color="#111122", linewidth=0.5)
ax1.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))

for ds, lbl in [("2020-02","COVID"), ("2022-01","2022 top"),
                ("2022-10","2022 low"), ("2025-02","Feb sell")]:
    try:
        ed = pd.Timestamp(ds)
        if sp_disp.index[0] <= ed <= sp_disp.index[-1]:
            ax1.axvline(ed, color="#2a2a3a", linewidth=0.8, linestyle="--", zorder=3)
            ax1.text(ed, sp_disp.max() * 0.88, lbl, color="#555", fontsize=7, ha="center",
                     bbox=dict(boxstyle="round,pad=0.2", facecolor="#0A0A0F",
                               edgecolor="#2a2a3a", alpha=0.9))
    except Exception:
        pass

patches = [mpatches.Patch(color=c, alpha=0.6, label=l)
           for l, c in color_map.items()]
p200 = plt.Line2D([0],[0], color="#f59e0b", linewidth=0.9, linestyle="--", label="200DMA")
patches.append(p200)
ax1.legend(handles=patches, loc="upper left", framealpha=0, fontsize=7.5, labelcolor="#aaa")
ax1.set_title(
    "S&P 500 — Business Cycle Regime  "
    "|  Flash Crash = Buy · Risk-Off = Stay Out · Risk-On = Invest",
    color="#E8E8E8", fontsize=11, fontweight="bold", pad=10, loc="left"
)

# Bear score
ax2.fill_between(bs_disp.index, bs_disp, 50,
                 where=bs_disp >= 50, color="#FF4757", alpha=0.35, interpolate=True)
ax2.fill_between(bs_disp.index, bs_disp, 50,
                 where=bs_disp < 50,  color="#00D4AA", alpha=0.35, interpolate=True)
ax2.plot(bs_disp.index, bs_disp.values, color="#ccc", linewidth=1.0, zorder=5)
ax2.axhline(50, color="#333",    linewidth=0.8)
ax2.axhline(45, color="#f59e0b", linewidth=0.5, linestyle=":", alpha=0.5)
ax2.axhline(58, color="#FF4757", linewidth=0.5, linestyle=":", alpha=0.5)
ax2.text(bs_disp.index[-1], 45, "  Caution", color="#f59e0b", fontsize=6, va="bottom")
ax2.text(bs_disp.index[-1], 58, "  Risk-Off", color="#FF4757", fontsize=6, va="bottom")
ax2.set_ylim(0, 100)
ax2.set_xlim(bs_disp.index[0], bs_disp.index[-1])
ax2.set_ylabel("Bear Score", color="#666", fontsize=7, labelpad=6)
ax2.set_xticklabels([])
ax2.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
ax2.grid(axis="y", color="#111122", linewidth=0.5)

# Five components
for series, color, label in [
    (c1d, "#00D4AA", "Business Cycle"),
    (c2d, "#5B8DEF", "Monetary Policy"),
    (c3d, "#FF6B35", "Oil/Inflation"),
    (c4d, "#f59e0b", "Dollar"),
    (c5d, "#FF4757", "Equity Structure"),
]:
    ax3.plot(series.index, series.values, color=color,
             linewidth=0.9, alpha=0.85, label=label)

ax3.axhline(50, color="#333", linewidth=0.8)
ax3.axhline(58, color="#FF4757", linewidth=0.4, linestyle=":", alpha=0.4)
ax3.set_ylim(0, 100)
ax3.set_xlim(c1d.index[0], c1d.index[-1])
ax3.set_ylabel("Components", color="#666", fontsize=7, labelpad=6)
ax3.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
ax3.grid(axis="y", color="#111122", linewidth=0.5)
ax3.legend(loc="upper left", framealpha=0, fontsize=7, labelcolor="#aaa", ncol=5)

fig.text(0.99, 0.005,
         "Generated " + TODAY + "  ·  FRED + yfinance  ·  Business Cycle Framework",
         ha="right", va="bottom", color="#333", fontsize=7, fontfamily="monospace")

plt.tight_layout(rect=[0, 0.01, 1, 1])
st.pyplot(fig, use_container_width=True)

pdf_buf = io.BytesIO()
with PdfPages(pdf_buf) as pdf:
    pdf.savefig(fig, facecolor="#0A0A0F", dpi=180)
plt.close(fig)
pdf_buf.seek(0)

st.download_button(
    label="Download PDF",
    data=pdf_buf,
    file_name="regime_business_cycle_" + TODAY + ".pdf",
    mime="application/pdf",
)
