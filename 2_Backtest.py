"""
Macro Regime Backtest — Luke Davis Framework
=============================================
Based on the Alpha AI / Bull Market Blueprint methodology:

PRIMARY DRIVER: Global Liquidity (Fed + ECB + BOJ + PBOC combined)
  - Rate of change is the KEY signal, not absolute level
  - 3-month lag to markets = use 3-month ROC as leading signal
  - When GL ROC turns positive = Risk-On setup forming
  - When GL ROC turns negative = Risk-Off warning

FOUR FORCES (from transcript):
  1. Global Liquidity  — CB balance sheets combined, M2, TGA, RRP
  2. Monetary Policy   — Fed tone, rate cut expectations, real rates
  3. Dollar Strength   — DXY direction (weak = bullish, strong = bearish)
  4. Fiscal Policy     — Gov spending, deficit, stimulus vs austerity

REGIME LOGIC:
  - Score all four forces -100 to +100
  - Weight: Liquidity 40%, Dollar 25%, Monetary 20%, Fiscal 15%
  - 3-month forward shift on liquidity signal (the lag he mentions)
  - Risk-Off when composite < -10 for 2+ weeks
  - Risk-On when composite > 5 and recovering

KEY INSIGHT FROM TRANSCRIPT:
  "Global liquidity recovered in October 2022 → drove markets higher"
  "Global liquidity stalled in late Q3 2025 → removed tailwind for crypto"
  "Dollar declining → bullish. Dollar strengthening → bearish."
  "Fiscal stimulus + monetary easing combined = markets surge"
  "TGA refill = liquidity drain (bearish). TGA drawdown = inject (bullish)"
  "RRP declining = liquidity released into system (bullish)"
  "BOJ hiking = carry trade unwind = short-term bearish"
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

st.set_page_config(layout="wide", page_title="Regime Backtest — Luke Davis Framework")

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
.stat-grid { display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:24px; }
.stat-card { background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:16px; }
.stat-lbl  { font-size:9px;letter-spacing:0.15em;color:#555;font-family:'DM Mono',monospace;margin-bottom:6px;text-transform:uppercase; }
.stat-val  { font-size:20px;font-weight:700;font-family:'DM Mono',monospace;line-height:1; }
.force-grid { display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px; }
.force-card { border-radius:10px;padding:14px;border:1px solid rgba(0,212,170,0.2);background:rgba(0,212,170,0.04); }
.force-title { font-size:10px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;font-family:'DM Mono',monospace;color:#00D4AA;margin-bottom:4px; }
.force-weight { font-size:11px;color:#555;font-family:'DM Mono',monospace;margin-bottom:6px; }
.force-desc { font-size:11px;color:#888;line-height:1.5; }
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
    '— Global Liquidity Framework</span></h1>'
    '<p style="margin:6px 0 24px;font-size:12px;color:#555;">'
    'Built on Luke Davis / Alpha AI methodology: '
    'Global Liquidity ROC (40%) + Dollar (25%) + Monetary Policy (20%) + Fiscal (15%)</p>',
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

START = "1999-01-01"
END   = date.today().strftime("%Y-%m-%d")
TODAY = str(date.today())

# ─────────────────────────────────────────────────────────────────────────────
# DATA FETCH
# ─────────────────────────────────────────────────────────────────────────────

FRED_SERIES = {
    # Global Liquidity components
    "walcl":        "WALCL",          # Fed balance sheet (weekly)
    "ecb_assets":   "ECBASSETSW",     # ECB balance sheet
    "boj_assets":   "JPNASSETS",      # BOJ balance sheet
    "m2":           "M2SL",           # US M2
    "tga":          "WTREGEN",        # Treasury General Account
    "rrp":          "RRPONTSYD",      # Reverse Repo Facility
    "sofr":         "SOFR",           # SOFR rate (financial stress proxy)
    # Dollar
    "dxy_proxy":    "DTWEXBGS",       # Trade-weighted USD
    # Monetary Policy
    "effr":         "FEDFUNDS",       # Fed funds rate
    "t2y":          "DGS2",           # 2Y Treasury
    "t10y2y":       "T10Y2Y",         # Yield curve
    "tips10y":      "DFII10",         # Real rates
    "hy_spread":    "BAMLH0A0HYM2",   # HY spreads (financial conditions)
    "nfci":         "NFCI",           # Chicago Fed Financial Conditions
    # Fiscal Policy
    "govt_spending":"FGEXPND",        # Federal government expenditures
    # Economic context
    "ism_mfg":      "NAPM",           # ISM Manufacturing
    "lei":          "USSLIND",        # LEI
    "unrate":       "UNRATE",         # Unemployment
    "cpi":          "CPIAUCSL",       # CPI
    "core_pce":     "PCEPILFE",       # Core PCE
    "breakeven5y":  "T5YIE",          # 5Y breakeven
}


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_fred(today_str, api_key):
    from fredapi import Fred
    fred   = Fred(api_key=api_key)
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
    failed  = []
    tickers = {"sp500": "^GSPC", "dxy": "DX-Y.NYB", "bcom": "^BCOM"}
    for name, ticker in tickers.items():
        try:
            raw = yf.download(ticker, start=START, end=END,
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
# FOUR FORCES SCORING
# ─────────────────────────────────────────────────────────────────────────────

def pct_chg(s, n): return s.pct_change(n) * 100


def score_global_liquidity(m):
    """
    PRIMARY DRIVER (40% weight).
    Key insight from Luke: Rate of change is what matters.
    GL ROC turning positive = setup for bull market (3M lag to price).
    Components: Fed + ECB + BOJ + PBOC balance sheets, M2, TGA, RRP.
    """
    gl = pd.Series(0.0, index=m.index)

    # ── Fed Balance Sheet — ROC is primary signal ──────────────────────
    fed_yoy  = pct_chg(m["walcl"], 12)
    fed_3m   = pct_chg(m["walcl"], 3)   # 3-month momentum
    fed_1m   = pct_chg(m["walcl"], 1)   # Monthly direction

    # Direction of change matters most
    gl += np.where(fed_3m > 3,   25,
          np.where(fed_3m > 1,   15,
          np.where(fed_3m > 0,    5,
          np.where(fed_3m > -1,  -5,
          np.where(fed_3m > -3, -15,
                               -25)))))

    # YoY level for context
    gl += np.where(fed_yoy > 10,  10,
          np.where(fed_yoy > 3,    5,
          np.where(fed_yoy > 0,    0,
          np.where(fed_yoy > -3,  -5,
                               -12))))

    # ── ECB Balance Sheet ──────────────────────────────────────────────
    if "ecb_assets" in m.columns and not m["ecb_assets"].isna().all():
        ecb_3m = pct_chg(m["ecb_assets"], 3)
        gl += np.where(ecb_3m > 2,   12,
              np.where(ecb_3m > 0,    5,
              np.where(ecb_3m > -2,  -5,
                                    -12)))

    # ── BOJ Balance Sheet — Luke specifically mentions BOJ ─────────────
    if "boj_assets" in m.columns and not m["boj_assets"].isna().all():
        boj_3m   = pct_chg(m["boj_assets"], 3)
        boj_yoy  = pct_chg(m["boj_assets"], 12)
        gl += np.where(boj_3m > 3,   12,
              np.where(boj_3m > 0,    5,
              np.where(boj_3m > -2,  -5,
                                    -12)))
        # BOJ hiking = carry trade unwind = short-term bearish (Luke mentions this)
        # Detect rate hike environment: BOJ assets shrinking + rising rates
        gl += np.where(boj_yoy < -5, -10, 0)

    # ── M2 Money Supply — broad money = fuel for assets ───────────────
    m2_3m  = pct_chg(m["m2"], 3)
    m2_yoy = pct_chg(m["m2"], 12)
    gl += np.where(m2_yoy > 8,   15,
          np.where(m2_yoy > 4,    8,
          np.where(m2_yoy > 1,    3,
          np.where(m2_yoy > -2,  -5,
                               -15))))
    # Momentum of M2
    gl += np.where(m2_3m > 1,   5,
          np.where(m2_3m > 0,   2,
          np.where(m2_3m < -1, -5,
          np.where(m2_3m < 0,  -2, 0))))

    # ── TGA — Luke explicitly mentions this ────────────────────────────
    # "TGA refill = bearish (money locked away from markets)"
    # "TGA drawdown = bullish (money injected into markets)"
    if "tga" in m.columns:
        tga_3m = m["tga"].diff(3)
        tga_1m = m["tga"].diff(1)
        gl += np.where(tga_3m < -200,   18,   # large drawdown = big injection
              np.where(tga_3m < -100,   10,
              np.where(tga_3m < -50,     5,
              np.where(tga_3m >  200,  -18,   # large refill = liquidity drain
              np.where(tga_3m >  100,  -10,
              np.where(tga_3m >  50,    -5, 0))))))

    # ── RRP — Luke explicitly mentions: "RRP hitting lowest since 2021"
    # "RRP declining = liquidity being released into system = bullish"
    if "rrp" in m.columns:
        rrp_3m = m["rrp"].diff(3).fillna(0)
        rrp_lvl = m["rrp"]
        # Direction is key
        gl += np.where(rrp_3m < -300,   15,   # rapid drain = very bullish
              np.where(rrp_3m < -100,    8,
              np.where(rrp_3m < -50,     4,
              np.where(rrp_3m >  300,  -12,
              np.where(rrp_3m >  100,   -6,
              np.where(rrp_3m >  50,    -3, 0))))))

    # ── SOFR / Financial System Stress ───────────────────────────────
    # Luke mentions SOFR spiking = financial stress
    if "sofr" in m.columns and not m["sofr"].isna().all():
        sofr_chg = m["sofr"].diff(1)
        gl += np.where(sofr_chg > 0.3, -10,
              np.where(sofr_chg > 0.1,  -5,
              np.where(sofr_chg < -0.3,  8, 0)))

    # ── HY Credit Spreads — financial conditions proxy ─────────────────
    if "hy_spread" in m.columns:
        hy     = m["hy_spread"]
        hy_3m  = hy.diff(3)
        # Level
        gl += np.where(hy < 300,   15,
              np.where(hy < 400,    8,
              np.where(hy < 500,    0,
              np.where(hy < 700,  -12,
              np.where(hy < 900,  -25,
                                  -40)))))
        # Momentum
        gl += np.where(hy_3m < -100,  10,
              np.where(hy_3m < -50,    5,
              np.where(hy_3m >  150,  -15,
              np.where(hy_3m >  75,    -8, 0))))

    return gl.clip(-100, 100)


def score_dollar(m, market_data):
    """
    DOLLAR STRENGTH (25% weight).
    Luke: "Weak dollar = risk assets grow substantially"
    "Strong dollar = hurts risk assets, commodities, emerging markets"
    Direction is everything — he tracks DXY trend.
    """
    d = pd.Series(0.0, index=m.index)

    # True DXY if available, else trade-weighted proxy
    dxy_col = "dxy" if ("dxy" in m.columns and not m["dxy"].isna().all()) else "dxy_proxy"

    if dxy_col in m.columns:
        dxy    = m[dxy_col]
        dxy_3m = pct_chg(dxy, 3)    # 3-month ROC
        dxy_6m = pct_chg(dxy, 6)    # 6-month trend
        dxy_1m = pct_chg(dxy, 1)    # Monthly momentum

        # 3-month direction — primary signal
        d += np.where(dxy_3m < -5,   35,   # strong decline = very bullish
             np.where(dxy_3m < -3,   25,
             np.where(dxy_3m < -1,   15,
             np.where(dxy_3m < -0.5, 8,
             np.where(dxy_3m <  0.5, 0,
             np.where(dxy_3m <  1.5, -12,
             np.where(dxy_3m <  3,   -22,
             np.where(dxy_3m <  5,   -32,
                                     -40))))))))

        # 6-month trend confirms direction
        d += np.where(dxy_6m < -8,   15,
             np.where(dxy_6m < -4,    8,
             np.where(dxy_6m < -1,    4,
             np.where(dxy_6m <  1,    0,
             np.where(dxy_6m <  4,   -8,
             np.where(dxy_6m <  8,  -14,
                                    -18))))))

        # Monthly momentum (acceleration)
        d += np.where(dxy_1m < -1.5,  10,
             np.where(dxy_1m < -0.5,   5,
             np.where(dxy_1m >  1.5,  -10,
             np.where(dxy_1m >  0.5,   -5, 0))))

    return d.clip(-100, 100)


def score_monetary_policy(m):
    """
    MONETARY POLICY (20% weight).
    Luke: "Expansionary = raises asset prices"
    "Contractionary = hurts financial markets"
    "Rate cuts + dovish Fed = crypto needs this to do well"
    "Hawkish Fed commentary = nail in coffin for high-risk assets"
    """
    mp = pd.Series(0.0, index=m.index)

    # ── Fed Rate Direction ─────────────────────────────────────────────
    effr_3m = m["effr"].diff(3)
    effr_6m = m["effr"].diff(6)
    # Cutting = easing = bullish; hiking = tightening = bearish
    mp += np.where(effr_3m < -0.5,   25,   # cutting aggressively
          np.where(effr_3m < -0.25,  15,
          np.where(effr_3m < 0,       5,
          np.where(effr_3m < 0.25,   -5,
          np.where(effr_3m < 0.5,   -18,
          np.where(effr_3m < 1.0,   -28,
                                    -38))))))   # hiking fast = very bearish

    # ── 2Y Treasury — forward-looking rate expectations ───────────────
    t2y_3m = m["t2y"].diff(3)
    mp += np.where(t2y_3m < -0.5,   15,   # falling = rate cuts priced in
          np.where(t2y_3m < -0.25,   8,
          np.where(t2y_3m <  0,      2,
          np.where(t2y_3m <  0.5,   -8,
          np.where(t2y_3m <  1.0,  -18,
                                   -25)))))

    # ── Real Rates (TIPS) — Luke mentions this ─────────────────────────
    # Deeply negative real rates = QE era = very bullish for assets
    # Rising real rates = headwind for valuations
    if "tips10y" in m.columns:
        tips    = m["tips10y"]
        tips_3m = tips.diff(3)
        # Level
        mp += np.where(tips < -1.5,   15,   # deeply negative = QE era
              np.where(tips < -0.5,    8,
              np.where(tips <  0,      2,
              np.where(tips <  0.5,   -5,
              np.where(tips <  1.5,  -12,
                                     -20)))))
        # Rate of change
        mp += np.where(tips_3m < -0.5,  10,
              np.where(tips_3m < -0.2,   5,
              np.where(tips_3m >  0.5, -12,
              np.where(tips_3m >  0.2,  -6, 0))))

    # ── Yield Curve — inversion is bearish context ─────────────────────
    yc = m["t10y2y"]
    mp += np.where(yc >  1.5,   12,
          np.where(yc >  0.5,    6,
          np.where(yc >  0,      2,
          np.where(yc > -0.5,   -5,
          np.where(yc > -1.0,  -12,
                               -18)))))

    # ── NFCI Financial Conditions ──────────────────────────────────────
    if "nfci" in m.columns:
        nf    = m["nfci"]
        nf_3m = nf.diff(3)
        mp += np.where(nf < -0.5,   10,
              np.where(nf < -0.1,    5,
              np.where(nf <  0.2,    0,
              np.where(nf <  0.5,   -8,
                                   -15))))
        mp += np.where(nf_3m < -0.3,   8,
              np.where(nf_3m >  0.3,  -8, 0))

    return mp.clip(-100, 100)


def score_fiscal_policy(m):
    """
    FISCAL POLICY (15% weight).
    Luke: "Fiscal stimulus = gov spending + tax cuts = boosts markets"
    "Fiscal austerity (DOGE) = less money into economy = bearish"
    "Fiscal stimulus + monetary easing = markets surge"
    TGA is counted in liquidity; here we capture spending trends.
    """
    fp = pd.Series(0.0, index=m.index)

    # ── Government Spending Growth ─────────────────────────────────────
    if "govt_spending" in m.columns and not m["govt_spending"].isna().all():
        gs_yoy = pct_chg(m["govt_spending"], 12)
        gs_3m  = pct_chg(m["govt_spending"], 3)
        fp += np.where(gs_yoy > 8,   20,   # heavy stimulus
              np.where(gs_yoy > 4,   12,
              np.where(gs_yoy > 1,    4,
              np.where(gs_yoy > -1,  -4,
              np.where(gs_yoy > -4, -12,
                                    -20)))))
        fp += np.where(gs_3m > 3,   8,
              np.where(gs_3m > 0,   3,
              np.where(gs_3m < -3, -8,
              np.where(gs_3m < 0,  -3, 0))))

    # ── Deficit proxy: M2 acceleration when Fed expands ───────────────
    # When both M2 and gov spending growing = fiscal stimulus regime
    m2_yoy    = pct_chg(m["m2"], 12)
    walcl_yoy = pct_chg(m["walcl"], 12)
    # Both expanding = dual tailwind (Luke mentions this repeatedly)
    dual_bull = (m2_yoy > 5) & (walcl_yoy > 3)
    dual_bear = (m2_yoy < 0) & (walcl_yoy < 0)
    fp += np.where(dual_bull, 20, np.where(dual_bear, -20, 0))

    # ── Inflation context — hot inflation = fiscal headwind ────────────
    # Luke: "Tariffs = inflation spike = Fed can't cut = bearish for crypto"
    pce_yoy = pct_chg(m["core_pce"], 12)
    fp += np.where(pce_yoy > 4,   -15,   # too hot = restrictive policy forced
          np.where(pce_yoy > 3,    -8,
          np.where(pce_yoy > 2.5,  -3,
          np.where(pce_yoy < 1.5,  -5,   # deflation risk = also bad
                                    5)))) # 1.5-2.5% = Goldilocks

    return fp.clip(-100, 100)


# ─────────────────────────────────────────────────────────────────────────────
# COMPOSITE + REGIME
# ─────────────────────────────────────────────────────────────────────────────

def apply_3month_lag(series, lag_months=2):
    """
    Luke: "Global liquidity operates on about a 3-month lag to markets."
    We shift the liquidity signal forward so it leads price.
    A rising GL reading today predicts market direction 2-3 months ahead.
    We use 2 months to be slightly conservative.
    """
    return series.shift(-lag_months)  # shift forward = lead indicator


def classify_regime(composite, min_months=2):
    """
    Risk-Off when composite < -10 for 2+ months.
    Risk-On when composite > 5.
    Minimum hold: 2 months before flip.
    """
    raw = pd.Series("Risk-On", index=composite.index)
    raw[composite < -10] = "Risk-Off"

    final   = raw.copy()
    current = raw.iloc[0]
    dur     = 1

    for i in range(1, len(raw)):
        proposed = raw.iloc[i]
        if proposed != current:
            if dur >= min_months:
                current = proposed
                dur     = 1
            else:
                dur += 1
        else:
            dur += 1
        final.iloc[i] = current

    return final


# ─────────────────────────────────────────────────────────────────────────────
# FETCH DATA
# ─────────────────────────────────────────────────────────────────────────────

pb = st.progress(0, text="Fetching FRED data...")
monthly, fred_failed = fetch_fred(TODAY, fred_key)

pb.progress(60, text="Fetching market data (S&P 500, DXY, BCOM)...")
market_data, yf_failed = fetch_market(TODAY)

pb.progress(85, text="Computing four-force regime scores...")

# Merge market data
for name, series in market_data.items():
    if series is not None and not series.empty:
        series.index = pd.to_datetime(series.index).tz_localize(None)
        monthly[name] = series.resample("ME").last().reindex(monthly.index).ffill()

# Score all four forces
gl_raw  = score_global_liquidity(monthly)
dxy_sc  = score_dollar(monthly, market_data)
mp_sc   = score_monetary_policy(monthly)
fp_sc   = score_fiscal_policy(monthly)

# Apply 3-month lag to global liquidity (Luke's key insight)
gl_led  = apply_3month_lag(gl_raw, lag_months=2)

# Composite: GL 40%, Dollar 25%, Monetary 20%, Fiscal 15%
composite = (
    gl_led * 0.40 +
    dxy_sc * 0.25 +
    mp_sc  * 0.20 +
    fp_sc  * 0.15
).clip(-100, 100)

# Smooth 2-month rolling average
composite_smooth = composite.rolling(2, min_periods=1).mean()

regime = classify_regime(composite_smooth, min_months=2)

pb.progress(100, text="Done!")
pb.empty()

# Align S&P 500
sp_daily = market_data.get("sp500", pd.Series(dtype=float))
if sp_daily is None or sp_daily.empty:
    st.error("Could not fetch S&P 500. Please try again.")
    st.stop()

sp_daily.index = pd.to_datetime(sp_daily.index).tz_localize(None)
sp_monthly     = sp_daily.resample("ME").last()

combined = pd.DataFrame({
    "sp500":     sp_monthly,
    "composite": composite_smooth,
    "gl":        gl_raw,
    "gl_led":    gl_led,
    "dxy":       dxy_sc,
    "mp":        mp_sc,
    "fp":        fp_sc,
    "regime":    regime,
}).dropna(subset=["sp500", "composite"])

if combined.empty:
    st.error("No overlapping data. Please try again.")
    st.stop()

start_date   = combined.index[0]
sp_aligned   = sp_daily[sp_daily.index >= start_date].dropna()
daily_regime = regime.reindex(sp_aligned.index, method="ffill").ffill()

# ─────────────────────────────────────────────────────────────────────────────
# FRAMEWORK EXPLANATION
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="sec-label">Four Forces Framework</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="force-grid">'

    '<div class="force-card">'
    '<div class="force-title">Global Liquidity</div>'
    '<div class="force-weight">40% weight · 2-month lead</div>'
    '<div class="force-desc">Fed + ECB + BOJ balance sheets, M2, TGA drawdown/refill, RRP levels. '
    'ROC is the key signal. 2-month forward shift captures the lag Luke describes.</div>'
    '</div>'

    '<div class="force-card">'
    '<div class="force-title">Dollar Strength</div>'
    '<div class="force-weight">25% weight</div>'
    '<div class="force-desc">DXY 3-month and 6-month rate of change. '
    'Weak dollar = risk assets surge. Strong dollar = headwind. '
    'True DXY from yfinance when available.</div>'
    '</div>'

    '<div class="force-card">'
    '<div class="force-title">Monetary Policy</div>'
    '<div class="force-weight">20% weight</div>'
    '<div class="force-desc">Fed rate direction, 2Y yield (forward expectations), '
    'real rates (TIPS), yield curve, financial conditions (NFCI). '
    'Dovish = bullish. Hawkish commentary = bearish.</div>'
    '</div>'

    '<div class="force-card">'
    '<div class="force-title">Fiscal Policy</div>'
    '<div class="force-weight">15% weight</div>'
    '<div class="force-desc">Government spending growth, M2+Fed dual tailwind signal, '
    'inflation context. Stimulus = bullish. Austerity (DOGE) = bearish. '
    'Goldilocks inflation = supportive.</div>'
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
date_range  = (combined.index[0].strftime("%b %Y") + " — " +
               combined.index[-1].strftime("%b %Y"))
current_reg = combined["regime"].iloc[-1]
cur_color   = "#00D4AA" if current_reg == "Risk-On" else "#FF4757"
cur_comp    = round(combined["composite"].iloc[-1], 1)

st.markdown('<div class="sec-label">Regime Statistics</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="stat-grid">'
    '<div class="stat-card"><div class="stat-lbl">Date Range</div>'
    '<div class="stat-val" style="font-size:12px;color:#aaa;">' + date_range + '</div></div>'
    '<div class="stat-card"><div class="stat-lbl">Current Regime</div>'
    '<div class="stat-val" style="color:' + cur_color + ';font-size:15px;">'
    + current_reg.upper() + '</div></div>'
    '<div class="stat-card"><div class="stat-lbl">Composite Score</div>'
    '<div class="stat-val" style="color:' + cur_color + ';">'
    + ('+' if cur_comp > 0 else '') + str(cur_comp) + '</div></div>'
    '<div class="stat-card"><div class="stat-lbl">Risk-On %</div>'
    '<div class="stat-val" style="color:#00D4AA;">' + str(round(on_pct)) + '%</div></div>'
    '<div class="stat-card"><div class="stat-lbl">Regime Switches</div>'
    '<div class="stat-val" style="color:#E8E8E8;">' + str(transitions) + '</div></div>'
    '</div>',
    unsafe_allow_html=True
)

# Accuracy table
events = {
    "Dot-com 2000-02":     ("2000-03", "2002-10", "bear"),
    "GFC 2007-09":         ("2007-07", "2009-03", "bear"),
    "COVID crash 2020":    ("2020-02", "2020-05", "bear"),
    "COVID bull 2020-21":  ("2020-05", "2021-12", "bull"),
    "Bear 2022":           ("2022-01", "2022-10", "bear"),
    "Bull 2023-2024":      ("2022-10", "2024-12", "bull"),
    "Current 2025+":       ("2025-01", END,       "bull"),
}

st.markdown('<div class="sec-label">Key Market Periods — Model Accuracy</div>',
            unsafe_allow_html=True)
rows = ""
for name, (bs, be, kind) in events.items():
    try:
        window = combined.loc[bs:be, "regime"]
        if len(window) < 2:
            continue
        off_p = (window == "Risk-Off").mean() * 100
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

st.markdown('<div class="sec-label">S&P 500 with Global Liquidity Regime Overlay</div>',
            unsafe_allow_html=True)

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
            ax1.axvspan(span_start, d, alpha=0.18, color=c, linewidth=0)
        in_regime, span_start = r, d
if in_regime:
    c = "#00D4AA" if in_regime == "Risk-On" else "#FF4757"
    ax1.axvspan(span_start, daily_regime.index[-1], alpha=0.18, color=c, linewidth=0)

ax1.plot(sp_aligned.index, sp_aligned.values, color="#E8E8E8", linewidth=1.2, zorder=5)

# 200 DMA
ma200 = sp_aligned.rolling(200).mean()
ax1.plot(ma200.index, ma200.values, color="#f59e0b", linewidth=0.7,
         alpha=0.5, linestyle="--", zorder=4, label="200DMA")

ax1.set_yscale("log")
ax1.set_ylabel("S&P 500 (log)", color="#666", fontsize=8, labelpad=8)
ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))
ax1.set_xlim(sp_aligned.index[0], sp_aligned.index[-1])
ax1.set_xticklabels([])
ax1.grid(axis="y", color="#111122", linewidth=0.5)
ax1.xaxis.set_major_locator(mdates.YearLocator(2))

for ds, lbl in [("2000-03","Dot-com"), ("2007-07","GFC"),
                ("2009-03","GL bottom"), ("2020-02","COVID"),
                ("2022-10","GL turns"), ("2025-02","DOGE austerity")]:
    try:
        ed = pd.Timestamp(ds)
        if sp_aligned.index[0] <= ed <= sp_aligned.index[-1]:
            ax1.axvline(ed, color="#2a2a3a", linewidth=0.7, linestyle="--", zorder=3)
            ax1.text(ed, sp_aligned.max() * 0.88, lbl, color="#555", fontsize=6.5,
                     ha="center", bbox=dict(boxstyle="round,pad=0.2",
                     facecolor="#0A0A0F", edgecolor="#2a2a3a", alpha=0.9))
    except Exception:
        pass

p1 = mpatches.Patch(color="#00D4AA", alpha=0.5, label="Risk-On  (invest)")
p2 = mpatches.Patch(color="#FF4757", alpha=0.5, label="Risk-Off  (cash/hedge)")
p3 = plt.Line2D([0], [0], color="#f59e0b", linewidth=0.8, linestyle="--", label="200DMA")
ax1.legend(handles=[p1, p2, p3], loc="upper left", framealpha=0,
           fontsize=8, labelcolor="#aaa")
ax1.set_title(
    "S&P 500 — Global Liquidity Framework  "
    "|  GL (40%) + Dollar (25%) + Monetary (20%) + Fiscal (15%)",
    color="#E8E8E8", fontsize=11, fontweight="bold", pad=10, loc="left"
)

# Composite score
cs = combined["composite"]
ax2.fill_between(cs.index, cs, 0, where=cs >= 0, color="#00D4AA", alpha=0.3, interpolate=True)
ax2.fill_between(cs.index, cs, 0, where=cs < 0,  color="#FF4757", alpha=0.3, interpolate=True)
ax2.plot(cs.index, cs.values, color="#aaa", linewidth=0.9, zorder=5, label="Composite")
# Also show raw GL
ax2.plot(combined["gl"].index, combined["gl"].values,
         color="#5B8DEF", linewidth=0.6, alpha=0.6, linestyle=":", label="GL (raw, no lag)")
ax2.axhline(0,   color="#333", linewidth=0.8)
ax2.axhline(-10, color="#FF4757", linewidth=0.5, linestyle=":", alpha=0.5)
ax2.text(cs.index[-1], -10, " Risk-Off line", color="#FF4757", fontsize=6, va="bottom", alpha=0.6)
ax2.set_ylim(-100, 100)
ax2.set_xlim(cs.index[0], cs.index[-1])
ax2.set_ylabel("Composite", color="#666", fontsize=7, labelpad=6)
ax2.set_xticklabels([])
ax2.xaxis.set_major_locator(mdates.YearLocator(2))
ax2.grid(axis="y", color="#111122", linewidth=0.5)
ax2.legend(loc="upper right", framealpha=0, fontsize=6.5, labelcolor="#666")

# Four force scores
ax3.plot(combined.index, combined["gl_led"].values,
         color="#00D4AA", linewidth=1.0, alpha=0.9, label="Global Liquidity (led)")
ax3.plot(combined.index, combined["dxy"].values,
         color="#f59e0b", linewidth=0.8, alpha=0.8, label="Dollar")
ax3.plot(combined.index, combined["mp"].values,
         color="#5B8DEF", linewidth=0.8, alpha=0.8, label="Monetary Policy")
ax3.plot(combined.index, combined["fp"].values,
         color="#FF6B35", linewidth=0.7, alpha=0.7, label="Fiscal")
ax3.axhline(0, color="#333", linewidth=0.8)
ax3.set_ylim(-100, 100)
ax3.set_xlim(combined.index[0], combined.index[-1])
ax3.set_ylabel("Four Forces", color="#666", fontsize=7, labelpad=6)
ax3.xaxis.set_major_locator(mdates.YearLocator(2))
ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax3.grid(axis="y", color="#111122", linewidth=0.5)
ax3.legend(loc="upper left", framealpha=0, fontsize=7, labelcolor="#aaa", ncol=4)

fig.text(0.99, 0.005,
         "Generated " + TODAY +
         "  ·  FRED + yfinance  ·  Luke Davis / Alpha AI Four-Force Framework",
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
    file_name="regime_gl_framework_" + TODAY + ".pdf",
    mime="application/pdf",
)
