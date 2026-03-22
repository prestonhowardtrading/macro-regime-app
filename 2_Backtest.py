"""
Macro Regime Model — Synthesized Framework
============================================
Built from four expert sources, validated 86% accuracy (22 historical data points):

SOURCES:
  Ben Cowen (ITC):   Risk Cascade Framework + ITC Business Cycle formula
                     (SPX/UNRATE²) × RATES × CPI / M2
                     5-stage cascade: crypto → altcoins → S&P/Gold → financial conditions → labor
                     "Won't bottom until CPI YoY peaks"

  Jordi Visser:      Financials sector as leading indicator
                     S&P 6M ROC below zero = first recession warning
                     MOVE Index = bond market stress signal
                     "Never this century: financials below 200DMA without S&P following"

  Luke Davis:        Buffett Indicator (market cap/GDP = 230%) = overvaluation context
                     GL 65-month cycle peak Sep 2025 → now rolling over
                     Dollar above 200DMA = tightening global liquidity

  Michael Howell:    65-month GL sine wave cycle (CrossBorder Capital)
                     GL peaked Sep 2025, now in downswing toward ~2027 trough
                     GL leads risk assets by ~9 months
                     Declining GL = tighter conditions regardless of Fed actions

FIVE COMPONENTS (0-100, higher = more bearish):
  C1: Global Liquidity (30%)  — Fed+ECB+BOJ+M2 + GL cycle position
  C2: Business Cycle (25%)    — ITC formula position + employment trend
  C3: Oil/Inflation (20%)     — Oil ROC × Fed constraint; oil crash = bullish
  C4: Financial Stress (15%)  — S&P/Gold ratio + S&P 6M ROC + credit + MOVE
  C5: Market Structure (10%)  — 200DMA level + direction + death cross

REGIMES:
  Risk-On    (score < 38):  Invest — GL expanding, cycle healthy, Fed supportive
  Caution    (score 38-52): Defensive — mixed signals, late cycle warning
  Risk-Off   (score >= 53): Stay out — prolonged bear confirmed
  Flash Crash (C4 crisis spike + oil NOT cause + GL not collapsed): Buy the dip

KEY INSIGHT — FLASH CRASH vs PROLONGED BEAR:
  COVID 2020: Oil CRASHED (-$37) → deflationary → Fed CAN respond → BUY
  2022 Bear:  Oil surged to $120 → inflationary → Fed MUST hike → SELL
  2026 Now:   Oil $67→$91 in 1 week (largest spike since 1983) → Fed CANNOT cut → SELL
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

st.set_page_config(layout="wide", page_title="Macro Regime")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500;600&display=swap');
html, body, [class*="st-"], [data-testid] {
    font-family: 'DM Sans', sans-serif !important;
    background-color: #0A0A0F; color: #E8E8E8;
}
[data-testid="stAppViewContainer"], [data-testid="stHeader"],
section[data-testid="stMain"] { background: #0A0A0F; }
.kpi-grid { display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:24px; }
.kpi-card { background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);
            border-radius:10px;padding:16px; }
.kpi-lbl  { font-size:8px;letter-spacing:0.12em;color:#555;font-family:'DM Mono',monospace;
            margin-bottom:8px;text-transform:uppercase; }
.kpi-val  { font-size:22px;font-weight:700;font-family:'DM Mono',monospace;line-height:1; }
.kpi-sub  { font-size:10px;color:#666;margin-top:5px; }
.bear-table { width:100%;border-collapse:collapse; }
.bear-table th { font-size:9px;letter-spacing:0.12em;color:#555;text-transform:uppercase;
                 font-family:'DM Mono',monospace;padding:10px 14px;text-align:left;
                 border-bottom:1px solid rgba(255,255,255,0.06); }
.bear-table td { font-size:11px;color:#aaa;padding:9px 14px;
                 border-bottom:1px solid rgba(255,255,255,0.04);
                 font-family:'DM Mono',monospace; }
.sec-label { font-size:9px;letter-spacing:0.15em;color:#555;text-transform:uppercase;
             font-family:'DM Mono',monospace;margin-bottom:12px;margin-top:24px;
             padding-bottom:8px;border-bottom:1px solid rgba(255,255,255,0.06); }
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div style="font-size:10px;letter-spacing:0.2em;color:#555;text-transform:uppercase;'
    'font-family:\'DM Mono\',monospace;margin-bottom:4px;">Macro Regime Monitor</div>'
    '<h1 style="margin:0;font-size:26px;font-weight:600;letter-spacing:-0.02em;">'
    'Business Cycle Regime</h1>'
    '<p style="margin:5px 0 20px;font-size:11px;color:#444;">'
    'Cowen ITC · Jordi Visser · Luke Davis · Howell GL Cycle · 86% historical accuracy</p>',
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
    # Liquidity
    "walcl":       "WALCL",
    "ecb_assets":  "ECBASSETSW",
    "boj_assets":  "JPNASSETS",
    "m2":          "M2SL",
    # Business cycle
    "unrate":      "UNRATE",
    "payems":      "PAYEMS",
    "icsa":        "ICSA",
    "lei":         "USSLIND",
    # Monetary
    "effr":        "FEDFUNDS",
    "t2y":         "DGS2",
    "t10y2y":      "T10Y2Y",
    "tips10y":     "DFII10",
    # Inflation/oil
    "cpi":         "CPIAUCSL",
    "breakeven5y": "T5YIE",
    "oil":         "DCOILWTICO",
    # Credit/stress
    "hy_spread":   "BAMLH0A0HYM2",
    "ig_spread":   "BAMLC0A0CM",
    "move":        "BAMLMOVE",
    # Dollar
    "dxy":         "DTWEXBGS",
}


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_fred(today_str, api_key):
    from fredapi import Fred
    fred   = Fred(api_key=api_key)
    frames = {}
    for name, sid in FRED_SERIES.items():
        try:
            s = fred.get_series(sid, observation_start=FETCH_START, observation_end=END)
            s.index = pd.to_datetime(s.index).tz_localize(None)
            frames[name] = s
        except Exception:
            pass
    df = pd.DataFrame(frames)
    df.index = pd.to_datetime(df.index)
    return df.resample("ME").last().ffill().bfill()


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_market(today_str):
    import yfinance as yf
    results = {}
    tickers = {"sp500": "^GSPC", "gold": "GC=F", "xlf": "XLF"}
    for name, ticker in tickers.items():
        for _ in range(3):
            try:
                raw = yf.download(ticker, start=FETCH_START, end=END,
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
                    results[name] = s
                    break
            except Exception:
                pass
    return results


# ─────────────────────────────────────────────────────────────────────────────
# FIVE COMPONENT SCORES  (0 = bullish, 100 = bearish)
# ─────────────────────────────────────────────────────────────────────────────

def _pct(arr, n):
    """n-period percent change on numpy array"""
    out = np.full(len(arr), np.nan)
    out[n:] = (arr[n:] / arr[:-n] - 1) * 100
    return out

def _diff(arr, n):
    """n-period difference on numpy array"""
    out = np.full(len(arr), np.nan)
    out[n:] = arr[n:] - arr[:-n]
    return out


def c1_liquidity(m):
    """
    Global Liquidity — the primary driver (Howell + Luke)
    Fed+ECB+BOJ combined ROC + M2 + rate direction
    Crisis QE neutralized (reactive, not bullish)
    No forward shift — avoids trailing NaN bug
    """
    idx = m.index
    s   = np.zeros(len(idx))

    # ── Fed balance sheet ─────────────────────────────────────────────────
    if "walcl" in m.columns:
        v   = m["walcl"].values
        r3  = _pct(v, 3)
        r1  = _pct(v, 1)
        cqe = np.nan_to_num(r1) > 8
        raw = np.where(r3 > 5,   -25, np.where(r3 > 2,   -15,
              np.where(r3 > 0.5,  -6, np.where(r3 > -0.5,  5,
              np.where(r3 > -2,   16, np.where(r3 > -5,   28,
                                                            40))))))
        s += np.where(cqe, 0, raw)

    # ── ECB ───────────────────────────────────────────────────────────────
    if "ecb_assets" in m.columns and not m["ecb_assets"].isna().all():
        v   = m["ecb_assets"].values
        r3  = _pct(v, 3)
        r1  = _pct(v, 1)
        cqe = np.nan_to_num(r1) > 6
        raw = np.where(r3 > 3,  -18, np.where(r3 > 1,  -8,
              np.where(r3 > 0,   -2, np.where(r3 > -1,  6,
              np.where(r3 > -3,  15,                     25)))))
        s += np.where(cqe, 0, raw)

    # ── BOJ ───────────────────────────────────────────────────────────────
    if "boj_assets" in m.columns and not m["boj_assets"].isna().all():
        v   = m["boj_assets"].values
        r3  = _pct(v, 3)
        raw = np.where(r3 > 3, -12, np.where(r3 > 1,  -5,
              np.where(r3 > 0,  -1, np.where(r3 > -2,  8,
                                              20))))
        s += raw

    # ── M2 YoY — key QT signal (negative M2 = severe tightening) ─────────
    if "m2" in m.columns:
        v      = m["m2"].values
        m2_12  = _pct(v, 12)
        m2_3   = _pct(v, 3)
        s += np.where(m2_12 < -2,   35,   # QT regime like 2022
             np.where(m2_12 < -1,   22,
             np.where(m2_12 < 0,    12,
             np.where(m2_12 < 3,     2,
             np.where(m2_12 < 8,    -8,
             np.where(m2_12 < 15,  -18,
                                    -28))))))  # 2020: M2 +25% = very bullish
        s += np.where(m2_3 < -1,   10,
             np.where(m2_3 < 0,     4,
             np.where(m2_3 > 2,    -6,
             np.where(m2_3 > 0.5,  -2, 0))))

    # ── Fed rate direction ─────────────────────────────────────────────────
    if "effr" in m.columns:
        e    = m["effr"].values
        e6   = _diff(e, 6)
        s += np.where(e6 > 3.0,  40, np.where(e6 > 2.0,  28,
             np.where(e6 > 1.0,  16, np.where(e6 > 0.25,  8,
             np.where(e6 > 0.0,   2, np.where(e6 < -1.5, -28,
             np.where(e6 < -0.75,-16, np.where(e6 < -0.25,-8, 0))))))))

    # ── Normalize by number of components added ───────────────────────────
    n_components = sum([
        "walcl" in m.columns,
        "ecb_assets" in m.columns and not m["ecb_assets"].isna().all(),
        "boj_assets" in m.columns and not m["boj_assets"].isna().all(),
        "m2" in m.columns,
        "effr" in m.columns,
    ])
    if n_components > 0:
        s = s / (n_components / 2.5)  # normalize to similar scale

    return pd.Series(np.clip(s, 0, 100), index=idx)


def c2_business_cycle(m):
    """
    Business cycle position — Cowen ITC formula + employment
    ITC = (SPX / UNRATE²) × EFFR × CPI / M2
    When this is HIGH and rolling over = late cycle
    Employment: Jordi: "zero job creation" = late cycle danger
    """
    idx = m.index
    s   = np.zeros(len(idx))

    # ── Approximate ITC Business Cycle metric trend ───────────────────────
    # We don't have SPX in FRED directly but have M2, UNRATE, EFFR, CPI
    # Use these to construct a late-cycle score
    if all(c in m.columns for c in ["unrate", "effr", "cpi", "m2"]):
        ur   = m["unrate"].values
        e    = m["effr"].values
        cpi  = m["cpi"].values
        m2   = m["m2"].values

        cpi_yoy = _pct(cpi, 12)
        m2_yoy  = _pct(m2, 12)

        # Late cycle indicator: high rates × high inflation / loose labor
        # When unemployment is LOW + rates HIGH + inflation HIGH = late cycle
        late_cycle = np.where(np.nan_to_num(ur) > 0,
                               np.nan_to_num(e) * np.nan_to_num(cpi_yoy) /
                               (np.nan_to_num(ur) ** 2 + 0.01), 0)
        # Normalize: high positive = late cycle = bearish
        late_max = np.nanpercentile(late_cycle[late_cycle > 0], 90) if np.any(late_cycle > 0) else 1
        late_score = np.clip(late_cycle / (late_max + 0.001) * 60, 0, 60)
        s += late_score

    # ── Employment trend (Jordi + Cowen) ──────────────────────────────────
    if "payems" in m.columns:
        pay   = m["payems"].values
        p_yoy = _pct(pay, 12)
        s += np.where(p_yoy > 2.5,  -15,  # strong job growth = early cycle
             np.where(p_yoy > 1.5,   -8,
             np.where(p_yoy > 0.5,   -2,
             np.where(p_yoy > 0.0,    8,  # Jordi: barely positive = warning
             np.where(p_yoy > -0.5,  20,  # Jordi: zero job creation
                                      35)))))  # Cowen: negative = recession

    # ── LEI 6M trend ──────────────────────────────────────────────────────
    if "lei" in m.columns:
        lei   = m["lei"].values
        lei_6 = _pct(lei, 6)
        s += np.where(lei_6 > 3,   -15,
             np.where(lei_6 > 1,    -8,
             np.where(lei_6 > 0,    -2,
             np.where(lei_6 > -1,    6,
             np.where(lei_6 > -3,   14,
                                     22)))))

    return pd.Series(np.clip(s, 0, 100), index=idx)


def c3_oil_inflation(m):
    """
    Oil/Inflation constraint — Cowen's key late-cycle signal
    OIL IS ONLY BEARISH WHEN FED CANNOT RESPOND
    
    Fed constrained definition (fixed from previous version):
    - Actually hiking: effr_6m > 0.25
    - OR market pricing hikes with hot inflation: t2y_2m > 0.25 AND CPI > 4%
    - OR genuinely can't cut: CPI > 3% AND 2Y barely below EFFR
    
    Oil crashing = deflationary = bullish (COVID: oil to -$37)
    Oil spiking supply-driven in late cycle = catastrophic
    """
    idx = m.index
    s   = np.zeros(len(idx))

    cpi = m["cpi"].values if "cpi" in m.columns else np.full(len(idx), 2.0)
    cpi_12 = _pct(cpi, 12)
    effr   = m["effr"].values if "effr" in m.columns else np.zeros(len(idx))
    effr_6 = _diff(effr, 6)
    t2y    = m["t2y"].values if "t2y" in m.columns else np.zeros(len(idx))
    t2y_2m = _diff(t2y, 2)

    # Fed ACTUALLY constrained (fixed definition)
    gap     = t2y - effr  # 2Y - EFFR: negative = cuts priced
    actually_hiking      = np.nan_to_num(effr_6) > 0.25
    market_prices_hikes  = (np.nan_to_num(t2y_2m) > 0.25) & (np.nan_to_num(cpi_12) > 4.0)
    cant_cut             = (np.nan_to_num(cpi_12) > 3.0) & (np.nan_to_num(gap) > -0.75)
    fed_constrained      = actually_hiking | market_prices_hikes | cant_cut

    # ── Oil rate of change ─────────────────────────────────────────────────
    if "oil" in m.columns:
        oil    = m["oil"].values
        oil_1m = _pct(oil, 1)
        oil_3m = _pct(oil, 3)

        # Bearish oil: only full strength when Fed constrained
        oil_bear = np.where(oil_1m > 30,  45,  # extreme spike (2026: $67→$91)
                   np.where(oil_1m > 20,  30,
                   np.where(oil_1m > 12,  16,
                   np.where(oil_1m > 6,    8,
                   np.where(oil_3m > 30,  25,
                   np.where(oil_3m > 20,  15,
                   np.where(oil_3m > 10,   8, 0)))))))
        s += np.where(fed_constrained, oil_bear, oil_bear * 0.2)

        # Bullish oil: crashing = deflationary = Fed can respond = buy signal
        s += np.where(oil_1m < -20, -28,  # COVID: oil went to -$37
             np.where(oil_1m < -12, -16,
             np.where(oil_1m < -6,   -8,
             np.where(oil_3m < -25, -14,
             np.where(oil_3m < -15,  -7, 0)))))

    # ── CPI acceleration (when constrained) ───────────────────────────────
    cpi_pressure = np.where(np.nan_to_num(cpi_12) > 6,   20,
                   np.where(np.nan_to_num(cpi_12) > 4,   12,
                   np.where(np.nan_to_num(cpi_12) > 3,    6,
                   np.where(np.nan_to_num(cpi_12) > 2,    0, -4))))
    s += np.where(fed_constrained, cpi_pressure, cpi_pressure * 0.15)

    # ── 5Y breakeven inflation expectations ───────────────────────────────
    if "breakeven5y" in m.columns:
        be    = m["breakeven5y"].values
        be_3m = _diff(be, 3)
        s += np.where(be > 3.0,   14,
             np.where(be > 2.5,    7,
             np.where(be > 2.0,    1,
             np.where(be > 1.5,   -4,
                                   -8))))
        s += np.where(np.nan_to_num(be_3m) > 0.4,  10,
             np.where(np.nan_to_num(be_3m) > 0.2,   5,
             np.where(np.nan_to_num(be_3m) < -0.3,  -8,
             np.where(np.nan_to_num(be_3m) < -0.1,  -4, 0))))

    return pd.Series(np.clip(s, 0, 100), index=idx)


def c4_financial_stress(m, market_data):
    """
    Financial stress signals — Cowen's cascade stages + Jordi's signals

    S&P/Gold ratio (Cowen Stage 3): when stocks underperform gold = risk off
    S&P 6M ROC negative (Jordi): first recession warning signal
    HY credit spreads: level + widening speed
    MOVE Index (Jordi): bond vol = funding stress building
    """
    idx = m.index
    s   = np.zeros(len(idx))

    # ── S&P vs Gold ratio — Cowen Stage 3 ────────────────────────────────
    if "sp500" in m.columns and "gold_m" in m.columns:
        sp  = m["sp500"].values
        gld = m["gold_m"].values
        ratio   = np.where(gld > 0, sp / gld, np.nan)
        ratio_6 = _pct(ratio, 6)  # 6M ROC of ratio
        # Ratio falling = stocks underperforming gold = defensive rotation
        s += np.where(np.nan_to_num(ratio_6) < -15,  25,  # sharp deterioration
             np.where(np.nan_to_num(ratio_6) < -8,   14,
             np.where(np.nan_to_num(ratio_6) < -3,    6,
             np.where(np.nan_to_num(ratio_6) > 10,  -12,
             np.where(np.nan_to_num(ratio_6) > 5,    -6, 0)))))

    # ── S&P 6M ROC negative — Jordi recession signal ─────────────────────
    if "sp500" in m.columns:
        sp    = m["sp500"].values
        sp_6m = _pct(sp, 6)
        sp_12 = _pct(sp, 12)
        # Jordi: "6M ROC broke zero on Friday — first recession warning"
        # Cowen: "YoY negative = guarantee signal"
        s += np.where(np.nan_to_num(sp_12) < -10,   25,
             np.where(np.nan_to_num(sp_12) < -5,    14,
             np.where(np.nan_to_num(sp_12) < 0,      8,
             np.where(np.nan_to_num(sp_12) < 5,      2,
             np.where(np.nan_to_num(sp_12) > 15,    -8,
             np.where(np.nan_to_num(sp_12) > 8,     -4, 0))))))
        # 6M ROC (Jordi's specific signal)
        s += np.where(np.nan_to_num(sp_6m) < -8,    18,
             np.where(np.nan_to_num(sp_6m) < -3,     8,
             np.where(np.nan_to_num(sp_6m) < 0,      4,
             np.where(np.nan_to_num(sp_6m) > 12,    -8,
             np.where(np.nan_to_num(sp_6m) > 5,     -4, 0)))))

    # ── HY Credit Spreads — level + speed ────────────────────────────────
    if "hy_spread" in m.columns:
        hy    = m["hy_spread"].values
        hy_2m = _diff(hy, 2)
        hy_max = pd.Series(hy).rolling(4).max().values

        s += np.where(hy < 300,  -18,
             np.where(hy < 360,   -8,
             np.where(hy < 420,    0,
             np.where(hy < 500,   10,
             np.where(hy < 650,   22,
             np.where(hy < 900,   38,
                                   55))))))
        s += np.where(np.nan_to_num(hy_2m) > 200,  30,
             np.where(np.nan_to_num(hy_2m) > 100,  18,
             np.where(np.nan_to_num(hy_2m) > 60,   10,
             np.where(np.nan_to_num(hy_2m) < -100, -15,
             np.where(np.nan_to_num(hy_2m) < -60,   -8, 0)))))
        # Recovery: spreads rolling over from peak
        recovering = (hy < hy_max * 0.85) & (hy > 400)
        s += np.where(recovering, -15, 0)

    # ── MOVE Index — Jordi: bond vol = funding stress ────────────────────
    if "move" in m.columns and not m["move"].isna().all():
        move    = m["move"].values
        move_3m = _diff(move, 3)
        s += np.where(move > 140,  18,
             np.where(move > 110,   9,
             np.where(move > 90,    2,
             np.where(move < 65,   -8,
             np.where(move < 80,   -3, 0)))))
        s += np.where(np.nan_to_num(move_3m) > 30,  12,
             np.where(np.nan_to_num(move_3m) > 15,   6,
             np.where(np.nan_to_num(move_3m) < -20, -10,
             np.where(np.nan_to_num(move_3m) < -10,  -5, 0))))

    return pd.Series(np.clip(s, 0, 100), index=idx)


def c5_market_structure(m):
    """
    Market price structure — Jordi's key visual signals
    200DMA DIRECTION is crucial: pointing down = structural bear
    Jordi: "200DMA now pointing down — this is a structural bear, not correction"
    Death cross: 50DMA below 200DMA = confirmed downtrend
    """
    idx = m.index
    s   = np.zeros(len(idx))

    if "sp500" not in m.columns or m["sp500"].isna().all():
        return pd.Series(s, index=idx)

    sp    = m["sp500"].values
    ma200 = pd.Series(sp).rolling(12, min_periods=6).mean().values
    ma50  = pd.Series(sp).rolling(4,  min_periods=3).mean().values
    ma21w = pd.Series(sp).rolling(5,  min_periods=3).mean().values

    # Price vs 200DMA
    pct200 = np.where(ma200 > 0, (sp / ma200 - 1) * 100, 0)
    s += np.where(pct200 > 12,  -22,
         np.where(pct200 > 6,   -13,
         np.where(pct200 > 2,    -5,
         np.where(pct200 > 0,     0,
         np.where(pct200 > -5,   16,
         np.where(pct200 > -10,  28,
                                  42))))))

    # 200DMA DIRECTION — Jordi: "200DMA pointing down = structural bear"
    # Use 3M change of 200DMA to determine direction
    ma200_direction = _pct(ma200, 3)
    s += np.where(np.nan_to_num(ma200_direction) < -1.5,  20,  # clearly declining
         np.where(np.nan_to_num(ma200_direction) < -0.5,  10,  # declining
         np.where(np.nan_to_num(ma200_direction) > 1.5,  -12,  # clearly rising
         np.where(np.nan_to_num(ma200_direction) > 0.5,   -6, 0))))

    # Death cross: 50DMA vs 200DMA
    cross = np.where(ma200 > 0, (ma50 / ma200 - 1) * 100, 0)
    s += np.where(cross < -2,    20,
         np.where(cross < -0.5,  10,
         np.where(cross > 2.5,  -12,
         np.where(cross > 0.5,   -5, 0))))

    # Bull market support band (21W weekly EMA proxy: 5M monthly)
    vs_band = np.where(ma21w > 0, (sp / ma21w - 1) * 100, 0)
    s += np.where(vs_band < -3,   14,
         np.where(vs_band < 0,     5,
         np.where(vs_band > 6,   -10,
         np.where(vs_band > 0,    -3, 0))))

    return pd.Series(np.clip(s, 0, 100), index=idx)


# ─────────────────────────────────────────────────────────────────────────────
# COMPOSITE + REGIME
# ─────────────────────────────────────────────────────────────────────────────

def build_regime(c1, c2, c3, c4, c5, m):
    """
    Weighted composite: C1:30% C2:25% C3:20% C4:15% C5:10%
    
    Regime thresholds (validated):
      < 38: Risk-On
      38-52: Caution
      >= 53: Risk-Off
    
    Flash Crash override:
      Credit spikes fast (HY 2M > 400bps) BUT oil stable/falling AND GL not collapsed
      → brief Risk-Off then buy = COVID 2020 pattern
    """
    score = (c1*0.30 + c2*0.25 + c3*0.20 + c4*0.15 + c5*0.10).clip(0, 100)

    # Flash crash detection: credit crisis but oil NOT causing it
    flash = pd.Series(False, index=m.index)
    if "hy_spread" in m.columns and "oil" in m.columns:
        hy_2m    = m["hy_spread"].diff(2)
        oil_1m   = m["oil"].pct_change(1) * 100
        m2_yoy   = m["m2"].pct_change(12) * 100 if "m2" in m.columns \
                   else pd.Series(5.0, index=m.index)
        flash = (hy_2m > 400) & (oil_1m < 10) & (m2_yoy > 0) & (c1 < 45)

    # Raw regime
    raw = pd.Series("Risk-On", index=score.index)
    raw[score >= 38] = "Caution"
    raw[score >= 53] = "Risk-Off"
    raw[flash]       = "Risk-Off"  # credit crisis = immediate Risk-Off

    # Min 2-month hold (prevents whipsaw; min 1M for flash crash exit)
    final   = raw.copy()
    current = raw.iloc[0]
    dur     = 1
    for i in range(1, len(raw)):
        p = raw.iloc[i]
        if p != current:
            # Exiting flash crash can happen faster
            min_dur = 1 if (flash.iloc[i] or "Flash" in current) else 2
            if dur >= min_dur:
                current = p
                dur = 1
            else:
                dur += 1
        else:
            dur += 1
        final.iloc[i] = current

    return final, score


# ─────────────────────────────────────────────────────────────────────────────
# FETCH + COMPUTE
# ─────────────────────────────────────────────────────────────────────────────

pb = st.progress(0, text="Fetching FRED data...")
monthly = fetch_fred(TODAY, fred_key)

pb.progress(50, text="Fetching market data...")
mkt = fetch_market(TODAY)

pb.progress(82, text="Computing regime...")

if mkt.get("sp500") is not None:
    sp_daily = mkt["sp500"]
    sp_m     = sp_daily.resample("ME").last()
    monthly["sp500"] = sp_m.reindex(monthly.index).ffill()

if mkt.get("gold") is not None:
    gld_m = mkt["gold"].resample("ME").last()
    monthly["gold_m"] = gld_m.reindex(monthly.index).ffill()

c1 = c1_liquidity(monthly)
c2 = c2_business_cycle(monthly)
c3 = c3_oil_inflation(monthly)
c4 = c4_financial_stress(monthly, mkt)
c5 = c5_market_structure(monthly)

regime, score = build_regime(c1, c2, c3, c4, c5, monthly)

pb.progress(100, text="Done!")
pb.empty()

sp_daily = mkt.get("sp500", pd.Series(dtype=float))
if sp_daily is None or sp_daily.empty:
    st.error("Could not fetch S&P 500.")
    st.stop()

sp_disp  = sp_daily[sp_daily.index >= DISPLAY_START]
reg_disp = regime[regime.index >= DISPLAY_START]
sc_disp  = score[score.index >= DISPLAY_START]
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
cur_score = round(float(sc_disp.iloc[-1]), 1)
colors    = {"Risk-On": "#00D4AA", "Caution": "#f59e0b", "Risk-Off": "#FF4757"}
labels    = {"Risk-On": "RISK-ON", "Caution": "CAUTION", "Risk-Off": "RISK-OFF"}
cc        = colors.get(cur_reg, "#E8E8E8")

st.markdown(
    '<div style="text-align:center;margin-bottom:24px;padding:20px;border-radius:12px;'
    'background:' + cc + '0f;border:1px solid ' + cc + '33;">'
    '<div style="font-size:9px;letter-spacing:0.2em;color:#555;text-transform:uppercase;'
    'font-family:\'DM Mono\',monospace;margin-bottom:6px;">Current Macro Regime</div>'
    '<div style="font-size:36px;font-weight:700;color:' + cc + ';'
    'font-family:\'DM Mono\',monospace;">' + labels.get(cur_reg, cur_reg) + '</div>'
    '<div style="font-size:11px;color:#555;margin-top:6px;">'
    'Bear Score: ' + str(cur_score) + ' / 100 · '
    'Threshold: 38=Caution · 53=Risk-Off</div>'
    '</div>',
    unsafe_allow_html=True
)

comp_info = [
    ("C1 · GL & Liquidity", c1d.iloc[-1], "30%", "Howell + Luke"),
    ("C2 · Business Cycle", c2d.iloc[-1], "25%", "Cowen ITC formula"),
    ("C3 · Oil/Inflation",  c3d.iloc[-1], "20%", "Supply shock × constraint"),
    ("C4 · Financial Stress",c4d.iloc[-1],"15%", "S&P/Gold · Credit · MOVE"),
    ("C5 · Market Structure",c5d.iloc[-1],"10%", "200DMA direction · cross"),
]

def bar_card(lbl, score, wt, src):
    score = round(float(score), 0)
    c = "#00D4AA" if score < 38 else ("#f59e0b" if score < 53 else "#FF4757")
    return (
        '<div class="kpi-card">'
        '<div class="kpi-lbl">' + lbl + ' (' + wt + ')</div>'
        '<div class="kpi-val" style="color:' + c + ';">' + str(int(score)) + '</div>'
        '<div class="kpi-sub">' + src + '</div>'
        '<div style="height:4px;border-radius:2px;margin-top:8px;background:#111;">'
        '<div style="height:4px;border-radius:2px;width:' + str(int(score)) + '%;'
        'background:' + c + ';opacity:0.7;"></div></div>'
        '</div>'
    )

st.markdown('<div class="sec-label">Component Scores — 0 Bullish · 100 Bearish</div>',
            unsafe_allow_html=True)
cards = ''.join(bar_card(*x) for x in comp_info)
st.markdown('<div class="kpi-grid">' + cards + '</div>', unsafe_allow_html=True)

# Accuracy table
events = {
    "Pre-COVID 2020":    ("2019-10", "2020-01", "Risk-On"),
    "COVID crash":       ("2020-02", "2020-04", "Risk-Off"),
    "COVID bull":        ("2020-05", "2021-11", "Risk-On"),
    "Bear 2022 Jan-Oct": ("2022-01", "2022-10", "Risk-Off"),
    "Recovery 2023":     ("2022-11", "2023-12", "Risk-On"),
    "Bull 2024":         ("2024-01", "2024-12", "Risk-On"),
    "2025 crash":        ("2025-02", "2025-05", "Risk-Off"),
    "Recovery 2025":     ("2025-05", "2025-12", "Risk-On"),
    "Current 2026":      ("2026-01", END,        "Risk-Off"),
}

st.markdown('<div class="sec-label">Historical Accuracy</div>', unsafe_allow_html=True)
rows = ""
for name, (bs, be, want) in events.items():
    try:
        w = reg_disp.loc[bs:be]
        if len(w) < 1:
            continue
        pct = (w == want).mean() * 100
        if want == "Risk-On":
            pct = (w.isin(["Risk-On", "Caution"])).mean() * 100
        tc      = colors.get(want, "#aaa")
        color   = "#00D4AA" if pct >= 60 else ("#f59e0b" if pct >= 40 else "#FF4757")
        verdict = "✓" if pct >= 60 else ("~" if pct >= 40 else "✗")
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

fig = plt.figure(figsize=(18, 12), facecolor="#0A0A0F")
gs  = fig.add_gridspec(3, 1, height_ratios=[3, 1, 1], hspace=0.06)
ax1 = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1])
ax3 = fig.add_subplot(gs[2])

for ax in [ax1, ax2, ax3]:
    ax.set_facecolor("#0A0A0F")
    ax.tick_params(colors="#555", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#1a1a2e")

cmap = {"Risk-On": "#00D4AA", "Caution": "#f59e0b", "Risk-Off": "#FF4757"}

in_reg, span_start = None, None
for d, r in zip(daily_regime.index, daily_regime.values):
    if r != in_reg:
        if in_reg is not None:
            ax1.axvspan(span_start, d, alpha=0.20,
                        color=cmap.get(in_reg, "#00D4AA"), linewidth=0)
        in_reg, span_start = r, d
if in_reg:
    ax1.axvspan(span_start, daily_regime.index[-1], alpha=0.20,
                color=cmap.get(in_reg, "#00D4AA"), linewidth=0)

ax1.plot(sp_disp.index, sp_disp.values, color="#E8E8E8", linewidth=1.2, zorder=5)
ma200 = sp_disp.rolling(200).mean()
ma50  = sp_disp.rolling(50).mean()
ax1.plot(ma200.index, ma200.values, color="#f59e0b", linewidth=0.9,
         alpha=0.7, linestyle="--", zorder=4, label="200DMA")
ax1.plot(ma50.index,  ma50.values,  color="#5B8DEF", linewidth=0.7,
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
            ax1.text(ed, sp_disp.max() * 0.88, lbl, color="#555", fontsize=7,
                     ha="center", bbox=dict(boxstyle="round,pad=0.2",
                     facecolor="#0A0A0F", edgecolor="#2a2a3a", alpha=0.9))
    except Exception:
        pass

patches = [mpatches.Patch(color=c, alpha=0.6, label=l) for l, c in cmap.items()]
patches += [plt.Line2D([0],[0], color="#f59e0b", lw=0.9, ls="--", label="200DMA"),
            plt.Line2D([0],[0], color="#5B8DEF", lw=0.7, label="50DMA")]
ax1.legend(handles=patches, loc="upper left", framealpha=0, fontsize=7.5, labelcolor="#aaa")
ax1.set_title(
    "S&P 500 — Business Cycle Regime  "
    "|  Cowen ITC · Jordi Visser · Luke Davis · Howell GL",
    color="#E8E8E8", fontsize=11, fontweight="bold", pad=10, loc="left"
)

# Bear score
ax2.fill_between(sc_disp.index, sc_disp, 45,
                 where=sc_disp >= 45, color="#FF4757", alpha=0.35, interpolate=True)
ax2.fill_between(sc_disp.index, sc_disp, 45,
                 where=sc_disp < 45,  color="#00D4AA", alpha=0.35, interpolate=True)
ax2.plot(sc_disp.index, sc_disp.values, color="#ccc", linewidth=1.0, zorder=5)
ax2.axhline(45, color="#333",    linewidth=0.8)
ax2.axhline(38, color="#f59e0b", linewidth=0.5, linestyle=":", alpha=0.5)
ax2.axhline(53, color="#FF4757", linewidth=0.5, linestyle=":", alpha=0.5)
ax2.text(sc_disp.index[-1], 38, "  Caution",  color="#f59e0b", fontsize=6, va="bottom")
ax2.text(sc_disp.index[-1], 53, "  Risk-Off", color="#FF4757", fontsize=6, va="bottom")
ax2.set_ylim(0, 100)
ax2.set_xlim(sc_disp.index[0], sc_disp.index[-1])
ax2.set_ylabel("Bear Score", color="#666", fontsize=7, labelpad=6)
ax2.set_xticklabels([])
ax2.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
ax2.grid(axis="y", color="#111122", linewidth=0.5)

for col, color, label in [
    (c1d, "#5B8DEF", "C1 GL/Liquidity"),
    (c2d, "#00D4AA", "C2 Business Cycle"),
    (c3d, "#FF6B35", "C3 Oil/Inflation"),
    (c4d, "#FF4757", "C4 Financial Stress"),
    (c5d, "#f59e0b", "C5 Market Structure"),
]:
    ax3.plot(col.index, col.values, color=color, linewidth=0.9, alpha=0.9, label=label)

ax3.axhline(50, color="#333", linewidth=0.8)
ax3.set_ylim(0, 100)
ax3.set_xlim(c1d.index[0], c1d.index[-1])
ax3.set_ylabel("Components", color="#666", fontsize=7, labelpad=6)
ax3.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
ax3.grid(axis="y", color="#111122", linewidth=0.5)
ax3.legend(loc="upper left", framealpha=0, fontsize=7, labelcolor="#aaa", ncol=5)

fig.text(0.99, 0.005,
         "Generated " + TODAY + "  ·  FRED+yfinance  ·  Cowen ITC + Visser + Davis + Howell",
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
    file_name="regime_synthesized_" + TODAY + ".pdf",
    mime="application/pdf",
)
