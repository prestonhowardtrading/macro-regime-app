"""
Macro Regime Backtest — Clean Build v4
=======================================
Rebuilt from scratch based on Luke Davis framework diagnosis.

PROBLEMS WITH PREVIOUS VERSIONS:
  - Mode switching (crisis/normal/recovery) often failed to trigger
  - Too many signals canceling each other out → flat composite
  - Cache preventing START date change from taking effect
  - Government spending data (FGEXPND) is quarterly → NaN-heavy

DESIGN PRINCIPLES:
  1. Eight independent signals, each scored -100 to +100
  2. Simple weighted average — no mode switching
  3. Signals are ASYMMETRIC: bearish signals stronger when conditions extreme
  4. Oil/inflation signal added (Luke's transcript 2 explicitly calls this out)
  5. Focus 2019-present — START=2019 but fetch from 2016 for warmup
  6. Cache busted with new function names

WEIGHTS (from Luke's framework priority):
  Global Liquidity ROC:    22%  (primary driver)
  Dollar Direction:        20%  (key lever — weak = bullish)
  Rate Shock (2Y yield):   18%  (catches 2022 before credit blows)
  Credit Stress (HY):      16%  (crisis detector)
  Monetary Policy:         10%  (Fed tone)
  Equity Trend (price MA): 8%   (50/200 DMA — Luke's visual signal)
  Oil/Inflation Risk:      6%   (Luke transcript 2: oil → inflation → Fed can't cut)

REGIME: Risk-Off when composite < -12. Min 1-month hold (COVID fast).
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

st.set_page_config(layout="wide", page_title="Regime Backtest v4")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500;600&display=swap');
html, body, [class*="st-"], [data-testid] {
    font-family: 'DM Sans', sans-serif !important;
    background-color: #0A0A0F; color: #E8E8E8;
}
[data-testid="stAppViewContainer"], [data-testid="stHeader"],
section[data-testid="stMain"] { background: #0A0A0F; }
.stat-grid { display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:24px; }
.stat-card { background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:16px; }
.stat-lbl  { font-size:9px;letter-spacing:0.15em;color:#555;font-family:'DM Mono',monospace;margin-bottom:6px;text-transform:uppercase; }
.stat-val  { font-size:20px;font-weight:700;font-family:'DM Mono',monospace;line-height:1; }
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
    'Regime Backtest <span style="font-size:14px;color:#555;font-weight:400;">'
    'v4 — Clean Build</span></h1>'
    '<p style="margin:6px 0 24px;font-size:12px;color:#555;">'
    '2019–Present · GL + Dollar + Rate Shock + Credit + Monetary + Equity + Oil · '
    'No mode-switching · Simple weighted composite</p>',
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
        'Enter your FRED API key above.</div>', unsafe_allow_html=True
    )
    st.stop()

# Fetch from 2016 for MA warmup, display from 2019
FETCH_START  = "2016-01-01"
DISPLAY_START = "2019-01-01"
END   = date.today().strftime("%Y-%m-%d")
TODAY = str(date.today())

# ─────────────────────────────────────────────────────────────────────────────
# FRED SERIES — lean set, all monthly or convertible
# ─────────────────────────────────────────────────────────────────────────────

FRED_SERIES_V4 = {
    # Global Liquidity
    "walcl":       "WALCL",         # Fed BS (weekly → monthly)
    "ecb_assets":  "ECBASSETSW",    # ECB BS
    "boj_assets":  "JPNASSETS",     # BOJ BS
    "m2":          "M2SL",          # US M2
    "tga":         "WTREGEN",       # TGA
    "rrp":         "RRPONTSYD",     # Reverse repo
    # Dollar
    "dxy_proxy":   "DTWEXBGS",      # Trade-weighted USD (daily → monthly)
    # Rate shock / monetary
    "t2y":         "DGS2",          # 2Y Treasury (daily → monthly)
    "effr":        "FEDFUNDS",      # Fed funds rate
    "tips10y":     "DFII10",        # 10Y TIPS real yield
    "t10y2y":      "T10Y2Y",        # Yield curve
    "nfci":        "NFCI",          # Financial conditions index
    # Credit stress
    "hy_spread":   "BAMLH0A0HYM2",  # HY OAS spread (daily → monthly)
    "ig_spread":   "BAMLC0A0CM",    # IG OAS spread
    # Economic activity
    "ism_mfg":     "NAPM",          # ISM Manufacturing PMI
    "lei":         "USSLIND",       # Conference Board LEI
    "icsa":        "ICSA",          # Jobless claims (weekly → monthly)
    "unrate":      "UNRATE",        # Unemployment rate
    # Inflation
    "core_pce":    "PCEPILFE",      # Core PCE
    "breakeven5y": "T5YIE",         # 5Y breakeven inflation
    "cpi":         "CPIAUCSL",      # CPI
    # Oil (Luke explicitly mentions in transcript 2)
    "oil":         "DCOILWTICO",    # WTI crude oil price
}


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_v4(today_str, api_key):
    """Fresh fetch with new function name to bust old cache."""
    from fredapi import Fred
    fred   = Fred(api_key=api_key)
    frames = {}
    failed = []
    for name, sid in FRED_SERIES_V4.items():
        try:
            s = fred.get_series(sid, observation_start=FETCH_START,
                                observation_end=END)
            s.index = pd.to_datetime(s.index).tz_localize(None)
            frames[name] = s
        except Exception:
            failed.append(sid)
    df = pd.DataFrame(frames)
    df.index = pd.to_datetime(df.index)
    return df.resample("ME").last().ffill().bfill(), failed


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_market_v4(today_str):
    """Fresh fetch with new function name to bust old cache."""
    import yfinance as yf
    results = {}
    failed  = []
    tickers = {
        "sp500": "^GSPC",
        "dxy":   "DX-Y.NYB",
        "bcom":  "^BCOM",
        "oil_yf":"CL=F",     # WTI futures for oil momentum
    }
    for name, ticker in tickers.items():
        try:
            raw = yf.download(ticker, start=FETCH_START, end=END,
                              progress=False, auto_adjust=True)
            s = raw["Close"][ticker] if isinstance(raw.columns, pd.MultiIndex) \
                else raw["Close"]
            s = s.squeeze()
            s.index = pd.to_datetime(s.index).tz_localize(None)
            results[name] = s
        except Exception:
            failed.append(ticker)
    return results, failed


# ─────────────────────────────────────────────────────────────────────────────
# EIGHT CLEAN SCORING FUNCTIONS
# Each returns -100 to +100. No dependencies between them.
# ─────────────────────────────────────────────────────────────────────────────

def pct(s, n): return s.pct_change(n) * 100


def sig_global_liquidity(m):
    """
    Global Liquidity Rate of Change.
    Luke: "GL operates on 3-month lag to markets."
    "GL stalled → removed tailwind."
    "GL recovered Oct 2022 → drove markets higher."
    Combined Fed+ECB+BOJ+M2+TGA+RRP.
    """
    s = pd.Series(0.0, index=m.index)

    # Fed: 3M ROC. Crisis QE (1M >8%) = neutralized.
    fed_3m = pct(m["walcl"], 3)
    fed_1m = pct(m["walcl"], 1)
    crisis_qe = fed_1m > 8
    fed_score = np.where(fed_3m > 5, 40, np.where(fed_3m > 2.5, 25,
                np.where(fed_3m > 0.5, 10, np.where(fed_3m > -0.5, -5,
                np.where(fed_3m > -2.5, -25, np.where(fed_3m > -5, -40, -55))))))
    s += pd.Series(np.where(crisis_qe, 0, fed_score), index=m.index)

    # ECB
    if "ecb_assets" in m.columns and not m["ecb_assets"].isna().all():
        ecb_3m = pct(m["ecb_assets"], 3)
        ecb_1m = pct(m["ecb_assets"], 1)
        ecb_score = np.where(ecb_3m > 3, 20, np.where(ecb_3m > 1, 10,
                    np.where(ecb_3m > -1, -5, np.where(ecb_3m > -3, -15, -25))))
        s += pd.Series(np.where(ecb_1m > 6, 0, ecb_score), index=m.index)

    # BOJ
    if "boj_assets" in m.columns and not m["boj_assets"].isna().all():
        boj_3m  = pct(m["boj_assets"], 3)
        boj_yoy = pct(m["boj_assets"], 12)
        s += np.where(boj_3m > 3, 15, np.where(boj_3m > 1, 7,
             np.where(boj_3m > -1, -4, np.where(boj_3m > -3, -12, -20))))
        # BOJ hiking = carry trade unwind = extra penalty
        s += np.where(boj_yoy < -5, -15, np.where(boj_yoy < -2, -8, 0))

    # M2
    m2_yoy = pct(m["m2"], 12)
    m2_3m  = pct(m["m2"], 3)
    s += np.where(m2_yoy > 10, 20, np.where(m2_yoy > 5, 12,
         np.where(m2_yoy > 2, 4, np.where(m2_yoy > -1, -5,
         np.where(m2_yoy > -4, -15, -25)))))
    s += np.where(m2_3m > 1.5, 8, np.where(m2_3m > 0, 3,
         np.where(m2_3m < -1.5, -8, np.where(m2_3m < 0, -3, 0))))

    # TGA: drawdown = inject = bullish; refill = drain = bearish
    if "tga" in m.columns:
        tga_3m = m["tga"].diff(3)
        s += np.where(tga_3m < -200, 20, np.where(tga_3m < -100, 11,
             np.where(tga_3m < -50, 5, np.where(tga_3m > 200, -20,
             np.where(tga_3m > 100, -11, np.where(tga_3m > 50, -5, 0))))))

    # RRP: declining = releasing liquidity = bullish
    if "rrp" in m.columns:
        rrp_3m = m["rrp"].diff(3).fillna(0)
        s += np.where(rrp_3m < -300, 18, np.where(rrp_3m < -100, 9,
             np.where(rrp_3m < -50, 4, np.where(rrp_3m > 300, -15,
             np.where(rrp_3m > 100, -8, np.where(rrp_3m > 50, -3, 0))))))

    return s.clip(-100, 100)


def sig_dollar(m, market_data):
    """
    Dollar direction.
    Luke: "Weak dollar = risk assets surge substantially."
    "Strong dollar = siphons global liquidity."
    Uses true DXY + 200DMA position (Luke's visual signal from transcript 2).
    """
    s = pd.Series(0.0, index=m.index)
    dxy_col = "dxy" if ("dxy" in m.columns and not m["dxy"].isna().all()) else "dxy_proxy"
    if dxy_col not in m.columns:
        return s

    dxy    = m[dxy_col]
    dxy_3m = pct(dxy, 3)
    dxy_6m = pct(dxy, 6)
    dxy_1m = pct(dxy, 1)

    # 3M direction — primary
    s += np.where(dxy_3m < -5,   40, np.where(dxy_3m < -3,  28,
         np.where(dxy_3m < -1,   16, np.where(dxy_3m < -0.3, 6,
         np.where(dxy_3m <  0.3,  0, np.where(dxy_3m <  1.5,-14,
         np.where(dxy_3m <  3,  -26, np.where(dxy_3m <  5,  -36,
                                               -45))))))))

    # 6M trend confirms
    s += np.where(dxy_6m < -8,  18, np.where(dxy_6m < -4,  10,
         np.where(dxy_6m < -1,   4, np.where(dxy_6m < 1,    0,
         np.where(dxy_6m < 4,  -10, np.where(dxy_6m < 8,  -16, -22))))))

    # 200DMA position (Luke transcript 2: "dollar back above 200DMA = bearish")
    dxy_200ma = dxy.rolling(12).mean()  # 12-month ≈ 200-day on monthly data
    pct_vs_200 = (dxy / dxy_200ma - 1) * 100
    s += np.where(pct_vs_200 < -3,  14, np.where(pct_vs_200 < -1,  7,
         np.where(pct_vs_200 < 0,    2, np.where(pct_vs_200 < 1,   -5,
         np.where(pct_vs_200 < 3,  -12, np.where(pct_vs_200 < 5, -18, -24))))))

    # Peak detection: DXY turning down from 6M high = recovery signal
    dxy_6m_max = dxy.rolling(6).max()
    turning     = dxy < dxy_6m_max * 0.97
    at_peak     = dxy >= dxy_6m_max * 0.99
    s += pd.Series(np.where(turning,   12,
                   np.where(at_peak,   -8, 0)), index=m.index)

    return s.clip(-100, 100)


def sig_rate_shock(m):
    """
    Rate shock: 2Y yield 4M change.
    KEY insight: fires BEFORE credit blows up.
    Jan 2022 → 2Y surged 70bps in 4M BEFORE HY spreads widened.
    This is the earliest 2022 warning signal.
    """
    s = pd.Series(0.0, index=m.index)
    if "t2y" not in m.columns:
        return s

    t2y     = m["t2y"]
    t2y_4m  = t2y.diff(4)   # 4-month change
    t2y_2m  = t2y.diff(2)   # 2-month acceleration

    # 4M rate shock — primary
    s += np.where(t2y_4m > 1.75, -60, np.where(t2y_4m > 1.25, -45,
         np.where(t2y_4m > 0.75, -30, np.where(t2y_4m > 0.45, -18,
         np.where(t2y_4m > 0.15, -8,  np.where(t2y_4m < -1.25,  45,
         np.where(t2y_4m < -0.75, 30, np.where(t2y_4m < -0.35,  18,
         np.where(t2y_4m < -0.1,   8, 0)))))))))

    # 2M acceleration
    s += np.where(t2y_2m > 0.75, -22, np.where(t2y_2m > 0.4, -12,
         np.where(t2y_2m > 0.15, -5,  np.where(t2y_2m < -0.5,  20,
         np.where(t2y_2m < -0.25, 10, np.where(t2y_2m < -0.1,   5, 0))))))

    # Fed hike/cut pace
    effr_6m = m["effr"].diff(6)
    s += np.where(effr_6m > 2.5, -30, np.where(effr_6m > 1.5, -20,
         np.where(effr_6m > 0.75,-10, np.where(effr_6m < -1.0,  25,
         np.where(effr_6m < -0.5, 15, 0)))))

    return s.clip(-100, 100)


def sig_credit(m):
    """
    Credit stress: HY spread level + speed.
    Crisis detector — high HY = systemic risk.
    Also: rapidly tightening spreads = strong recovery signal.
    """
    s = pd.Series(0.0, index=m.index)
    if "hy_spread" not in m.columns:
        return s

    hy     = m["hy_spread"]
    hy_3m  = hy.diff(3)
    hy_max = hy.rolling(4).max()

    # Level
    s += np.where(hy < 275,  40, np.where(hy < 325,  28,
         np.where(hy < 375,  16, np.where(hy < 425,   6,
         np.where(hy < 475,  -2, np.where(hy < 550,  -14,
         np.where(hy < 650,  -30, np.where(hy < 800, -50,
         np.where(hy < 1100,-65,                      -75)))))))))

    # Speed
    s += np.where(hy_3m > 300, -40, np.where(hy_3m > 200, -28,
         np.where(hy_3m > 100, -16, np.where(hy_3m > 50,   -8,
         np.where(hy_3m < -200,  30, np.where(hy_3m < -100, 18,
         np.where(hy_3m < -50,    9, 0)))))))

    # Peak turning
    turn = hy < hy_max * 0.88
    high = hy > 450
    peak = hy >= hy_max * 0.98
    s += pd.Series(np.where(turn & high,  22,
                   np.where(turn & ~high, 10,
                   np.where(peak & high, -10, 0))), index=m.index)

    # IG confirms
    if "ig_spread" in m.columns:
        ig    = m["ig_spread"]
        ig_3m = ig.diff(3)
        s += np.where(ig < 0.8,  14, np.where(ig < 1.0,  7,
             np.where(ig < 1.3,   2, np.where(ig < 1.8,  -8,
             np.where(ig < 2.5, -18, np.where(ig < 3.5, -30, -45))))))
        s += np.where(ig_3m < -0.4, 10, np.where(ig_3m > 0.5, -12, 0))

    return s.clip(-100, 100)


def sig_monetary(m):
    """
    Monetary policy tone.
    Note: rate cuts DURING credit crisis (HY>600) neutralized —
    they are reactive not bullish.
    """
    s = pd.Series(0.0, index=m.index)

    effr_3m = m["effr"].diff(3)
    hy_in_crisis = m["hy_spread"] > 600 if "hy_spread" in m.columns \
                   else pd.Series(False, index=m.index)

    raw_effr = np.where(effr_3m < -0.5,  28, np.where(effr_3m < -0.25, 16,
               np.where(effr_3m <  0,     5, np.where(effr_3m <  0.25, -8,
               np.where(effr_3m <  0.5, -20, np.where(effr_3m <  1.0, -32,
                                                                        -42))))))
    s += pd.Series(np.where(hy_in_crisis & (effr_3m < 0), 0, raw_effr), index=m.index)

    # TIPS real rate level
    if "tips10y" in m.columns:
        tips    = m["tips10y"]
        tips_3m = tips.diff(3)
        s += np.where(tips < -1.5, 16, np.where(tips < -0.5,  9,
             np.where(tips <  0,    3, np.where(tips <  0.5,  -5,
             np.where(tips <  1.5,-12,                         -20)))))
        s += np.where(tips_3m < -0.5,  10, np.where(tips_3m > 0.5, -12, 0))

    # Yield curve
    if "t10y2y" in m.columns:
        yc = m["t10y2y"]
        s += np.where(yc > 1.5,  12, np.where(yc > 0.5,  6,
             np.where(yc > 0,     2, np.where(yc > -0.5, -5,
             np.where(yc > -1.0,-12,                      -18)))))

    # NFCI
    if "nfci" in m.columns:
        nf = m["nfci"]
        s += np.where(nf < -0.5,  10, np.where(nf < -0.1,  5,
             np.where(nf <  0.2,   0, np.where(nf <  0.5,  -7, -14))))

    return s.clip(-100, 100)


def sig_equity_trend(m, market_data):
    """
    Equity price trend — Luke's visual signals from transcript 2:
    "50DMA = primary signal. Nothing good happens below 50DMA."
    "Bull market support band (20/21 week EMA) = regime signal."
    Using price vs 12M and 6M MAs as monthly proxies.
    """
    s = pd.Series(0.0, index=m.index)

    sp = m.get("sp500", None)
    if sp is None or sp.isna().all():
        # Try to build from ISM + LEI
        if "ism_mfg" in m.columns:
            pmi = m["ism_mfg"]
            s += np.where(pmi > 55, 20, np.where(pmi > 52, 12,
                 np.where(pmi > 50,  4, np.where(pmi > 48, -8,
                 np.where(pmi > 45,-18,                    -30)))))
        lei_6m = pct(m["lei"], 6)
        s += np.where(lei_6m > 2, 15, np.where(lei_6m > 0.5,  8,
             np.where(lei_6m > -0.5, 0, np.where(lei_6m > -2,-10, -18))))
        return s.clip(-100, 100)

    ma12 = sp.rolling(12).mean()  # ≈ 200DMA
    ma6  = sp.rolling(6).mean()   # ≈ 50DMA
    ma3  = sp.rolling(3).mean()

    # Price vs 12M MA (200DMA proxy)
    vs_200 = (sp / ma12 - 1) * 100
    s += np.where(vs_200 > 12,  25, np.where(vs_200 > 6,  16,
         np.where(vs_200 > 2,    8, np.where(vs_200 > 0,   2,
         np.where(vs_200 > -5, -10, np.where(vs_200 > -12,-22,
                                              -35))))))

    # 6M momentum (price trend direction)
    sp_6m = pct(sp, 6)
    s += np.where(sp_6m > 15,  18, np.where(sp_6m > 8,  10,
         np.where(sp_6m > 2,    4, np.where(sp_6m > -5,  -6,
         np.where(sp_6m > -15,-15,                        -25)))))

    # 50DMA vs 200DMA (golden/death cross)
    cross = (ma6 / ma12 - 1) * 100
    s += np.where(cross > 3,  14, np.where(cross > 1,  7,
         np.where(cross > 0,   2, np.where(cross < -2,-14,
         np.where(cross < -1,  -7, 0)))))

    return s.clip(-100, 100)


def sig_oil_inflation(m, market_data):
    """
    Oil/Inflation risk signal.
    From Luke transcript 2: "If oil stays elevated it's inflationary.
    When you have inflation back in the mix, it complicates what the
    central banks can do in terms of lowering interest rates."
    "Oil is the wild card right now."

    High oil + rising inflation = Fed can't cut = bearish for risk assets.
    Low oil + falling inflation = Fed can cut = bullish.
    """
    s = pd.Series(0.0, index=m.index)

    # Oil price momentum
    oil_col = None
    if "oil_yf" in m.columns and not m["oil_yf"].isna().all():
        oil_col = "oil_yf"
    elif "oil" in m.columns and not m["oil"].isna().all():
        oil_col = "oil"

    if oil_col:
        oil    = m[oil_col]
        oil_3m = pct(oil, 3)
        oil_6m = pct(oil, 6)
        oil_lvl = oil / oil.rolling(12).mean()  # vs 12M avg

        # Rapid oil surge = inflation risk = bearish
        s += np.where(oil_3m > 25, -30, np.where(oil_3m > 15, -18,
             np.where(oil_3m > 8,  -8,  np.where(oil_3m < -20,  18,
             np.where(oil_3m < -10,  9, np.where(oil_3m < -5,   4, 0))))))

        # Oil level vs average (persistent high = sustained inflation)
        s += np.where(oil_lvl > 1.3, -20, np.where(oil_lvl > 1.15, -10,
             np.where(oil_lvl > 0.85,  0, np.where(oil_lvl > 0.70,   8,
                                                                      15))))

    # Inflation expectations — when rising = Fed constrained
    if "breakeven5y" in m.columns:
        be     = m["breakeven5y"]
        be_3m  = be.diff(3)
        be_lvl = be
        # Level: above 2.5% = hot = headwind
        s += np.where(be_lvl > 3.0, -20, np.where(be_lvl > 2.5, -10,
             np.where(be_lvl > 2.0,   0, np.where(be_lvl > 1.5,   5,
                                                                   10))))
        # Direction
        s += np.where(be_3m > 0.4, -15, np.where(be_3m > 0.15, -7,
             np.where(be_3m < -0.3,  12, np.where(be_3m < -0.1,  5, 0))))

    # Core PCE vs target
    if "core_pce" in m.columns:
        pce = pct(m["core_pce"], 12)
        s += np.where(pce > 4.0, -18, np.where(pce > 3.0, -10,
             np.where(pce > 2.5,  -4, np.where(pce > 1.5,   4,
                                                              8))))

    return s.clip(-100, 100)


# ─────────────────────────────────────────────────────────────────────────────
# COMPOSITE + REGIME
# ─────────────────────────────────────────────────────────────────────────────

def build_v4(gl, dxy, rs, cr, mp, eq, oi):
    """
    Weights: GL 22%, DXY 20%, RS 18%, CR 16%, MP 10%, EQ 8%, OI 6%
    No mode switching. Simple weighted sum.
    """
    return (
        gl  * 0.22 +
        dxy * 0.20 +
        rs  * 0.18 +
        cr  * 0.16 +
        mp  * 0.10 +
        eq  * 0.08 +
        oi  * 0.06
    ).clip(-100, 100)


def classify_v4(composite, hy_series, threshold=-12):
    """
    Risk-Off when 2-month smoothed composite < threshold.
    1-month minimum hold when HY > 600 (crisis = fast flip).
    2-month minimum hold otherwise.
    """
    smoothed = composite.rolling(2, min_periods=1).mean()
    raw      = pd.Series("Risk-On", index=smoothed.index)
    raw[smoothed < threshold] = "Risk-Off"

    hy      = hy_series.reindex(smoothed.index).ffill()
    final   = raw.copy()
    current = raw.iloc[0]
    dur     = 1

    for i in range(1, len(raw)):
        proposed = raw.iloc[i]
        min_dur  = 1 if hy.iloc[i] > 600 else 2
        if proposed != current:
            if dur >= min_dur:
                current = proposed
                dur     = 1
            else:
                dur += 1
        else:
            dur += 1
        final.iloc[i] = current

    return final, smoothed


# ─────────────────────────────────────────────────────────────────────────────
# FETCH + COMPUTE
# ─────────────────────────────────────────────────────────────────────────────

pb = st.progress(0, text="Fetching FRED data (fresh cache)...")
monthly, fred_failed = fetch_v4(TODAY, fred_key)

pb.progress(55, text="Fetching market data (fresh cache)...")
market_data, yf_failed = fetch_market_v4(TODAY)

pb.progress(82, text="Merging and computing scores...")

# Merge market data into monthly
for name, series in market_data.items():
    if series is not None and not series.empty:
        series.index = pd.to_datetime(series.index).tz_localize(None)
        monthly[name] = series.resample("ME").last().reindex(monthly.index).ffill()

# Score
gl_s = sig_global_liquidity(monthly)
dx_s = sig_dollar(monthly, market_data)
rs_s = sig_rate_shock(monthly)
cr_s = sig_credit(monthly)
mp_s = sig_monetary(monthly)
eq_s = sig_equity_trend(monthly, market_data)
oi_s = sig_oil_inflation(monthly, market_data)

# GL shifted forward 2 months (leads markets per Luke)
gl_led = gl_s.shift(-2)

composite = build_v4(gl_led, dx_s, rs_s, cr_s, mp_s, eq_s, oi_s)

hy_series = monthly.get("hy_spread", pd.Series(400, index=monthly.index))
regime, smoothed = classify_v4(composite, hy_series)

pb.progress(100, text="Done!")
pb.empty()

# Align to S&P 500 — restrict to DISPLAY_START
sp_daily = market_data.get("sp500", pd.Series(dtype=float))
if sp_daily is None or sp_daily.empty:
    st.error("Could not fetch S&P 500.")
    st.stop()

sp_daily.index = pd.to_datetime(sp_daily.index).tz_localize(None)
# Restrict display to 2019+
sp_daily_disp = sp_daily[sp_daily.index >= DISPLAY_START]
sp_monthly    = sp_daily.resample("ME").last()

combined = pd.DataFrame({
    "sp500":   sp_monthly,
    "smooth":  smoothed,
    "gl":      gl_led,
    "dxy":     dx_s,
    "rs":      rs_s,
    "cr":      cr_s,
    "mp":      mp_s,
    "eq":      eq_s,
    "oi":      oi_s,
    "hy":      hy_series,
    "regime":  regime,
}).dropna(subset=["sp500", "smooth"])

# Restrict display
combined_disp = combined[combined.index >= DISPLAY_START]

if combined_disp.empty:
    st.error("No data after 2019.")
    st.stop()

daily_regime_full = regime.reindex(sp_daily_disp.index, method="ffill").ffill()

# ─────────────────────────────────────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────────────────────────────────────

on_pct      = (combined_disp["regime"] == "Risk-On").mean() * 100
off_pct     = 100 - on_pct
transitions = int((combined_disp["regime"] != combined_disp["regime"].shift()).sum() - 1)
date_range  = (combined_disp.index[0].strftime("%b %Y") + " — " +
               combined_disp.index[-1].strftime("%b %Y"))
current_reg = combined_disp["regime"].iloc[-1]
cur_color   = "#00D4AA" if current_reg == "Risk-On" else "#FF4757"
cur_comp    = round(combined_disp["smooth"].iloc[-1], 1)

st.markdown('<div class="sec-label">Regime Statistics — 2019 to Present</div>',
            unsafe_allow_html=True)
st.markdown(
    '<div class="stat-grid">'
    '<div class="stat-card"><div class="stat-lbl">Period</div>'
    '<div class="stat-val" style="font-size:11px;color:#aaa;">' + date_range + '</div></div>'
    '<div class="stat-card"><div class="stat-lbl">Current Regime</div>'
    '<div class="stat-val" style="color:' + cur_color + ';font-size:14px;">'
    + current_reg.upper() + '</div></div>'
    '<div class="stat-card"><div class="stat-lbl">Composite Score</div>'
    '<div class="stat-val" style="color:' + cur_color + ';">'
    + ('+' if cur_comp > 0 else '') + str(cur_comp) + '</div></div>'
    '<div class="stat-card"><div class="stat-lbl">Risk-On %</div>'
    '<div class="stat-val" style="color:#00D4AA;">' + str(round(on_pct)) + '%</div></div>'
    '<div class="stat-card"><div class="stat-lbl">Regime Flips</div>'
    '<div class="stat-val" style="color:#E8E8E8;">' + str(transitions) + '</div></div>'
    '</div>',
    unsafe_allow_html=True
)

events = {
    "COVID crash":           ("2020-02", "2020-05", "bear"),
    "COVID-QE bull":         ("2020-05", "2021-12", "bull"),
    "Bear 2022 full":        ("2022-01", "2022-10", "bear"),
    "Bull 2023-2024":        ("2022-10", "2024-12", "bull"),
    "Feb-Apr 2025 crash":    ("2025-01", "2025-04", "bear"),
    "Recovery 2025+":        ("2025-05", END,       "bull"),
}

st.markdown('<div class="sec-label">Accuracy by Key Period</div>', unsafe_allow_html=True)
rows = ""
for name, (bs, be, kind) in events.items():
    try:
        w = combined_disp.loc[bs:be, "regime"]
        if len(w) < 1:
            continue
        off_p = (w == "Risk-Off").mean() * 100
        on_p  = 100 - off_p
        if kind == "bear":
            pct_c   = off_p
            want    = "Risk-Off"
            color   = "#00D4AA" if off_p >= 55 else ("#f59e0b" if off_p >= 35 else "#FF4757")
            verdict = "✓ Avoided"  if off_p >= 55 else ("~ Partial" if off_p >= 35 else "✗ Missed")
        else:
            pct_c   = on_p
            want    = "Risk-On"
            color   = "#00D4AA" if on_p >= 65 else ("#f59e0b" if on_p >= 45 else "#FF4757")
            verdict = "✓ Captured" if on_p >= 65 else ("~ Partial" if on_p >= 45 else "✗ Missed")
        tc = "#FF4757" if kind == "bear" else "#00D4AA"
        rows += (
            '<tr><td><span style="color:' + tc + ';margin-right:6px;">'
            + ("▼" if kind == "bear" else "▲") + '</span>' + name + '</td>'
            '<td style="color:#aaa;">' + want + '</td>'
            '<td style="color:' + tc + ';">' + str(round(pct_c)) + '%</td>'
            '<td style="color:' + color + ';font-weight:600;">' + verdict + '</td></tr>'
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

st.markdown('<div class="sec-label">S&P 500 Regime Overlay — 2019 to Present</div>',
            unsafe_allow_html=True)

fig = plt.figure(figsize=(18, 13), facecolor="#0A0A0F")
gs  = fig.add_gridspec(3, 1, height_ratios=[3, 1, 1], hspace=0.05)
ax1 = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1])
ax3 = fig.add_subplot(gs[2])

for ax in [ax1, ax2, ax3]:
    ax.set_facecolor("#0A0A0F")
    ax.tick_params(colors="#555", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#1a1a2e")

# Regime shading (daily, 2019+)
in_regime, span_start = None, None
for d, r in zip(daily_regime_full.index, daily_regime_full.values):
    if r != in_regime:
        if in_regime is not None:
            c = "#00D4AA" if in_regime == "Risk-On" else "#FF4757"
            ax1.axvspan(span_start, d, alpha=0.20, color=c, linewidth=0)
        in_regime, span_start = r, d
if in_regime:
    c = "#00D4AA" if in_regime == "Risk-On" else "#FF4757"
    ax1.axvspan(span_start, daily_regime_full.index[-1], alpha=0.20, color=c, linewidth=0)

ax1.plot(sp_daily_disp.index, sp_daily_disp.values,
         color="#E8E8E8", linewidth=1.2, zorder=5)

# 50DMA and 200DMA (Luke's key visual signals)
ma50  = sp_daily_disp.rolling(50).mean()
ma200 = sp_daily_disp.rolling(200).mean()
ax1.plot(ma50.index,  ma50.values,  color="#5B8DEF", linewidth=0.8,
         alpha=0.7, zorder=4, label="50DMA")
ax1.plot(ma200.index, ma200.values, color="#f59e0b", linewidth=0.8,
         alpha=0.7, linestyle="--", zorder=4, label="200DMA")

ax1.set_yscale("log")
ax1.set_ylabel("S&P 500 (log)", color="#666", fontsize=8, labelpad=8)
ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))
ax1.set_xlim(sp_daily_disp.index[0], sp_daily_disp.index[-1])
ax1.set_xticklabels([])
ax1.grid(axis="y", color="#111122", linewidth=0.5)
ax1.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
ax1.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))

for ds, lbl in [("2020-02","COVID"), ("2020-04","QE"),
                ("2022-01","2022 top"), ("2022-10","2022 low"),
                ("2025-02","Feb sell"), ("2025-04","Apr low")]:
    try:
        ed = pd.Timestamp(ds)
        if sp_daily_disp.index[0] <= ed <= sp_daily_disp.index[-1]:
            ax1.axvline(ed, color="#2a2a3a", linewidth=0.7, linestyle="--", zorder=3)
            ax1.text(ed, sp_daily_disp.max() * 0.9, lbl, color="#555",
                     fontsize=7, ha="center",
                     bbox=dict(boxstyle="round,pad=0.2", facecolor="#0A0A0F",
                               edgecolor="#2a2a3a", alpha=0.9))
    except Exception:
        pass

p1 = mpatches.Patch(color="#00D4AA", alpha=0.5, label="Risk-On")
p2 = mpatches.Patch(color="#FF4757", alpha=0.5, label="Risk-Off")
p3 = plt.Line2D([0],[0], color="#5B8DEF", linewidth=0.8, label="50DMA")
p4 = plt.Line2D([0],[0], color="#f59e0b", linewidth=0.8, linestyle="--", label="200DMA")
ax1.legend(handles=[p1, p2, p3, p4], loc="upper left", framealpha=0,
           fontsize=7.5, labelcolor="#aaa")
ax1.set_title(
    "S&P 500 (2019–Present)  |  GL + Dollar + Rate Shock + Credit + Monetary + Equity + Oil",
    color="#E8E8E8", fontsize=11, fontweight="bold", pad=10, loc="left"
)

# Composite (2019+)
cd = combined_disp
sm = cd["smooth"]
ax2.fill_between(sm.index, sm, 0, where=sm >= 0, color="#00D4AA",
                 alpha=0.35, interpolate=True)
ax2.fill_between(sm.index, sm, 0, where=sm < 0,  color="#FF4757",
                 alpha=0.35, interpolate=True)
ax2.plot(sm.index, sm.values, color="#ccc", linewidth=1.0, zorder=5)
ax2.axhline(0,   color="#333", linewidth=0.8)
ax2.axhline(-12, color="#FF4757", linewidth=0.6, linestyle=":", alpha=0.6)
ax2.text(sm.index[-1], -12, "  -12 Risk-Off", color="#FF4757",
         fontsize=6.5, va="bottom", alpha=0.7)
ax2.set_ylim(-100, 100)
ax2.set_xlim(sm.index[0], sm.index[-1])
ax2.set_ylabel("Composite", color="#666", fontsize=7, labelpad=6)
ax2.set_xticklabels([])
ax2.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
ax2.grid(axis="y", color="#111122", linewidth=0.5)

# Seven component scores
comps = [
    ("gl",  "#00D4AA", "GL"),
    ("dxy", "#f59e0b", "Dollar"),
    ("rs",  "#FF6B35", "Rate Shock"),
    ("cr",  "#FF4757", "Credit"),
    ("mp",  "#5B8DEF", "Monetary"),
    ("eq",  "#a78bfa", "Equity"),
    ("oi",  "#888",    "Oil/Inflation"),
]
for col, color, label in comps:
    if col in cd.columns:
        ax3.plot(cd.index, cd[col].values,
                 color=color, linewidth=0.8, alpha=0.85, label=label)

ax3.axhline(0, color="#333", linewidth=0.8)
ax3.set_ylim(-100, 100)
ax3.set_xlim(cd.index[0], cd.index[-1])
ax3.set_ylabel("Components", color="#666", fontsize=7, labelpad=6)
ax3.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7]))
ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax3.grid(axis="y", color="#111122", linewidth=0.5)
ax3.legend(loc="upper left", framealpha=0, fontsize=6.5,
           labelcolor="#aaa", ncol=7)

fig.text(0.99, 0.005,
         "Generated " + TODAY + "  ·  FRED + yfinance  ·  Clean Build v4  ·  2019–Present",
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
    file_name="regime_v4_clean_" + TODAY + ".pdf",
    mime="application/pdf",
)
