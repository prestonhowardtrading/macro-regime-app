"""
Macro Regime Backtest — Multi-Frequency Model v4
=================================================
Architecture:
  FAST LAYER  (daily/weekly FRED data) — reacts within 1-2 weeks
  MACRO LAYER (monthly data)           — 20+ indicators, structural context
  MOMENTUM    (price-based)            — trend confirmation

Regime Logic:
  RISK-OFF if: fast_score < threshold AND macro_score < threshold
  RISK-ON  if: fast_score clear AND macro_score positive OR recovering
  Minimum hold: 3 weeks (weekly) before flip allowed
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
    'v4 — Multi-Frequency Model</span></h1>'
    '<p style="margin:6px 0 24px;font-size:12px;color:#555;">'
    'Weekly fast signals + 20+ monthly macro indicators + momentum overlay</p>',
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
# DATA FETCH — DAILY (for fast signals)
# ─────────────────────────────────────────────────────────────────────────────

DAILY_SERIES = {
    "t2y":       "DGS2",          # 2Y Treasury yield (daily)
    "t10y":      "DGS10",         # 10Y Treasury yield (daily)
    "t10y2y":    "T10Y2Y",        # 10Y-2Y spread (daily)
    "t10y3m":    "T10Y3M",        # 10Y-3M spread (daily)
    "tips10y":   "DFII10",        # 10Y TIPS real yield (daily)
    "hy_spread": "BAMLH0A0HYM2",  # HY OAS spread (daily)
    "ig_spread": "BAMLC0A0CM",    # IG OAS spread (daily)
    "icsa":      "ICSA",          # Initial jobless claims (weekly)
}

# ─────────────────────────────────────────────────────────────────────────────
# DATA FETCH — MONTHLY (for macro context)
# ─────────────────────────────────────────────────────────────────────────────

MONTHLY_SERIES = {
    # Central bank balance sheets
    "walcl":       "WALCL",         # Fed balance sheet
    "ecb_assets":  "ECBASSETSW",    # ECB balance sheet
    "boj_assets":  "JPNASSETS",     # BOJ balance sheet
    # Money supply
    "m2":          "M2SL",          # US M2
    # Treasury liquidity
    "rrp":         "RRPONTSYD",     # Reverse repo
    "tga":         "WTREGEN",       # TGA
    # Dollar
    "dxy_proxy":   "DTWEXBGS",      # Trade-weighted USD
    # Labor
    "unrate":      "UNRATE",        # Unemployment rate
    "wages":       "CES0500000003", # Average hourly earnings
    # Activity
    "ism_mfg":     "NAPM",          # ISM Manufacturing PMI
    "ism_svc":     "NMFSL",         # ISM Services PMI
    "retail":      "RSAFS",         # Retail sales
    "lei":         "USSLIND",       # Conference Board LEI
    "gdpc1":       "GDPC1",         # Real GDP (quarterly)
    # Inflation
    "cpi":         "CPIAUCSL",      # CPI
    "core_pce":    "PCEPILFE",      # Core PCE
    "ppi":         "PPIACO",        # PPI
    "breakeven5y": "T5YIE",         # 5Y breakeven inflation
    # Financial conditions
    "nfci":        "NFCI",          # Chicago Fed NFCI
    "lending_std": "DRTSCILM",      # Bank lending standards
    "effr":        "FEDFUNDS",      # Fed funds rate
}


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_all_data(today_str, api_key):
    from fredapi import Fred
    fred   = Fred(api_key=api_key)
    daily  = {}
    monthly = {}
    failed = []

    # Fetch daily series
    for name, sid in DAILY_SERIES.items():
        try:
            s = fred.get_series(sid, observation_start=START, observation_end=END)
            s.index = pd.to_datetime(s.index).tz_localize(None)
            daily[name] = s
        except Exception:
            failed.append(sid)

    # Fetch monthly series
    for name, sid in MONTHLY_SERIES.items():
        try:
            s = fred.get_series(sid, observation_start=START, observation_end=END)
            s.index = pd.to_datetime(s.index).tz_localize(None)
            monthly[name] = s
        except Exception:
            failed.append(sid)

    daily_df   = pd.DataFrame(daily).ffill().bfill()
    monthly_df = pd.DataFrame(monthly)
    monthly_df.index = pd.to_datetime(monthly_df.index)
    monthly_df = monthly_df.resample("ME").last().ffill().bfill()

    return daily_df, monthly_df, failed


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_market(today_str):
    import yfinance as yf
    results = {}
    failed  = []
    tickers = {
        "sp500": "^GSPC",
        "dxy":   "DX-Y.NYB",
        "bcom":  "^BCOM",
        "vix":   "^VIX",
    }
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
# FAST LAYER — scored on weekly resampled daily data
# Reacts within 1-2 weeks to market stress signals
# ─────────────────────────────────────────────────────────────────────────────

def compute_fast_score(daily_df, market_data):
    """
    Score: -100 to +100 on weekly basis.
    Negative = stress, Positive = clear.
    """
    # Resample to weekly
    w = daily_df.resample("W").last().ffill()

    # Add VIX if available
    if "vix" in market_data and not market_data["vix"].empty:
        vix = market_data["vix"].resample("W").last()
        w["vix"] = vix.reindex(w.index).ffill()

    score = pd.Series(0.0, index=w.index)

    # ── 1. 2Y Treasury rate of change (8-week) ───────────────────────────
    # This is the single best 2022 signal — fires FAST when Fed pivots hawkish
    if "t2y" in w.columns:
        t2y_8w = w["t2y"].diff(8)   # 8-week (2-month) change
        t2y_4w = w["t2y"].diff(4)   # 4-week change for acceleration

        score += np.where(t2y_8w > 1.5,  -40,   # massive rate shock
                 np.where(t2y_8w > 1.0,  -28,
                 np.where(t2y_8w > 0.5,  -14,
                 np.where(t2y_8w < -1.5,  35,   # massive easing = very bullish
                 np.where(t2y_8w < -1.0,  25,
                 np.where(t2y_8w < -0.5,  12,
                 np.where(t2y_8w < -0.2,   5, 0)))))))

    # ── 2. HY Credit spreads — level + speed ─────────────────────────────
    # Most reliable real-time stress indicator
    if "hy_spread" in w.columns:
        hy     = w["hy_spread"]
        hy_8w  = hy.diff(8)
        hy_4w  = hy.diff(4)

        # Level signal
        score += np.where(hy < 300,  25,   # very tight = very bullish
                 np.where(hy < 350,  18,
                 np.where(hy < 400,  10,
                 np.where(hy < 450,   4,
                 np.where(hy < 500,  -8,
                 np.where(hy < 600, -20,
                 np.where(hy < 800, -35,
                                    -50)))))))

        # Speed signal — rapid widening = crisis developing
        score += np.where(hy_8w >  200, -35,
                 np.where(hy_8w >  100, -20,
                 np.where(hy_8w >   50, -10,
                 np.where(hy_8w < -100,  20,   # rapid tightening = recovery
                 np.where(hy_8w <  -50,  12,
                 np.where(hy_8w <  -25,   6, 0))))))

    # ── 3. Yield curve — inversion is bearish but not instant ────────────
    if "t10y2y" in w.columns:
        yc = w["t10y2y"]
        score += np.where(yc >  1.0,  15,
                 np.where(yc >  0.5,   8,
                 np.where(yc >  0.0,   2,
                 np.where(yc > -0.3,  -8,
                 np.where(yc > -0.7, -18,
                                     -28)))))

    # ── 4. Real rates (TIPS) — rising real rates hurt valuations ─────────
    if "tips10y" in w.columns:
        tips    = w["tips10y"]
        tips_8w = tips.diff(8)

        # Level (very negative = liquidity flush, positive = headwind)
        score += np.where(tips < -1.0,  15,   # deeply negative = QE era
                 np.where(tips < -0.5,  10,
                 np.where(tips <  0.0,   4,
                 np.where(tips <  0.5,  -5,
                 np.where(tips <  1.0, -12,
                                       -20)))))

        # Rate of change
        score += np.where(tips_8w >  1.0, -20,
                 np.where(tips_8w >  0.5, -10,
                 np.where(tips_8w < -0.5,  12,
                 np.where(tips_8w < -1.0,  20, 0))))

    # ── 5. VIX — fear gauge ───────────────────────────────────────────────
    if "vix" in w.columns:
        vix = w["vix"].ffill()
        score += np.where(vix < 15,  15,
                 np.where(vix < 20,   8,
                 np.where(vix < 25,   2,
                 np.where(vix < 30,  -8,
                 np.where(vix < 40, -20,
                                    -35)))))

    # ── 6. IG spreads ─────────────────────────────────────────────────────
    if "ig_spread" in w.columns:
        ig    = w["ig_spread"]
        ig_8w = ig.diff(8)
        score += np.where(ig < 0.8,  12,
                 np.where(ig < 1.0,   6,
                 np.where(ig < 1.3,   0,
                 np.where(ig < 1.8,  -8,
                                    -18))))
        score += np.where(ig_8w >  0.4, -12,
                 np.where(ig_8w >  0.2,  -6,
                 np.where(ig_8w < -0.3,  10,
                 np.where(ig_8w < -0.15,  5, 0))))

    # ── 7. Jobless claims — labor stress ──────────────────────────────────
    if "icsa" in w.columns:
        ic    = w["icsa"]
        ic_4w = ic.pct_change(4) * 100
        score += np.where(ic_4w <  -10,  10,
                 np.where(ic_4w <   -5,   5,
                 np.where(ic_4w >   25,  -18,
                 np.where(ic_4w >   15,  -10,
                 np.where(ic_4w >    8,   -5, 0)))))

    return score.clip(-100, 100)


# ─────────────────────────────────────────────────────────────────────────────
# MACRO LAYER — monthly, 20+ indicators
# Structural regime context — slower but deeper
# ─────────────────────────────────────────────────────────────────────────────

def compute_macro_score(m, market_data):
    """
    Monthly macro score: -100 to +100.
    Covers liquidity, growth, inflation, credit cycle.
    """
    score = pd.Series(0.0, index=m.index)

    # Add market data
    if "dxy" in market_data and not market_data["dxy"].empty:
        dxy = market_data["dxy"].resample("ME").last()
        m["dxy"] = dxy.reindex(m.index).ffill()
    if "bcom" in market_data and not market_data["bcom"].empty:
        bcom = market_data["bcom"].resample("ME").last()
        m["bcom"] = bcom.reindex(m.index).ffill()

    def pct_chg(s, n): return s.pct_change(n) * 100

    # ── GLOBAL LIQUIDITY (most important for bull markets) ────────────────

    # Fed balance sheet — PACE matters
    # Slow expansion = accommodative (bullish)
    # Crisis-pace expansion = emergency (neutral initially)
    # Contraction = headwind (bearish)
    walcl_yoy = pct_chg(m["walcl"], 12)
    walcl_3m  = pct_chg(m["walcl"], 3)
    score += np.where((walcl_yoy > 3) & (walcl_yoy < 20),  18,
             np.where(walcl_yoy > 20,   8,   # crisis QE — helpful but signals emergency
             np.where(walcl_yoy < -3, -22,   # QT is a meaningful headwind
             np.where(walcl_yoy < 0,   -8, 0))))

    # ECB balance sheet
    if "ecb_assets" in m.columns and not m["ecb_assets"].isna().all():
        ecb_yoy = pct_chg(m["ecb_assets"], 12)
        score += np.where(ecb_yoy > 5,  10,
                 np.where(ecb_yoy > 0,   4,
                 np.where(ecb_yoy < -5, -10,
                 np.where(ecb_yoy < 0,   -4, 0))))

    # BOJ balance sheet
    if "boj_assets" in m.columns and not m["boj_assets"].isna().all():
        boj_yoy = pct_chg(m["boj_assets"], 12)
        score += np.where(boj_yoy > 8,  10,
                 np.where(boj_yoy > 2,   5,
                 np.where(boj_yoy < -3, -8,
                 np.where(boj_yoy < 0,  -3, 0))))

    # M2 money supply — expanding = more money chasing assets
    m2_yoy = pct_chg(m["m2"], 12)
    score += np.where(m2_yoy > 10,  15,   # rapid expansion = very bullish
             np.where(m2_yoy >  6,  10,
             np.where(m2_yoy >  3,   5,
             np.where(m2_yoy >  0,   0,
             np.where(m2_yoy > -3,  -8,
                                   -16)))))

    # TGA drawdown = liquidity injection
    if "tga" in m.columns:
        tga_3m = m["tga"].diff(3)
        score += np.where(tga_3m < -200,  12,
                 np.where(tga_3m < -100,   6,
                 np.where(tga_3m >  200,  -10,
                 np.where(tga_3m >  100,   -5, 0))))

    # RRP decline = liquidity released into system
    if "rrp" in m.columns:
        rrp_3m = m["rrp"].diff(3).fillna(0)
        score += np.where(rrp_3m < -200,  10,
                 np.where(rrp_3m < -100,   5,
                 np.where(rrp_3m >  200,  -8,
                 np.where(rrp_3m >  100,  -4, 0))))

    # Dollar — weak dollar = global liquidity, strong = tightening
    dxy_col = "dxy" if ("dxy" in m.columns and not m["dxy"].isna().all()) else "dxy_proxy"
    if dxy_col in m.columns:
        dc = pct_chg(m[dxy_col], 3)
        score += np.where(dc < -3,  14,
                 np.where(dc < -1,   7,
                 np.where(dc >  4, -16,
                 np.where(dc >  2,  -8, 0))))

    # ── GROWTH / ACTIVITY ─────────────────────────────────────────────────

    # ISM Manufacturing — above 50 = expanding
    if "ism_mfg" in m.columns:
        pmi = m["ism_mfg"]
        score += np.where(pmi > 55,  12,
                 np.where(pmi > 52,   7,
                 np.where(pmi > 50,   2,
                 np.where(pmi > 48,  -5,
                 np.where(pmi > 45, -12,
                                    -20)))))
        pmi_3m = pmi.diff(3)
        score += np.where(pmi_3m > 3,  6,
                 np.where(pmi_3m > 1,  3,
                 np.where(pmi_3m < -3, -6,
                 np.where(pmi_3m < -1, -3, 0))))

    # ISM Services
    if "ism_svc" in m.columns:
        svc = m["ism_svc"]
        score += np.where(svc > 55,  10,
                 np.where(svc > 52,   5,
                 np.where(svc > 50,   2,
                 np.where(svc > 48,  -5,
                                    -12))))

    # Conference Board LEI
    lei_6m = pct_chg(m["lei"], 6)
    score += np.where(lei_6m >  2,  10,
             np.where(lei_6m >  0.5, 5,
             np.where(lei_6m > -0.5, 0,
             np.where(lei_6m > -2,  -8,
                                   -15))))

    # Retail sales
    ret_yoy = pct_chg(m["retail"], 12)
    score += np.where(ret_yoy > 5,  8,
             np.where(ret_yoy > 2,  4,
             np.where(ret_yoy > 0,  0,
             np.where(ret_yoy > -2, -5,
                                   -10))))

    # GDP
    gdp_yoy = pct_chg(m["gdpc1"].ffill(), 4)
    score += np.where(gdp_yoy > 3,  8,
             np.where(gdp_yoy > 1,  4,
             np.where(gdp_yoy > 0,  0,
             np.where(gdp_yoy > -1, -6,
                                   -12))))

    # ── LABOR MARKET ──────────────────────────────────────────────────────

    # Unemployment trend (not Sahm Rule as standalone — just trend)
    uc_3m = m["unrate"].diff(3)
    score += np.where(uc_3m < -0.2,  8,
             np.where(uc_3m < 0,     4,
             np.where(uc_3m < 0.2,  -4,
             np.where(uc_3m < 0.5, -12,
                                   -20))))

    # Wage growth — moderate wages = Goldilocks, too high = inflation risk
    if "wages" in m.columns:
        wg = pct_chg(m["wages"], 12)
        score += np.where((wg > 2) & (wg < 5),  8,   # Goldilocks zone
                 np.where(wg > 6,               -5,   # too hot = inflation
                 np.where(wg < 1,               -5,   # too cold = deflation
                                                  0)))

    # ── FINANCIAL CONDITIONS ───────────────────────────────────────────────

    if "nfci" in m.columns:
        nf   = m["nfci"]
        nf_3m = nf.diff(3)
        score += np.where(nf < -0.5,  12,
                 np.where(nf < -0.2,   6,
                 np.where(nf <  0.1,   0,
                 np.where(nf <  0.4,  -8,
                                      -18))))
        score += np.where(nf_3m < -0.3,  8,
                 np.where(nf_3m >  0.3, -8, 0))

    # Bank lending standards — easing = credit expanding
    if "lending_std" in m.columns:
        ls = m["lending_std"].diff(2).fillna(0)
        score += np.where(ls < -8,  10,
                 np.where(ls < -3,   5,
                 np.where(ls >  8,  -10,
                 np.where(ls >  3,   -5, 0))))

    # ── INFLATION CONTEXT ─────────────────────────────────────────────────
    # Moderate inflation = Goldilocks, extreme = headwind

    pce_yoy = pct_chg(m["core_pce"], 12)
    score += np.where((pce_yoy > 1.5) & (pce_yoy < 2.5),  5,   # Goldilocks
             np.where(pce_yoy > 4,                         -10,  # too hot
             np.where(pce_yoy < 0.5,                       -5,   # deflation risk
                                                             0)))

    # Commodity prices (BCOM if available, else PPI)
    bcom_col = "bcom" if ("bcom" in m.columns and not m["bcom"].isna().all()) else "ppi"
    if bcom_col in m.columns:
        bc_6m = pct_chg(m[bcom_col], 6)
        # Rising commodities = inflationary pressure (slight negative)
        # Falling commodities = deflationary (slight negative)
        # Moderate = fine
        score += np.where((bc_6m > -5) & (bc_6m < 10),  3,
                 np.where(bc_6m > 15, -8,
                 np.where(bc_6m < -10, -5, 0)))

    # 5Y breakeven — rising expectations = inflationary pressure
    if "breakeven5y" in m.columns:
        be_3m = m["breakeven5y"].diff(3)
        score += np.where(be_3m > 0.5,  -8,
                 np.where(be_3m > 0.2,  -3,
                 np.where(be_3m < -0.3,  5, 0)))

    return score.clip(-100, 100)


# ─────────────────────────────────────────────────────────────────────────────
# MOMENTUM OVERLAY — price-based trend
# S&P 500 above/below key moving averages
# ─────────────────────────────────────────────────────────────────────────────

def compute_momentum(sp_daily):
    """
    Price momentum score: -100 to +100 on daily basis.
    Above 200DMA = bullish, below = bearish.
    """
    score = pd.Series(0.0, index=sp_daily.index)
    sp    = sp_daily.ffill()

    ma50  = sp.rolling(50).mean()
    ma200 = sp.rolling(200).mean()
    ma50_slope  = ma50.pct_change(20) * 100    # 20-day slope
    ma200_slope = ma200.pct_change(60) * 100   # 60-day slope

    # Price vs 200DMA
    pct_vs_200 = (sp / ma200 - 1) * 100
    score += np.where(pct_vs_200 >  10,  25,
             np.where(pct_vs_200 >   5,  18,
             np.where(pct_vs_200 >   0,  10,
             np.where(pct_vs_200 >  -5,  -8,
             np.where(pct_vs_200 > -10, -18,
                                        -30)))))

    # 50DMA vs 200DMA (golden/death cross)
    ma_ratio = (ma50 / ma200 - 1) * 100
    score += np.where(ma_ratio >  2,  15,
             np.where(ma_ratio >  0,   8,
             np.where(ma_ratio < -2, -15,
             np.where(ma_ratio <  0,  -8, 0))))

    # 200DMA slope (trending up vs down)
    score += np.where(ma200_slope >  1,  10,
             np.where(ma200_slope >  0,   5,
             np.where(ma200_slope < -1,  -12,
             np.where(ma200_slope <  0,   -6, 0))))

    return score.clip(-100, 100)


# ─────────────────────────────────────────────────────────────────────────────
# REGIME CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def classify_regime(fast_weekly, macro_monthly, momentum_daily, min_weeks=3):
    """
    Combine three layers into a final regime on weekly basis.

    Weights: Fast 45%, Macro 35%, Momentum 20%
    These reflect that fast signals should drive timing,
    macro provides context, momentum prevents fighting the trend.

    Risk-Off when composite < -15 (requires meaningful deterioration,
    not just noise). Risk-On when composite > -15.

    Min_weeks: must stay in new regime for N weeks before flipping.
    """
    # Resample all to weekly
    fast  = fast_weekly

    # Macro: resample monthly to weekly (forward-fill)
    macro = macro_monthly.resample("W").last().ffill()
    macro = macro.reindex(fast.index).ffill()

    # Momentum: resample daily to weekly
    mom = momentum_daily.resample("W").last().ffill()
    mom = mom.reindex(fast.index).ffill()

    # Composite
    composite = (
        fast  * 0.45 +
        macro * 0.35 +
        mom   * 0.20
    ).clip(-100, 100)

    # Smooth with 2-week rolling average to cut noise
    composite_smooth = composite.rolling(2, min_periods=1).mean()

    # Classify
    raw_regime = pd.Series("Risk-On", index=composite_smooth.index)
    raw_regime[composite_smooth < -15] = "Risk-Off"

    # Enforce minimum hold
    final   = raw_regime.copy()
    current = raw_regime.iloc[0]
    dur     = 1

    for i in range(1, len(raw_regime)):
        proposed = raw_regime.iloc[i]
        if proposed != current:
            if dur >= min_weeks:
                current = proposed
                dur     = 1
            else:
                dur += 1
        else:
            dur += 1
        final.iloc[i] = current

    return final, composite_smooth, fast, macro, mom


# ─────────────────────────────────────────────────────────────────────────────
# FETCH DATA
# ─────────────────────────────────────────────────────────────────────────────

pb = st.progress(0, text="Fetching FRED daily + monthly data...")
daily_df, monthly_df, fred_failed = fetch_all_data(TODAY, fred_key)

pb.progress(55, text="Fetching market data (S&P 500, VIX, DXY, BCOM)...")
market_data, yf_failed = fetch_market(TODAY)

pb.progress(80, text="Computing multi-frequency regime scores...")

# Fast layer (weekly)
fast_score = compute_fast_score(daily_df, market_data)

# Macro layer (monthly)
macro_score = compute_macro_score(monthly_df, market_data)

# Momentum layer (daily → weekly)
sp_daily = market_data.get("sp500", pd.Series(dtype=float))
if sp_daily is None or sp_daily.empty:
    st.error("Could not fetch S&P 500. Please try again.")
    st.stop()
sp_daily.index = pd.to_datetime(sp_daily.index).tz_localize(None)

momentum_score = compute_momentum(sp_daily)

# Classify regime
regime_weekly, composite, fast_w, macro_w, mom_w = classify_regime(
    fast_score, macro_score, momentum_score, min_weeks=3
)

pb.progress(100, text="Done!")
pb.empty()

# Align for combined DataFrame
sp_weekly = sp_daily.resample("W").last()
combined  = pd.DataFrame({
    "sp500":     sp_weekly,
    "regime":    regime_weekly,
    "composite": composite,
    "fast":      fast_w,
    "macro":     macro_w,
    "momentum":  mom_w,
}).dropna(subset=["sp500", "composite"])

if combined.empty:
    st.error("No overlapping data. Please try again.")
    st.stop()

# Daily regime for chart shading
start_date   = combined.index[0]
sp_aligned   = sp_daily[sp_daily.index >= start_date].dropna()
daily_regime = regime_weekly.reindex(sp_aligned.index, method="ffill").ffill()

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

st.markdown('<div class="sec-label">Regime Statistics</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="stat-grid">'
    '<div class="stat-card"><div class="stat-lbl">Date Range</div>'
    '<div class="stat-val" style="font-size:12px;color:#aaa;">' + date_range + '</div></div>'
    '<div class="stat-card"><div class="stat-lbl">Current Regime</div>'
    '<div class="stat-val" style="color:' + cur_color + ';font-size:15px;">'
    + current_reg.upper() + '</div></div>'
    '<div class="stat-card"><div class="stat-lbl">Risk-On</div>'
    '<div class="stat-val" style="color:#00D4AA;">' + str(round(on_pct)) + '%</div></div>'
    '<div class="stat-card"><div class="stat-lbl">Risk-Off</div>'
    '<div class="stat-val" style="color:#FF4757;">' + str(round(off_pct)) + '%</div></div>'
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
    "Current (2025+)":     ("2025-01", END,       "bull"),
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

st.markdown('<div class="sec-label">S&P 500 with Multi-Frequency Regime Overlay</div>',
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

# S&P price
ax1.plot(sp_aligned.index, sp_aligned.values, color="#E8E8E8", linewidth=1.2, zorder=5)

# 200-day moving average overlay
ma200 = sp_aligned.rolling(200).mean()
ax1.plot(ma200.index, ma200.values, color="#f59e0b", linewidth=0.7,
         alpha=0.6, linestyle="--", zorder=4, label="200DMA")

ax1.set_yscale("log")
ax1.set_ylabel("S&P 500 (log)", color="#666", fontsize=8, labelpad=8)
ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))
ax1.set_xlim(sp_aligned.index[0], sp_aligned.index[-1])
ax1.set_xticklabels([])
ax1.grid(axis="y", color="#111122", linewidth=0.5)
ax1.xaxis.set_major_locator(mdates.YearLocator(2))

for ds, lbl in [("2000-03","Dot-com"), ("2007-07","GFC"),
                ("2020-02","COVID"), ("2021-11","Peak"), ("2022-10","2022 Low")]:
    try:
        ed = pd.Timestamp(ds)
        if sp_aligned.index[0] <= ed <= sp_aligned.index[-1]:
            ax1.axvline(ed, color="#2a2a3a", linewidth=0.7, linestyle="--", zorder=3)
            ax1.text(ed, sp_aligned.max() * 0.88, lbl, color="#555", fontsize=6.5,
                     ha="center", bbox=dict(boxstyle="round,pad=0.2",
                     facecolor="#0A0A0F", edgecolor="#2a2a3a", alpha=0.9))
    except Exception:
        pass

p1 = mpatches.Patch(color="#00D4AA", alpha=0.5, label="Risk-On")
p2 = mpatches.Patch(color="#FF4757", alpha=0.5, label="Risk-Off")
p3 = plt.Line2D([0], [0], color="#f59e0b", linewidth=0.8,
                linestyle="--", label="200DMA")
ax1.legend(handles=[p1, p2, p3], loc="upper left", framealpha=0,
           fontsize=8, labelcolor="#aaa")
ax1.set_title(
    "S&P 500 — Multi-Frequency Regime Model v4  "
    "|  Fast (45%) + Macro (35%) + Momentum (20%)",
    color="#E8E8E8", fontsize=11, fontweight="bold", pad=10, loc="left"
)

# Composite score
cs = combined["composite"]
ax2.fill_between(cs.index, cs, 0, where=cs >= 0, color="#00D4AA",
                 alpha=0.3, interpolate=True)
ax2.fill_between(cs.index, cs, 0, where=cs < 0,  color="#FF4757",
                 alpha=0.3, interpolate=True)
ax2.plot(cs.index, cs.values, color="#aaa", linewidth=0.9, zorder=5)
ax2.axhline(0,   color="#333", linewidth=0.8)
ax2.axhline(-15, color="#FF4757", linewidth=0.6, linestyle=":",
            alpha=0.6)  # threshold line
ax2.text(cs.index[-1], -15, " Risk-Off threshold",
         color="#FF4757", fontsize=6.5, va="bottom", alpha=0.7)
ax2.set_ylim(-100, 100)
ax2.set_xlim(cs.index[0], cs.index[-1])
ax2.set_ylabel("Composite\nScore", color="#666", fontsize=7, labelpad=6)
ax2.set_xticklabels([])
ax2.xaxis.set_major_locator(mdates.YearLocator(2))
ax2.grid(axis="y", color="#111122", linewidth=0.5)

# Three layer scores
ax3.plot(combined.index, combined["fast"].values,
         color="#FF4757", linewidth=0.9, alpha=0.9, label="Fast (weekly)")
ax3.plot(combined.index, combined["macro"].values,
         color="#00D4AA", linewidth=0.9, alpha=0.9, label="Macro (monthly)")
ax3.plot(combined.index, combined["momentum"].values,
         color="#f59e0b", linewidth=0.8, alpha=0.8, label="Momentum (price)")
ax3.axhline(0, color="#333", linewidth=0.8)
ax3.set_ylim(-100, 100)
ax3.set_xlim(combined.index[0], combined.index[-1])
ax3.set_ylabel("Layer Scores", color="#666", fontsize=7, labelpad=6)
ax3.xaxis.set_major_locator(mdates.YearLocator(2))
ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax3.grid(axis="y", color="#111122", linewidth=0.5)
ax3.legend(loc="upper left", framealpha=0, fontsize=7,
           labelcolor="#aaa", ncol=3)

fig.text(0.99, 0.005,
         "Generated " + TODAY +
         "  ·  FRED (daily+monthly) + yfinance  ·  Multi-Frequency v4",
         ha="right", va="bottom", color="#333", fontsize=7,
         fontfamily="monospace")

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
    file_name="regime_v4_" + TODAY + ".pdf",
    mime="application/pdf",
)
