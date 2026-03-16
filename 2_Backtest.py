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
    "wages":       "CES0500000003", # Average hourly earnings (Fed wage watch)
    # Inflation
    "core_pce":    "PCEPILFE",      # Core PCE
    "breakeven5y": "T5YIE",         # 5Y breakeven inflation
    "cpi":         "CPIAUCSL",      # CPI
    # Oil (Luke explicitly mentions in transcript 2)
    "oil":         "DCOILWTICO",    # WTI crude oil price
    # Labor market — Fed dual mandate
    "payrolls":    "PAYEMS",        # Nonfarm payrolls (monthly change)
    "u6":          "U6RATE",        # U6 underemployment (broader than U3)
    "jolts_quit":  "JTSQUR",        # Quits rate — leading labor strength signal
    "avg_hours":   "AWHMAN",        # Average weekly hours (leading employment)
    "wages":       "CES0500000003", # Average hourly earnings
    "cont_claims": "CCSA",          # Continued jobless claims
    # Fed outlook / rate expectations proxy
    "t1y":         "DGS1",          # 1Y Treasury (closer to Fed expectations)
    "t3m":         "DTB3",          # 3M T-bill (current Fed rate proxy)
    "sofr":        "SOFR",          # SOFR rate (overnight rate expectations)
    "pce_target":  "PCEPILFE",      # Core PCE vs 2% target (already fetched as core_pce)
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
    """Fresh fetch with robust MultiIndex handling."""
    import yfinance as yf
    results = {}
    failed  = []
    tickers = {
        "sp500": "^GSPC",
        "dxy":   "DX-Y.NYB",
        "bcom":  "^BCOM",
        "oil_yf":"CL=F",
    }
    for name, ticker in tickers.items():
        try:
            raw = yf.download(ticker, start=FETCH_START, end=END,
                              progress=False, auto_adjust=True)
            if raw.empty:
                failed.append(ticker)
                continue
            # Handle MultiIndex columns (newer yfinance)
            if isinstance(raw.columns, pd.MultiIndex):
                # Try to get Close for this ticker
                if ("Close", ticker) in raw.columns:
                    s = raw[("Close", ticker)]
                elif "Close" in raw.columns.get_level_values(0):
                    s = raw["Close"].iloc[:, 0]
                else:
                    s = raw.iloc[:, 0]
            else:
                if "Close" in raw.columns:
                    s = raw["Close"]
                elif "Adj Close" in raw.columns:
                    s = raw["Adj Close"]
                else:
                    s = raw.iloc[:, 0]
            s = s.squeeze()
            if hasattr(s.index, 'tz') and s.index.tz is not None:
                s.index = s.index.tz_localize(None)
            else:
                s.index = pd.to_datetime(s.index)
            s = s.dropna()
            if not s.empty:
                results[name] = s
            else:
                failed.append(ticker)
        except Exception as e:
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
    Monetary policy + FedWatch proxy + Labor market Fed reaction function.

    THREE COMPONENTS:

    1. FEDWATCH PROXY (2Y yield as market's rate expectation)
       CME FedWatch shows cut/hike probabilities in real-time.
       The 2Y Treasury is the best free proxy — it prices in the next
       12-18 months of Fed policy BEFORE the Fed acts.
       - 2Y falling fast = market pricing in cuts = bullish
       - 2Y rising fast = market pricing in hikes = bearish
       - Rate of CHANGE matters more than level

    2. FED DUAL MANDATE — LABOR MARKET REACTION FUNCTION
       The Fed has two jobs: control inflation AND maximize employment.
       When labor weakens → Fed gets permission to cut → bullish.
       When labor is too hot → Fed stays restrictive → bearish.
       Luke mentions: "unemployment up → markets go up because Fed
       will cut rates" — this second-order logic must be captured.

       Labor score = f(unemployment trend, claims trend, wages)
       mapped to Fed's LIKELY REACTION, not raw labor strength.

    3. POLICY STANCE (actual rates + TIPS + financial conditions)
    """
    s = pd.Series(0.0, index=m.index)

    hy_in_crisis = (m["hy_spread"] > 600) if "hy_spread" in m.columns \
                   else pd.Series(False, index=m.index)

    # ── 1. FEDWATCH PROXY: 2Y YIELD ──────────────────────────────────
    # The 2Y moves BEFORE the Fed. It's the market's vote on future policy.
    # This is effectively what CME FedWatch shows — priced into 2Y.
    t2y_3m = m["t2y"].diff(3)   # 3-month change = rate expectation shift
    t2y_1m = m["t2y"].diff(1)   # 1-month for acceleration
    t2y_lvl = m["t2y"]           # absolute level

    # Direction of market's rate expectation — primary signal
    raw_fw = np.where(t2y_3m < -1.00,  40,   # market pricing aggressive cuts
             np.where(t2y_3m < -0.50,  26,
             np.where(t2y_3m < -0.25,  14,
             np.where(t2y_3m < -0.05,   5,
             np.where(t2y_3m <  0.10,   0,
             np.where(t2y_3m <  0.40, -12,
             np.where(t2y_3m <  0.75, -24,
             np.where(t2y_3m <  1.25, -36,
                                       -45))))))))

    # During credit crisis: falling 2Y = cuts coming = keep this signal
    # (different from actual cuts which are reactive)
    s += pd.Series(raw_fw, index=m.index)

    # Absolute level: very high 2Y = rate environment is restrictive
    s += np.where(t2y_lvl > 5.0, -15,
         np.where(t2y_lvl > 4.0,  -8,
         np.where(t2y_lvl > 3.0,  -3,
         np.where(t2y_lvl < 1.0,  10,
         np.where(t2y_lvl < 0.5,  18, 0)))))

    # ── 2. LABOR MARKET → FED REACTION FUNCTION ──────────────────────
    # Map labor data to Fed's likely policy response
    # Weak labor = Fed cuts = bullish | Hot labor = Fed holds/hikes = bearish
    # Luke: "unemployment going up → Fed will cut → markets go up"

    labor = pd.Series(0.0, index=m.index)

    # Unemployment trend — Sahm-like but mapped to Fed reaction
    uc_3m = m["unrate"].diff(3)   # 3-month change
    uc_6m = m["unrate"].diff(6)   # 6-month change
    unrate_12m_low = m["unrate"].rolling(12).min()
    sahm  = m["unrate"] - unrate_12m_low  # Sahm indicator

    # Rising unemployment → Fed gets permission to cut → BULLISH for markets
    # (counterintuitive but correct — Luke explains this in transcript 1)
    labor += np.where(uc_3m > 0.5,   25,   # labor weakening fast → big cut signal
             np.where(uc_3m > 0.3,   15,
             np.where(uc_3m > 0.1,    6,
             np.where(uc_3m < -0.3, -15,   # labor too hot → Fed stays hawkish
             np.where(uc_3m < -0.1,  -6, 0)))))

    # Sahm Rule trigger → recession + Fed emergency cuts incoming
    # Short-term bearish (recession) but forward-looking = cuts coming
    # Net effect depends on context — use moderate positive (cuts incoming)
    labor += np.where(sahm > 0.5,  12,   # Sahm triggered → Fed will cut aggressively
             np.where(sahm > 0.3,   6,
             np.where(sahm > 0.1,   2, 0)))

    # Initial jobless claims — most timely labor signal
    if "icsa" in m.columns:
        ic_4w = pct(m["icsa"], 3)   # 3-month % change
        # Rising claims → labor weakening → Fed cuts → bullish expectation
        labor += np.where(ic_4w > 20,   18,   # claims spiking → big cut priced in
                 np.where(ic_4w > 10,   10,
                 np.where(ic_4w > 5,     4,
                 np.where(ic_4w < -10, -12,   # claims falling → labor hot → Fed holds
                 np.where(ic_4w < -5,   -6, 0)))))

    # Wages — too hot = Fed can't cut; Goldilocks = Fed can ease
    if "wages" in m.columns:
        wage_yoy = pct(m["wages"], 12)
        # Fed's target is ~3-3.5% wage growth
        labor += np.where(wage_yoy > 6.0, -18,   # too hot → inflation spiral
                 np.where(wage_yoy > 4.5,  -8,   # above comfort
                 np.where(wage_yoy > 3.5,  -2,
                 np.where(wage_yoy > 2.5,   8,   # Goldilocks → Fed comfortable cutting
                 np.where(wage_yoy > 1.5,   4,   # soft
                                           -5))))) # deflation risk

    # Unemployment LEVEL vs historical — very low = Fed alert on inflation
    unrate_lvl = m["unrate"]
    labor += np.where(unrate_lvl > 5.5,  10,   # slack → cut-friendly
             np.where(unrate_lvl > 4.5,   4,
             np.where(unrate_lvl > 4.0,   0,
             np.where(unrate_lvl > 3.5,  -6,   # tight → Fed hawkish
                                          -12)))) # very tight → no cuts

    s += labor * 0.5   # Labor reaction = 50% weight within monetary

    # ── 3. POLICY STANCE ─────────────────────────────────────────────
    # Actual Fed rate + TIPS + financial conditions

    # Fed funds actual pace (reactive but still informative)
    effr_3m = m["effr"].diff(3)
    raw_effr = np.where(effr_3m < -0.5,  20,
               np.where(effr_3m < -0.25, 10,
               np.where(effr_3m <  0,     3,
               np.where(effr_3m <  0.25, -6,
               np.where(effr_3m <  0.5, -16,
               np.where(effr_3m <  1.0, -26, -35))))))
    # Neutralize during credit crisis — cuts are reactive
    s += pd.Series(np.where(hy_in_crisis & (effr_3m < 0), 0, raw_effr),
                   index=m.index) * 0.4

    # TIPS real yields
    if "tips10y" in m.columns:
        tips    = m["tips10y"]
        tips_3m = tips.diff(3)
        s += np.where(tips < -1.5, 12, np.where(tips < -0.5,  7,
             np.where(tips <  0,    2, np.where(tips <  0.5,  -5,
             np.where(tips <  1.5,-10,                         -16))))) * 0.4
        s += np.where(tips_3m < -0.5,  8,
             np.where(tips_3m >  0.5, -10, 0)) * 0.4

    # Yield curve (10Y-2Y)
    if "t10y2y" in m.columns:
        yc = m["t10y2y"]
        s += np.where(yc > 1.5,  10, np.where(yc > 0.5,  5,
             np.where(yc > 0,     1, np.where(yc > -0.5, -4,
             np.where(yc > -1.0, -10,                     -14))))) * 0.4

    # NFCI financial conditions
    if "nfci" in m.columns:
        nf = m["nfci"]
        s += np.where(nf < -0.5,  8, np.where(nf < -0.1,  4,
             np.where(nf <  0.2,  0, np.where(nf <  0.5,  -6, -12)))) * 0.4

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


def sig_fed_outlook(m):
    """
    CME FedWatch proxy — forward-looking rate cut probability.

    Since we can't scrape CME in a cached backtest, we use the best
    available proxies that LEAD the actual Fed decision by 1-3 months:

    1. T1Y - T3M spread: market pricing future cuts vs current rate
       When 1Y yield < 3M yield = market expects cuts ahead = bullish
       When 1Y yield > 3M yield = market expects hikes = bearish

    2. 2Y yield vs Fed funds rate gap:
       When 2Y significantly below EFFR = aggressive cut pricing
       When 2Y above EFFR = hike pricing

    3. SOFR vs EFFR spread: overnight market stress/expectations

    This captures what CME FedWatch shows — the market's forward
    expectation of Fed policy, which leads actual Fed decisions by
    1-3 FOMC meetings (roughly 3-6 months).
    """
    s = pd.Series(0.0, index=m.index)

    # ── T1Y vs T3M: term premium / rate expectations ──────────────────
    # 1Y-3M inversion = cuts expected within a year = bullish setup
    if "t1y" in m.columns and "t3m" in m.columns:
        t1y  = m["t1y"]
        t3m  = m["t3m"]
        gap  = t1y - t3m   # negative = cuts priced in

        s += np.where(gap < -1.0,  45,   # >100bps cuts priced: very bullish
             np.where(gap < -0.5,  28,
             np.where(gap < -0.2,  14,
             np.where(gap < 0.0,    5,
             np.where(gap < 0.2,   -5,
             np.where(gap < 0.5,  -14,
             np.where(gap < 1.0,  -25,
                                   -35)))))))   # hikes priced: very bearish

        # Rate of change — accelerating cut pricing = strong bullish
        gap_3m = gap.diff(3)
        s += np.where(gap_3m < -0.5,  18,
             np.where(gap_3m < -0.2,   9,
             np.where(gap_3m >  0.5,  -18,
             np.where(gap_3m >  0.2,   -9, 0))))

    # ── 2Y vs Fed funds: market vs actual ────────────────────────────
    # 2Y well below EFFR = market pricing multiple cuts = bullish
    if "t2y" in m.columns and "effr" in m.columns:
        gap2 = m["t2y"] - m["effr"]

        s += np.where(gap2 < -1.5,  35,   # deep inversion: big cuts priced
             np.where(gap2 < -0.75, 20,
             np.where(gap2 < -0.25,  8,
             np.where(gap2 <  0.25,  0,
             np.where(gap2 <  0.75, -10,
             np.where(gap2 <  1.5,  -20,
                                    -30))))))   # 2Y > EFFR: hikes priced

    # ── SOFR vs EFFR: overnight market stress ─────────────────────────
    # SOFR spiking above EFFR = funding stress = bearish
    if "sofr" in m.columns and "effr" in m.columns:
        sofr_gap = m["sofr"] - m["effr"]
        s += np.where(sofr_gap > 0.25, -20,
             np.where(sofr_gap > 0.1,  -10,
             np.where(sofr_gap < -0.1,   8, 0)))

    return s.clip(-100, 100)


def sig_labor_dual_mandate(m):
    """
    Fed Dual Mandate: Employment + Inflation INTERACTION.

    The key is how labor and inflation interact to constrain/enable Fed policy:

    SCENARIO A — Bullish: Labor weakening + inflation falling
      → Fed CAN cut aggressively → risk assets rally
      → This is the 2023-2024 soft landing

    SCENARIO B — Bearish: Labor strong + inflation high
      → Fed CANNOT cut (2022 exactly)
      → Risk assets get crushed

    SCENARIO C — Mixed bullish: Labor weakening but inflation controlled
      → Fed cuts to protect employment → risk assets OK

    SCENARIO D — Mixed bearish: Labor fine + inflation reaccelerating
      → Fed tightens more than expected → headwind

    Individual components:
    - Payrolls momentum (leading)
    - Jobless claims trend (most timely)
    - Unemployment Sahm-style acceleration
    - Wage growth vs inflation (real wages = consumer health)
    - JOLTS quits rate (highest = workers confident = strong labor)
    - Dual mandate interaction score (the key NEW signal)
    """
    s = pd.Series(0.0, index=m.index)

    # ── Nonfarm payrolls momentum ──────────────────────────────────────
    if "payrolls" in m.columns and not m["payrolls"].isna().all():
        pay_3m = m["payrolls"].diff(3)   # 3M change in level
        pay_mom = pct(m["payrolls"], 3)  # % change
        s += np.where(pay_3m > 600,  20,
             np.where(pay_3m > 300,  12,
             np.where(pay_3m > 100,   5,
             np.where(pay_3m > -100, -5,
             np.where(pay_3m > -300,-15,
                                    -28)))))

    # ── Jobless claims (most timely labor signal) ──────────────────────
    if "icsa" in m.columns:
        ic_chg = pct(m["icsa"], 3)
        ic_lvl = m["icsa"]
        # Absolute level vs historical threshold
        s += np.where(ic_lvl < 200,   12,
             np.where(ic_lvl < 250,    6,
             np.where(ic_lvl < 300,    2,
             np.where(ic_lvl < 350,   -4,
             np.where(ic_lvl < 450,  -12,
                                      -22)))))
        # Trend
        s += np.where(ic_chg < -10,  10,
             np.where(ic_chg < -5,    5,
             np.where(ic_chg > 20,  -18,
             np.where(ic_chg > 10,  -10,
             np.where(ic_chg > 5,    -5, 0)))))

    # ── Continued claims (depth of unemployment) ──────────────────────
    if "cont_claims" in m.columns and not m["cont_claims"].isna().all():
        cc_3m = pct(m["cont_claims"], 3)
        s += np.where(cc_3m < -8,   8,
             np.where(cc_3m < -3,   4,
             np.where(cc_3m > 15,  -12,
             np.where(cc_3m > 8,    -6, 0))))

    # ── JOLTS Quits Rate — most leading labor signal ───────────────────
    # High quits = workers confident, labor tight = strong economy
    # But too high → wage pressure → inflation → Fed constrained
    if "jolts_quit" in m.columns and not m["jolts_quit"].isna().all():
        qr     = m["jolts_quit"]
        qr_3m  = qr.diff(3)
        # Level: 2-3% = healthy, <1.8% = labor cooling
        s += np.where(qr > 3.0,   5,   # very high: slightly negative (wage pressure)
             np.where(qr > 2.5,  12,   # strong: bullish
             np.where(qr > 2.0,   6,
             np.where(qr > 1.8,  -4,
             np.where(qr > 1.5, -12,
                                 -20)))))
        # Trend
        s += np.where(qr_3m > 0.2,   8,
             np.where(qr_3m < -0.2, -10, 0))

    # ── Real wages (wages - inflation) — consumer health ──────────────
    if "wages" in m.columns and "core_pce" in m.columns:
        wage_yoy = pct(m["wages"], 12)
        pce_yoy  = pct(m["core_pce"], 12)
        real_wage = wage_yoy - pce_yoy  # positive = real gains = bullish
        s += np.where(real_wage > 2,   14,
             np.where(real_wage > 0.5,  8,
             np.where(real_wage > 0,    3,
             np.where(real_wage > -1,  -4,
             np.where(real_wage > -2, -10,
                                      -18)))))

    # ── DUAL MANDATE INTERACTION — the key new signal ─────────────────
    # This is what determines whether the Fed is FREE to act or CONSTRAINED
    if "unrate" in m.columns and "core_pce" in m.columns:
        un    = m["unrate"]
        pce   = pct(m["core_pce"], 12)
        un_3m = un.diff(3)

        # Fed FREEDOM score: can they cut without stoking inflation?
        # Falling unemployment + high inflation = constrained (bearish)
        # Rising unemployment + falling inflation = free to cut (bullish)
        labor_stress  = un_3m > 0.3   # unemployment rising
        infl_falling  = pce < 2.5     # inflation near/below target
        infl_hot      = pce > 3.0     # inflation above comfort zone
        labor_tight   = un < 4.0      # labor market very tight

        # Best case: Fed can cut freely (labor weakening + inflation cooling)
        dual_bullish = labor_stress & infl_falling
        # Worst case: Fed stuck (labor tight + inflation hot = 2022)
        dual_bearish = labor_tight & infl_hot

        s += pd.Series(
            np.where(dual_bullish,  25,    # Fed free to cut = very bullish
            np.where(dual_bearish, -30,    # Fed stuck = very bearish (2022)
                                     0)),  # mixed = neutral
            index=m.index
        )

        # Sahm Rule: unemployment 0.5% above 12M low = recession signal
        un_12m_low = un.rolling(12).min()
        sahm       = un - un_12m_low
        s += np.where(sahm > 0.5, -20,
             np.where(sahm > 0.3, -10, 0))

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
sp_daily = market_data.get("sp500", None)
if sp_daily is None or (hasattr(sp_daily, 'empty') and sp_daily.empty):
    # Try fetching S&P 500 directly as fallback
    try:
        import yfinance as yf
        raw = yf.download("^GSPC", start=FETCH_START, end=END,
                          progress=False, auto_adjust=True)
        if isinstance(raw.columns, pd.MultiIndex):
            sp_daily = raw["Close"].iloc[:, 0]
        else:
            sp_daily = raw["Close"]
        sp_daily = sp_daily.squeeze().dropna()
        sp_daily.index = pd.to_datetime(sp_daily.index)
        if hasattr(sp_daily.index, 'tz') and sp_daily.index.tz:
            sp_daily.index = sp_daily.index.tz_localize(None)
    except Exception:
        st.error("Could not fetch S&P 500 from yfinance. Please check your internet connection and try again.")
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
