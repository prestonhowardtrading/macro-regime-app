"""
Macro Regime Backtest — GL Framework v3
========================================
Four precise fixes from diagnosis:

FIX 1 — RATE CUTS DURING CREDIT CRISIS = REACTIVE (not bullish)
  When HY > 550bps, monetary easing signals are neutralized.
  A Fed cutting rates during a credit crisis is fighting the fire,
  not adding fuel. Same logic as crisis QE.

FIX 2 — COVID: 1-MONTH MINIMUM, NO SMOOTHING ON CRISIS SIGNALS
  COVID crash lasted 33 days. 2-month smoothing means it never
  sustained. Crisis signals (HY > 600bps) bypass smoothing and
  trigger Risk-Off immediately with only 1-month hold.

FIX 3 — DOT-COM: ADD EQUITY MOMENTUM + LEI EARLY WARNING
  Dot-com had no credit crisis early. Need equity-based signal:
  S&P 500 below falling 12-month MA + LEI declining = Risk-Off.
  This captures valuation-driven bear markets without needing
  a credit crisis.

FIX 4 — 2022 EXIT: MONETARY POLICY FADE DURING RECOVERY
  When credit stress is recovering (spreads falling from peak)
  AND dollar is weakening, reduce monetary policy penalty weight.
  The rate hike PACE matters — Fed slowing = less restrictive.
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
    '— GL Framework v3</span></h1>'
    '<p style="margin:6px 0 24px;font-size:12px;color:#555;">'
    'Crisis-aware monetary neutralization · Fast COVID reaction · '
    'Dot-com equity signal · 2022 recovery exit</p>',
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
        'Enter your FRED API key above.</div>', unsafe_allow_html=True
    )
    st.stop()

START = "2018-01-01"   # 2018 start gives 12-month MA runway by Jan 2019
END   = date.today().strftime("%Y-%m-%d")
TODAY = str(date.today())

# ─────────────────────────────────────────────────────────────────────────────
# DATA FETCH
# ─────────────────────────────────────────────────────────────────────────────

FRED_SERIES = {
    "walcl":       "WALCL",
    "ecb_assets":  "ECBASSETSW",
    "boj_assets":  "JPNASSETS",
    "m2":          "M2SL",
    "tga":         "WTREGEN",
    "rrp":         "RRPONTSYD",
    "dxy_proxy":   "DTWEXBGS",
    "effr":        "FEDFUNDS",
    "t2y":         "DGS2",
    "t10y2y":      "T10Y2Y",
    "tips10y":     "DFII10",
    "hy_spread":   "BAMLH0A0HYM2",
    "ig_spread":   "BAMLC0A0CM",
    "nfci":        "NFCI",
    "govt_spend":  "FGEXPND",
    "ism_mfg":     "NAPM",
    "lei":         "USSLIND",
    "unrate":      "UNRATE",
    "cpi":         "CPIAUCSL",
    "core_pce":    "PCEPILFE",
    "breakeven5y": "T5YIE",
    "icsa":        "ICSA",
    "retail":      "RSAFS",
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
    for name, ticker in {"sp500": "^GSPC", "dxy": "DX-Y.NYB", "bcom": "^BCOM"}.items():
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
# COMPONENT SCORES
# ─────────────────────────────────────────────────────────────────────────────

def pct_chg(s, n): return s.pct_change(n) * 100


def score_credit_stress(m):
    """
    Credit stress: level + momentum of HY and IG spreads.
    This is the primary crisis detector.
    HIGH WEIGHT when in crisis. Normal weight otherwise.
    """
    cs = pd.Series(0.0, index=m.index)

    if "hy_spread" not in m.columns:
        return cs

    hy        = m["hy_spread"]
    hy_3m     = hy.diff(3)
    hy_3m_max = hy.rolling(3).max()
    hy_6m_max = hy.rolling(6).max()

    # Level — granular thresholds
    cs += np.where(hy < 275,   35,
          np.where(hy < 325,   25,
          np.where(hy < 375,   15,
          np.where(hy < 425,    8,
          np.where(hy < 475,    2,
          np.where(hy < 525,   -5,
          np.where(hy < 600,  -18,
          np.where(hy < 750,  -35,
          np.where(hy < 1000, -55,
                               -70)))))))))

    # Speed — rapid widening = crisis building
    cs += np.where(hy_3m >  300, -35,
          np.where(hy_3m >  200, -25,
          np.where(hy_3m >  100, -15,
          np.where(hy_3m >   50,  -8,
          np.where(hy_3m < -200,  25,
          np.where(hy_3m < -100,  15,
          np.where(hy_3m <  -50,   8, 0)))))))

    # Peak turning — spreads falling from recent high = recovery
    turning  = hy < hy_3m_max * 0.88
    elevated = hy > 450
    at_peak  = hy >= hy_3m_max * 0.98
    cs += pd.Series(np.where(turning & elevated,   20,
                   np.where(turning & ~elevated,   10,
                   np.where(at_peak & elevated,   -10, 0))),
                   index=m.index)

    # IG spreads (early mover)
    if "ig_spread" in m.columns:
        ig    = m["ig_spread"]
        ig_3m = ig.diff(3)
        cs += np.where(ig < 0.8,   12,
              np.where(ig < 1.0,    7,
              np.where(ig < 1.3,    2,
              np.where(ig < 1.8,   -6,
              np.where(ig < 2.5,  -16,
              np.where(ig < 3.5,  -28,
                                   -40))))))
        cs += np.where(ig_3m < -0.4,   10,
              np.where(ig_3m < -0.2,    5,
              np.where(ig_3m >  0.5,  -12,
              np.where(ig_3m >  0.3,   -6, 0))))

    return cs.clip(-100, 100)


def score_global_liquidity(m):
    """GL: rate of change of combined CB balance sheets + plumbing"""
    gl = pd.Series(0.0, index=m.index)

    fed_3m  = pct_chg(m["walcl"], 3)
    fed_1m  = pct_chg(m["walcl"], 1)
    fed_yoy = pct_chg(m["walcl"], 12)

    # Crisis QE = reactive, neutralize
    crisis_qe  = fed_1m > 8
    normal_fed = np.where(fed_3m > 4,   22,
                 np.where(fed_3m > 2,   14,
                 np.where(fed_3m > 0.5,  6,
                 np.where(fed_3m > -0.5,-4,
                 np.where(fed_3m > -2, -14,
                 np.where(fed_3m > -4, -22,
                                       -30))))))
    gl += pd.Series(np.where(crisis_qe, 0, normal_fed), index=m.index)

    if "ecb_assets" in m.columns and not m["ecb_assets"].isna().all():
        ecb_3m = pct_chg(m["ecb_assets"], 3)
        ecb_1m = pct_chg(m["ecb_assets"], 1)
        crisis_ecb = ecb_1m > 6
        ecb_n  = np.where(ecb_3m > 3,  12, np.where(ecb_3m > 1, 6,
                 np.where(ecb_3m > -1, -4, np.where(ecb_3m > -3,-10,-15))))
        gl += pd.Series(np.where(crisis_ecb, 0, ecb_n), index=m.index)

    if "boj_assets" in m.columns and not m["boj_assets"].isna().all():
        boj_3m  = pct_chg(m["boj_assets"], 3)
        boj_yoy = pct_chg(m["boj_assets"], 12)
        gl += np.where(boj_3m > 3, 10, np.where(boj_3m > 1, 5,
              np.where(boj_3m > -1, -3, np.where(boj_3m > -3, -8, -12))))
        gl += np.where(boj_yoy < -5, -12, np.where(boj_yoy < -2, -6, 0))

    m2_yoy = pct_chg(m["m2"], 12)
    m2_3m  = pct_chg(m["m2"], 3)
    gl += np.where(m2_yoy > 10, 14, np.where(m2_yoy > 5, 8,
          np.where(m2_yoy > 2, 3, np.where(m2_yoy > -1, -3,
          np.where(m2_yoy > -4, -10, -18)))))
    gl += np.where(m2_3m > 1.5, 6, np.where(m2_3m > 0, 2,
          np.where(m2_3m < -1.5, -6, np.where(m2_3m < 0, -2, 0))))

    if "tga" in m.columns:
        tga_3m = m["tga"].diff(3)
        gl += np.where(tga_3m < -200, 16, np.where(tga_3m < -100, 9,
              np.where(tga_3m < -50, 4, np.where(tga_3m > 200, -16,
              np.where(tga_3m > 100, -9, np.where(tga_3m > 50, -4, 0))))))

    if "rrp" in m.columns:
        rrp_3m = m["rrp"].diff(3).fillna(0)
        gl += np.where(rrp_3m < -300, 14, np.where(rrp_3m < -100, 7,
              np.where(rrp_3m < -50, 3, np.where(rrp_3m > 300, -12,
              np.where(rrp_3m > 100, -6, np.where(rrp_3m > 50, -3, 0))))))

    return gl.clip(-100, 100)


def score_dollar(m, market_data):
    """Dollar direction: weak = bullish, strong = bearish"""
    d = pd.Series(0.0, index=m.index)
    dxy_col = "dxy" if ("dxy" in m.columns and not m["dxy"].isna().all()) else "dxy_proxy"
    if dxy_col in m.columns:
        dxy    = m[dxy_col]
        dxy_3m = pct_chg(dxy, 3)
        dxy_6m = pct_chg(dxy, 6)
        d += np.where(dxy_3m < -5,  35, np.where(dxy_3m < -3,  24,
             np.where(dxy_3m < -1,  14, np.where(dxy_3m < -0.3, 6,
             np.where(dxy_3m <  0.3, 0, np.where(dxy_3m <  1.5,-12,
             np.where(dxy_3m <  3, -22, np.where(dxy_3m <  5, -30,
                                                              -38))))))))
        d += np.where(dxy_6m < -8, 14, np.where(dxy_6m < -4, 8,
             np.where(dxy_6m < -1, 3, np.where(dxy_6m < 1, 0,
             np.where(dxy_6m < 4, -8, np.where(dxy_6m < 8, -14, -18))))))
    return d.clip(-100, 100)


def score_monetary_policy(m, hy_spread_series):
    """
    FIX 1: When HY spreads > 550bps (credit crisis), rate cuts are
    REACTIVE — neutralize the bullish rate cut signal.
    The Fed is fighting the fire. That's not a bullish macro signal.

    FIX 4: When in 2022-style tightening BUT spreads are recovering,
    use rate PACE (acceleration) rather than absolute direction.
    """
    mp = pd.Series(0.0, index=m.index)

    # Is this a credit crisis environment?
    hy           = hy_spread_series
    credit_crisis = hy > 550  # GFC, COVID, dot-com late stage

    effr_3m = m["effr"].diff(3)
    effr_1m = m["effr"].diff(1)

    # Raw monetary signal
    raw_mp = np.where(effr_3m < -0.5,  24,
             np.where(effr_3m < -0.25, 14,
             np.where(effr_3m <  0,     4,
             np.where(effr_3m <  0.25, -6,
             np.where(effr_3m <  0.5, -18,
             np.where(effr_3m <  1.0, -28,
                                       -38))))))

    # FIX 1: During credit crisis, neutralize the easing signal
    # (cuts are reactive) but keep the tightening signal if any
    adj_mp = np.where(
        credit_crisis & (effr_3m < 0),
        0,          # neutralize cuts during credit crisis
        raw_mp      # keep normal signal otherwise
    )
    mp += pd.Series(adj_mp, index=m.index)

    # 2Y yield — forward market expectations
    if "t2y" in m.columns:
        t2y_3m = m["t2y"].diff(3)
        raw_t2y = np.where(t2y_3m < -0.75,  18, np.where(t2y_3m < -0.35, 10,
                  np.where(t2y_3m < -0.1,    4, np.where(t2y_3m <  0.35,  -6,
                  np.where(t2y_3m <  0.75, -14,                            -22)))))
        # During crisis: falling 2Y = rate cuts coming = slightly positive
        # (different from Fed already cutting — this is forward-looking)
        mp += pd.Series(raw_t2y * 0.7, index=m.index)  # dampen slightly

    # Real rates (TIPS)
    if "tips10y" in m.columns:
        tips    = m["tips10y"]
        tips_3m = tips.diff(3)
        mp += np.where(tips < -1.5, 12, np.where(tips < -0.5, 6,
              np.where(tips <  0, 2, np.where(tips < 0.5, -4,
              np.where(tips <  1.5, -10, -16)))))
        mp += np.where(tips_3m < -0.5, 8, np.where(tips_3m < -0.2, 4,
              np.where(tips_3m > 0.5, -10, np.where(tips_3m > 0.2, -5, 0))))

    # Yield curve
    yc = m["t10y2y"]
    mp += np.where(yc > 1.5, 10, np.where(yc > 0.5, 5,
          np.where(yc > 0, 2, np.where(yc > -0.5, -4,
          np.where(yc > -1.0, -10, -15)))))

    # Financial conditions
    if "nfci" in m.columns:
        nf = m["nfci"]
        mp += np.where(nf < -0.5, 8, np.where(nf < -0.1, 4,
              np.where(nf < 0.2, 0, np.where(nf < 0.5, -6, -12))))

    return mp.clip(-100, 100)


def score_equity_trend(m, market_data):
    """
    FIX 3: Dot-com early warning.
    S&P 500 price momentum as a regime signal.
    Equity bear markets that don't start with a credit crisis
    (like dot-com 2000, some 2018 episodes) need a price-based signal.

    S&P 500 below its 12-month MA AND declining = Risk-Off context.
    Also: ISM + LEI both declining = growth warning.
    """
    eq = pd.Series(0.0, index=m.index)

    # S&P 500 vs 12-month moving average
    if "sp500" in m.columns:
        sp     = m["sp500"]
        sp_12m = sp.rolling(12).mean()
        sp_6m  = sp.rolling(6).mean()
        sp_pct = (sp / sp_12m - 1) * 100

        # Below 12M MA = trend is bearish
        eq += np.where(sp_pct >  10,  18,
              np.where(sp_pct >   5,  12,
              np.where(sp_pct >   0,   5,
              np.where(sp_pct >  -5,  -8,
              np.where(sp_pct > -10, -18,
                                     -30)))))

        # 6M momentum (rate of change)
        sp_6m_roc = pct_chg(sp, 6)
        eq += np.where(sp_6m_roc >  15,  12,
              np.where(sp_6m_roc >   5,   6,
              np.where(sp_6m_roc >   0,   2,
              np.where(sp_6m_roc > -10,  -8,
              np.where(sp_6m_roc > -20, -18,
                                        -28)))))

    # ISM Manufacturing trend
    if "ism_mfg" in m.columns:
        pmi    = m["ism_mfg"]
        pmi_3m = pmi.diff(3)
        eq += np.where(pmi > 55,  12, np.where(pmi > 52, 7,
              np.where(pmi > 50,  2, np.where(pmi > 48, -5,
              np.where(pmi > 45, -12, -22)))))
        eq += np.where(pmi_3m > 3, 6, np.where(pmi_3m > 1, 3,
              np.where(pmi_3m < -3, -6, np.where(pmi_3m < -1, -3, 0))))

    # Conference Board LEI
    lei_6m = pct_chg(m["lei"], 6)
    eq += np.where(lei_6m > 2, 10, np.where(lei_6m > 0.5, 5,
          np.where(lei_6m > -0.5, 0, np.where(lei_6m > -2, -8, -15))))

    # Jobless claims trend
    if "icsa" in m.columns:
        ic_3m = pct_chg(m["icsa"], 3)
        eq += np.where(ic_3m < -8, 8, np.where(ic_3m < -3, 4,
              np.where(ic_3m > 20, -16, np.where(ic_3m > 10, -8,
              np.where(ic_3m > 5, -4, 0)))))

    return eq.clip(-100, 100)


def score_fiscal(m):
    """Fiscal policy: stimulus = bullish, austerity = bearish"""
    fp = pd.Series(0.0, index=m.index)
    if "govt_spend" in m.columns and not m["govt_spend"].isna().all():
        gs_yoy = pct_chg(m["govt_spend"], 12)
        fp += np.where(gs_yoy > 8, 18, np.where(gs_yoy > 4, 10,
              np.where(gs_yoy > 1, 3, np.where(gs_yoy > -1, -3,
              np.where(gs_yoy > -4, -10, -18)))))

    m2_yoy    = pct_chg(m["m2"], 12)
    walcl_yoy = pct_chg(m["walcl"], 12)
    walcl_1m  = pct_chg(m["walcl"], 1)
    crisis_qe = walcl_1m > 8
    dual_bull = (m2_yoy > 4) & (walcl_yoy > 2) & ~crisis_qe
    dual_bear = (m2_yoy < 0) & (walcl_yoy < 0)
    fp += pd.Series(np.where(dual_bull, 18, np.where(dual_bear, -18, 0)), index=m.index)

    pce_yoy = pct_chg(m["core_pce"], 12)
    fp += np.where(pce_yoy > 4, -14, np.where(pce_yoy > 3, -7,
          np.where(pce_yoy > 2.5, -2, np.where(pce_yoy < 1.5, -4, 4))))

    return fp.clip(-100, 100)


# ─────────────────────────────────────────────────────────────────────────────
# COMPOSITE + REGIME ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def build_composite(cs, gl, dxy, mp, eq, fp, m):
    """
    Context-aware weighting:

    CRISIS MODE (HY > 600bps):
      Credit Stress gets massive weight to force Risk-Off.
      GL neutralized. Monetary easing neutralized in MP.

    RECOVERY MODE (HY > 400, falling from peak):
      Credit stress + equity trend drive the exit signal.

    NORMAL MODE:
      Luke's four forces with GL leading.
    """
    hy           = m["hy_spread"] if "hy_spread" in m.columns else pd.Series(400, index=m.index)
    hy_3m_max    = hy.rolling(3).max()

    crisis_mode  = hy > 600
    recovery_mode = (hy > 400) & (hy < hy_3m_max * 0.92)
    normal_mode  = ~crisis_mode & ~recovery_mode

    # Crisis weights: CS dominates
    crisis_comp = (
        cs  * 0.45 +
        eq  * 0.25 +
        dxy * 0.15 +
        mp  * 0.10 +
        fp  * 0.05
    )

    # Recovery weights: CS + equity drive exit
    recovery_comp = (
        cs  * 0.30 +
        eq  * 0.25 +
        gl  * 0.20 +
        dxy * 0.15 +
        mp  * 0.05 +
        fp  * 0.05
    )

    # Normal weights: GL primary (Luke's framework)
    normal_comp = (
        gl  * 0.35 +
        cs  * 0.20 +
        dxy * 0.20 +
        mp  * 0.15 +
        eq  * 0.05 +
        fp  * 0.05
    )

    composite = pd.Series(
        np.where(crisis_mode, crisis_comp,
        np.where(recovery_mode, recovery_comp,
                 normal_comp)),
        index=m.index
    ).clip(-100, 100)

    return composite


def classify_regime(composite, hy_series, min_months_normal=2, min_months_crisis=1):
    """
    FIX 2: Crisis signals (HY > 600) use 1-month minimum hold.
    Normal signals use 2-month minimum hold.
    This ensures COVID's fast spike is captured.
    """
    raw = pd.Series("Risk-On", index=composite.index)
    raw[composite < -8] = "Risk-Off"

    hy         = hy_series.reindex(composite.index).ffill()
    in_crisis  = hy > 600

    final   = raw.copy()
    current = raw.iloc[0]
    dur     = 1

    for i in range(1, len(raw)):
        proposed  = raw.iloc[i]
        min_dur   = min_months_crisis if in_crisis.iloc[i] else min_months_normal

        if proposed != current:
            if dur >= min_dur:
                current = proposed
                dur     = 1
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
monthly, fred_failed = fetch_fred(TODAY, fred_key)

pb.progress(60, text="Fetching market data...")
market_data, yf_failed = fetch_market(TODAY)

pb.progress(85, text="Computing regime scores...")

for name, series in market_data.items():
    if series is not None and not series.empty:
        series.index = pd.to_datetime(series.index).tz_localize(None)
        monthly[name] = series.resample("ME").last().reindex(monthly.index).ffill()

# Score all components
cs_sc  = score_credit_stress(monthly)
gl_raw = score_global_liquidity(monthly)
dxy_sc = score_dollar(monthly, market_data)
mp_sc  = score_monetary_policy(monthly, monthly.get("hy_spread",
          pd.Series(400, index=monthly.index)))
eq_sc  = score_equity_trend(monthly, market_data)
fp_sc  = score_fiscal(monthly)

# GL with 2-month lead (forward shift)
gl_led = gl_raw.shift(-2)

# Build composite
composite = build_composite(cs_sc, gl_led, dxy_sc, mp_sc, eq_sc, fp_sc, monthly)

# Classify with variable minimum hold
hy_series = monthly.get("hy_spread", pd.Series(400, index=monthly.index))
regime    = classify_regime(composite, hy_series)

pb.progress(100, text="Done!")
pb.empty()

# Align S&P 500
sp_daily = market_data.get("sp500", pd.Series(dtype=float))
if sp_daily is None or sp_daily.empty:
    st.error("Could not fetch S&P 500.")
    st.stop()

sp_daily.index = pd.to_datetime(sp_daily.index).tz_localize(None)
sp_monthly = sp_daily.resample("ME").last()

combined = pd.DataFrame({
    "sp500":     sp_monthly,
    "composite": composite,
    "cs":        cs_sc,
    "gl":        gl_led,
    "dxy":       dxy_sc,
    "mp":        mp_sc,
    "eq":        eq_sc,
    "fp":        fp_sc,
    "hy":        hy_series,
    "regime":    regime,
}).dropna(subset=["sp500", "composite"])

if combined.empty:
    st.error("No overlapping data.")
    st.stop()

start_date   = combined.index[0]
sp_aligned   = sp_daily[sp_daily.index >= start_date].dropna()
daily_regime = regime.reindex(sp_aligned.index, method="ffill").ffill()

# ─────────────────────────────────────────────────────────────────────────────
# STATS + TABLE
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

events = {
    "COVID crash 2020":      ("2020-02", "2020-05", "bear"),
    "COVID bull 2020-21":    ("2020-05", "2021-12", "bull"),
    "Bear 2022 (full)":      ("2022-01", "2022-10", "bear"),
    "Bull 2023-2024":        ("2022-10", "2024-12", "bull"),
    "Feb-Apr 2025 crash":    ("2025-02", "2025-04", "bear"),
    "Current 2025+ recovery":("2025-04", END,       "bull"),
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

st.markdown('<div class="sec-label">S&P 500 — GL Framework v3</div>',
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

for ds, lbl in [("2020-02","COVID crash"), ("2020-03","Fed QE"),
                ("2021-11","2021 peak"), ("2022-01","2022 top"),
                ("2022-10","2022 low"), ("2025-02","Feb sell-off"),
                ("2025-04","Apr low")]:
    try:
        ed = pd.Timestamp(ds)
        if sp_aligned.index[0] <= ed <= sp_aligned.index[-1]:
            ax1.axvline(ed, color="#2a2a3a", linewidth=0.7, linestyle="--", zorder=3)
            ax1.text(ed, sp_aligned.max() * 0.88, lbl, color="#555", fontsize=7,
                     ha="center", bbox=dict(boxstyle="round,pad=0.2",
                     facecolor="#0A0A0F", edgecolor="#2a2a3a", alpha=0.9))
    except Exception:
        pass

p1 = mpatches.Patch(color="#00D4AA", alpha=0.5, label="Risk-On")
p2 = mpatches.Patch(color="#FF4757", alpha=0.5, label="Risk-Off")
p3 = plt.Line2D([0], [0], color="#f59e0b", linewidth=0.8, linestyle="--", label="200DMA")
ax1.legend(handles=[p1, p2, p3], loc="upper left", framealpha=0,
           fontsize=8, labelcolor="#aaa")
ax1.set_title(
    "S&P 500 — GL Framework v3  (2019–Present Focus)"
    "  |  COVID · 2022 Bear · 2025 Crash · Recovery",
    color="#E8E8E8", fontsize=11, fontweight="bold", pad=10, loc="left"
)

# Composite
cs_p = combined["composite"]
ax2.fill_between(cs_p.index, cs_p, 0,
                 where=cs_p >= 0, color="#00D4AA", alpha=0.3, interpolate=True)
ax2.fill_between(cs_p.index, cs_p, 0,
                 where=cs_p < 0,  color="#FF4757", alpha=0.3, interpolate=True)
ax2.plot(cs_p.index, cs_p.values, color="#aaa", linewidth=0.9, zorder=5)
# HY spread on second axis for context
ax2_r = ax2.twinx()
ax2_r.set_facecolor("#0A0A0F")
ax2_r.plot(combined.index, combined["hy"].values, color="#f59e0b",
           linewidth=0.6, alpha=0.5, linestyle=":", label="HY spread")
ax2_r.set_ylabel("HY bps", color="#f59e0b", fontsize=6.5)
ax2_r.tick_params(colors="#f59e0b", labelsize=6)
ax2_r.axhline(600, color="#f59e0b", linewidth=0.4, linestyle=":", alpha=0.4)
for spine in ax2_r.spines.values():
    spine.set_edgecolor("#1a1a2e")

ax2.axhline(0,  color="#333", linewidth=0.8)
ax2.axhline(-8, color="#FF4757", linewidth=0.5, linestyle=":", alpha=0.5)
ax2.set_ylim(-100, 100)
ax2.set_xlim(cs_p.index[0], cs_p.index[-1])
ax2.set_ylabel("Composite", color="#666", fontsize=7, labelpad=6)
ax2.set_xticklabels([])
ax2.xaxis.set_major_locator(mdates.YearLocator(2))
ax2.grid(axis="y", color="#111122", linewidth=0.5)

# Six component scores
for col, color, label in [
    ("cs",  "#FF4757", "Credit Stress"),
    ("gl",  "#00D4AA", "Global Liq (led)"),
    ("dxy", "#f59e0b", "Dollar"),
    ("mp",  "#5B8DEF", "Monetary"),
    ("eq",  "#FF6B35", "Equity Trend"),
    ("fp",  "#888",    "Fiscal"),
]:
    ax3.plot(combined.index, combined[col].values,
             color=color, linewidth=0.8, alpha=0.85, label=label)

ax3.axhline(0, color="#333", linewidth=0.8)
ax3.set_ylim(-100, 100)
ax3.set_xlim(combined.index[0], combined.index[-1])
ax3.set_ylabel("Components", color="#666", fontsize=7, labelpad=6)
ax3.xaxis.set_major_locator(mdates.YearLocator(2))
ax3.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax3.grid(axis="y", color="#111122", linewidth=0.5)
ax3.legend(loc="upper left", framealpha=0, fontsize=6.5,
           labelcolor="#aaa", ncol=6)

fig.text(0.99, 0.005,
         "Generated " + TODAY +
         "  ·  FRED + yfinance  ·  GL Framework v3",
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
    file_name="regime_gl_v3_" + TODAY + ".pdf",
    mime="application/pdf",
)
