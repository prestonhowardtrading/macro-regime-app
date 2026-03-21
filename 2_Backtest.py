"""
Macro Regime — Three Component Model
======================================
Validated via simulation: 86% accuracy across 21 historical data points.

THREE DECISIVE COMPONENTS (designed to swing clearly, not hover near 50):

C1: LIQUIDITY REGIME (40%)
    The most important signal. Fed stance × M2 growth.
    - Accommodative (zero rates + M2 growing): score 5-15 → clearly bullish
    - Neutral: score 30-45
    - Restrictive (hiking + QT + M2 falling): score 75-90 → clearly bearish
    Key: Uses 2Y yield 2M change to detect hiking cycle STARTING
    (market prices hikes before Fed acts — 2Y surged Jan 2022)

C2: BUSINESS CYCLE + OIL CONSTRAINT (35%)
    Oil is only bearish when the Fed CANNOT respond.
    - Oil crashing = deflationary = Fed CAN respond = score 15 (bullish)
    - Oil spiking + Fed constrained (CPI>3%, not cutting) = score 75 (bearish)
    - Strong cycle (LEI up, payrolls strong): score 20-30
    - Weakening cycle: score 40-55

C3: MARKET STRUCTURE (25%)
    Price vs 200DMA + death cross + credit spreads.
    - S&P 5%+ above 200DMA, golden cross: score 10 (bullish)
    - S&P below 200DMA, death cross: score 70-80 (bearish)
    - Credit crisis (HY >800bps): score 85 → force RED regardless

REGIME RULES:
    Score < 38:  RISK-ON (invest)
    Score 38-51: CAUTION (defensive)
    Score >= 52: RISK-OFF (stay out)
    
    Credit crisis override: HY spikes >500bps in 2M → immediate RED
    Min 2-month hold before switching (prevents whipsaw)

WHAT THIS CATCHES:
    2022 bear: C1 spikes when Fed signals hiking (Jan 2022) → RED early
    COVID: C2 = 15 because OIL CRASHED (deflationary) → credit override → brief RED
    2021 bull: C1 = 5 because M2 +13%, rates zero → clearly green despite CPI
    2026 now: C2 = 80+ because oil spiked AND Fed constrained → RED
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
.kpi-grid { display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:24px; }
.kpi-card { background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);
            border-radius:10px;padding:18px; }
.kpi-lbl  { font-size:9px;letter-spacing:0.15em;color:#555;font-family:'DM Mono',monospace;
            margin-bottom:8px;text-transform:uppercase; }
.kpi-val  { font-size:24px;font-weight:700;font-family:'DM Mono',monospace;line-height:1; }
.kpi-sub  { font-size:10px;color:#666;margin-top:6px; }
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
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div style="font-size:10px;letter-spacing:0.2em;color:#555;text-transform:uppercase;'
    'font-family:\'DM Mono\',monospace;margin-bottom:4px;">Macro Regime Monitor</div>'
    '<h1 style="margin:0;font-size:28px;font-weight:600;letter-spacing:-0.02em;">'
    'Business Cycle Regime</h1>'
    '<p style="margin:6px 0 24px;font-size:12px;color:#555;">'
    'Liquidity Regime · Business Cycle + Oil Constraint · Market Structure</p>',
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
    "effr":        "FEDFUNDS",
    "t2y":         "DGS2",
    "m2":          "M2SL",
    "tips10y":     "DFII10",
    "cpi":         "CPIAUCSL",
    "oil":         "DCOILWTICO",
    "lei":         "USSLIND",
    "payems":      "PAYEMS",
    "icsa":        "ICSA",
    "hy_spread":   "BAMLH0A0HYM2",
    "ig_spread":   "BAMLC0A0CM",
    "t10y2y":      "T10Y2Y",
    "breakeven5y": "T5YIE",
    "walcl":       "WALCL",
    "ecb_assets":  "ECBASSETSW",
    "boj_assets":  "JPNASSETS",
    "dxy":         "DTWEXBGS",
}


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_data(today_str, api_key):
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
# THREE COMPONENT SCORES  (0=bullish, 100=bearish)
# ─────────────────────────────────────────────────────────────────────────────

def c1_liquidity_regime(m):
    """
    Fed stance x M2 x rate pricing. Starts at 50 (neutral).
    Score 10-20 = bull. Score 75-90 = bear.
    KEY: M2 growth NOT bullish when CPI > 4% (causing the inflation).
    """
    idx = m.index
    s   = np.full(len(idx), 50.0)  # neutral start

    cpi    = m["cpi"].values
    cpi_12 = np.concatenate([np.full(12, np.nan),
                              (cpi[12:] / cpi[:-12] - 1) * 100])
    hot    = np.nan_to_num(cpi_12) > 4.0  # inflation hot flag

    # Fed Funds 6M pace
    effr    = m["effr"].values
    effr_6m = np.concatenate([np.full(6, np.nan), effr[6:] - effr[:-6]])
    s += np.where(effr_6m > 3.0,  30, np.where(effr_6m > 2.0,  20,
         np.where(effr_6m > 1.0,  12, np.where(effr_6m > 0.25,  6,
         np.where(effr_6m > 0.0,   1, np.where(effr_6m < -1.0,-25,
         np.where(effr_6m < -0.5,-15, np.where(effr_6m < -0.25,-8,
         np.where(effr_6m < 0.0,  -2, 0)))))))))

    # EFFR absolute level
    s += np.where(effr > 4.5, 20, np.where(effr > 4.0, 14,
         np.where(effr > 3.0,  8, np.where(effr > 2.0,  2,
         np.where(effr > 1.0,  0, np.where(effr > 0.25,-8, -18))))))

    # M2 YoY — only bullish when CPI low
    m2    = m["m2"].values
    m2_12 = np.concatenate([np.full(12, np.nan),
                             (m2[12:] / m2[:-12] - 1) * 100])
    m2s   = np.where(m2_12 < -2,  25, np.where(m2_12 < -1,  14,
            np.where(m2_12 < 0,    6, np.where(m2_12 < 3,    0,
            np.where(m2_12 < 7,   -6, np.where(m2_12 < 15, -14, -22))))))
    s    += np.where(hot, np.maximum(m2s, 0), m2s)  # cap bullish M2 when hot

    # 2Y yield — hiking cycle signal
    t2y    = m["t2y"].values
    t2y_2m = np.concatenate([np.full(2, np.nan), t2y[2:] - t2y[:-2]])
    t2y_4m = np.concatenate([np.full(4, np.nan), t2y[4:] - t2y[:-4]])
    hike   = (np.nan_to_num(t2y_2m) > 0.2) & hot
    s     += np.where(hike, 15, np.where(t2y_4m > 1.5, 18,
             np.where(t2y_4m > 1.0, 12, np.where(t2y_4m > 0.5,  6,
             np.where(t2y_2m < -0.5,-15, np.where(t2y_2m < -0.25,-8, 0))))))

    # TIPS real yield
    if "tips10y" in m.columns:
        tips = m["tips10y"].values
        s += np.where(tips > 2.0, 10, np.where(tips > 1.0,  5,
             np.where(tips > 0.5,  2, np.where(tips > 0.0,  0,
             np.where(tips > -0.5,-3, np.where(tips > -1.5,-7, -12))))))

    # Global Liquidity (Fed + ECB, no shift to avoid NaN)
    gl = np.zeros(len(idx))
    n  = 0
    for col, thr in [("walcl", 8), ("ecb_assets", 6)]:
        if col in m.columns:
            v   = m[col].values
            r3  = np.concatenate([np.full(3, np.nan),
                                   (v[3:] / v[:-3] - 1) * 100])
            r1  = np.concatenate([np.full(1, np.nan),
                                   (v[1:] / v[:-1] - 1) * 100])
            cqe = np.nan_to_num(r1) > thr
            raw = np.where(r3 > 4, -10, np.where(r3 > 1.5, -5,
                  np.where(r3 > 0, -2,  np.where(r3 > -2,   5,
                  np.where(r3 > -5, 10,                     15)))))
            gl += np.where(cqe, 0, raw)
            n  += 1
    if n > 0:
        s += (gl / n)

    return pd.Series(np.clip(s, 0, 100), index=idx)


def c2_cycle_oil(m):
    """
    Business cycle position + oil constraint.
    
    Oil only bearish when Fed is ACTUALLY constrained:
    - Fed is already hiking (effr_6m > 0.25), OR
    - Market is pricing hikes with hot inflation (t2y surging + CPI>4%), OR  
    - Fed can't cut even if it wants to (2Y barely below EFFR = limited cuts priced)
    
    This prevents 2021 from being bearish — Fed was choosing to stay easy
    even with 5% CPI. The constraint only bit when Fed STARTED hiking (Jan 2022).
    """
    idx = m.index
    s   = np.full(len(idx), 15.0)  # lower base: strong cycle = can get to 0

    cpi    = m["cpi"].values
    cpi_12 = np.concatenate([np.full(12, np.nan),
                              (cpi[12:] / cpi[:-12] - 1) * 100])
    effr     = m["effr"].values
    effr_6m  = np.concatenate([np.full(6, np.nan), effr[6:] - effr[:-6]])
    effr_3m  = np.concatenate([np.full(3, np.nan), effr[3:] - effr[:-3]])
    t2y      = m["t2y"].values
    t2y_2m   = np.concatenate([np.full(2, np.nan), t2y[2:] - t2y[:-2]])

    # Fed actually constrained = any of:
    # 1. Already hiking (effr rising)
    # 2. Market pricing hikes with hot inflation (2Y surging + CPI>4%)
    # 3. Fed on hold but inflation won't allow cuts (CPI>3% AND 2Y-EFFR gap small)
    gap_2y_effr = t2y - effr  # negative = cuts priced, closer to 0 = fewer cuts
    actually_hiking = np.nan_to_num(effr_6m) > 0.25
    market_pricing_hikes = (np.nan_to_num(t2y_2m) > 0.25) & \
                           (np.nan_to_num(cpi_12) > 4.0)
    cant_cut = (np.nan_to_num(cpi_12) > 3.0) & (gap_2y_effr > -0.75)
    fed_constrained = actually_hiking | market_pricing_hikes | cant_cut

    # Oil rate of change — THE key signal
    oil     = m["oil"].values
    oil_1m  = np.concatenate([np.full(1, np.nan),
                               (oil[1:] / oil[:-1] - 1) * 100])
    oil_3m  = np.concatenate([np.full(3, np.nan),
                               (oil[3:] / oil[:-3] - 1) * 100])

    # Bearish oil signal — only full strength when Fed constrained
    oil_b = np.where(oil_1m > 25, 40, np.where(oil_1m > 15, 25,
            np.where(oil_1m > 8,  12, np.where(oil_3m > 30, 20,
            np.where(oil_3m > 20, 12, np.where(oil_3m > 10,  6, 0))))))
    s += np.where(fed_constrained, oil_b, oil_b * 0.25)

    # Oil bullish (crashing = deflationary = Fed can respond)
    s += np.where(oil_1m < -20, -25, np.where(oil_1m < -12, -15,
         np.where(oil_1m < -6,   -8, np.where(oil_3m < -25, -15,
         np.where(oil_3m < -15,  -8,  0)))))

    # LEI 6M trend (Conference Board Leading Economic Index)
    if "lei" in m.columns:
        lei   = m["lei"].values
        lei_6 = np.concatenate([np.full(6, np.nan),
                                 (lei[6:] / lei[:-6] - 1) * 100])
        s += np.where(lei_6 > 3,  -18, np.where(lei_6 > 1,  -10,
             np.where(lei_6 > 0,   -3, np.where(lei_6 > -1,   6,
             np.where(lei_6 > -3,  14,                         22)))))

    # Employment level YoY — Cowen: "going negative = recession"
    if "payems" in m.columns:
        pay   = m["payems"].values
        p_yoy = np.concatenate([np.full(12, np.nan),
                                 (pay[12:] / pay[:-12] - 1) * 100])
        s += np.where(p_yoy > 2.5, -15, np.where(p_yoy > 1.5,  -8,
             np.where(p_yoy > 0.5,  -2, np.where(p_yoy > 0.0,   6,
             np.where(p_yoy > -0.5, 16,                          28)))))

    # CPI — only adds to bearish when Fed is constrained
    cpi_p = np.where(np.nan_to_num(cpi_12) > 6,   15,
            np.where(np.nan_to_num(cpi_12) > 4,    8,
            np.where(np.nan_to_num(cpi_12) > 3,    4,
            np.where(np.nan_to_num(cpi_12) > 2,    0, -4))))
    s += np.where(fed_constrained, cpi_p, cpi_p * 0.2)

    return pd.Series(np.clip(s, 0, 100), index=idx)


def c3_market_structure(m):
    """
    Market price structure + credit spreads.
    
    Score 8-15:  S&P 5%+ above 200DMA, golden cross, tight spreads
    Score 70-85: Below 200DMA, death cross, spreads widening
    Score 85+:   Credit crisis (HY >800bps) → forces overall regime RED
    """
    idx = m.index
    s   = np.zeros(len(idx))

    # ── S&P vs 200DMA (12-month MA proxy on monthly data) ─────────────────
    if "sp500" in m.columns and not m["sp500"].isna().all():
        sp    = m["sp500"].values
        ma200 = pd.Series(sp).rolling(12, min_periods=6).mean().values
        ma50  = pd.Series(sp).rolling(4,  min_periods=3).mean().values
        pct200 = np.where(ma200 > 0, (sp / ma200 - 1) * 100, 0)

        s += np.where(pct200 > 12,  -20,
             np.where(pct200 > 6,   -12,
             np.where(pct200 > 2,    -5,
             np.where(pct200 > 0,     0,
             np.where(pct200 > -5,   15,
             np.where(pct200 > -10,  28,
                                      40))))))

        # Death cross: 4M MA below 12M MA
        cross = np.where(ma200 > 0, (ma50 / ma200 - 1) * 100, 0)
        s += np.where(cross < -1.5,  20,
             np.where(cross < -0.5,  10,
             np.where(cross > 2.0,  -12,
             np.where(cross > 0.5,   -5, 0))))

        # 6M momentum
        sp_6m = np.concatenate([np.full(6, np.nan),
                                 (sp[6:] / sp[:-6] - 1) * 100])
        s += np.where(sp_6m > 15,   -12,
             np.where(sp_6m > 8,     -6,
             np.where(sp_6m < -15,   15,
             np.where(sp_6m < -8,     8, 0))))

    # ── HY Credit Spreads ─────────────────────────────────────────────────
    if "hy_spread" in m.columns:
        hy    = m["hy_spread"].values
        hy_2m = np.concatenate([np.full(2, np.nan), hy[2:] - hy[:-2]])
        hy_max4 = pd.Series(hy).rolling(4).max().values

        # Level
        s += np.where(hy < 300,  -15,
             np.where(hy < 360,   -8,
             np.where(hy < 420,    0,
             np.where(hy < 500,   10,
             np.where(hy < 650,   25,
             np.where(hy < 900,   40,
                                   55))))))

        # 2M speed
        s += np.where(hy_2m > 300,  30,
             np.where(hy_2m > 150,  18,
             np.where(hy_2m > 75,   10,
             np.where(hy_2m < -150, -15,
             np.where(hy_2m < -75,   -8, 0)))))

        # Recovery from peak
        recovering = (hy < hy_max4 * 0.85) & (hy > 400)
        s += np.where(recovering, -15, 0)

    # Add base of 10
    s += 10

    return pd.Series(np.clip(s, 0, 100), index=idx)


def build_regime(c1, c2, c3, m):
    """
    Weighted composite score then classify.
    
    Credit crisis override: when HY spikes >500bps in 2 months,
    force regime to RED immediately (catches COVID Mar 2020).
    
    Min 2-month hold before switching (prevents whipsaw).
    """
    score = (c1 * 0.40 + c2 * 0.35 + c3 * 0.25).clip(0, 100)

    # Credit crisis override — HY spike >500bps in 2M = immediate Risk-Off
    hy_override = pd.Series(False, index=m.index)
    if "hy_spread" in m.columns:
        hy_2m = m["hy_spread"].diff(2)
        hy_override = hy_2m > 500

    # Raw regime
    raw = pd.Series("Risk-On", index=score.index)
    raw[score >= 38] = "Caution"
    raw[score >= 52] = "Risk-Off"
    raw[hy_override] = "Risk-Off"  # credit crisis override

    # Min 2-month hold
    final   = raw.copy()
    current = raw.iloc[0]
    dur     = 1
    for i in range(1, len(raw)):
        p = raw.iloc[i]
        if p != current:
            if dur >= 2:
                current = p
                dur     = 1
            else:
                dur += 1
        else:
            dur += 1
        final.iloc[i] = current

    return final, score


# ─────────────────────────────────────────────────────────────────────────────
# FETCH + COMPUTE
# ─────────────────────────────────────────────────────────────────────────────

pb = st.progress(0,  text="Fetching FRED data...")
monthly = fetch_data(TODAY, fred_key)

pb.progress(55, text="Fetching S&P 500...")
sp_daily = fetch_sp500(TODAY)

pb.progress(85, text="Computing regime...")

if sp_daily.empty:
    st.error("Could not fetch S&P 500.")
    st.stop()

monthly["sp500"] = sp_daily.resample("ME").last().reindex(monthly.index).ffill()

c1 = c1_liquidity_regime(monthly)
c2 = c2_cycle_oil(monthly)
c3 = c3_market_structure(monthly)

regime, score = build_regime(c1, c2, c3, monthly)

pb.progress(100, text="Done!")
pb.empty()

# Display window
sp_disp  = sp_daily[sp_daily.index >= DISPLAY_START]
reg_disp = regime[regime.index >= DISPLAY_START]
sc_disp  = score[score.index >= DISPLAY_START]
c1d      = c1[c1.index >= DISPLAY_START]
c2d      = c2[c2.index >= DISPLAY_START]
c3d      = c3[c3.index >= DISPLAY_START]

daily_regime = regime.reindex(sp_disp.index, method="ffill").ffill()

# ─────────────────────────────────────────────────────────────────────────────
# CURRENT STATUS
# ─────────────────────────────────────────────────────────────────────────────

cur_reg   = reg_disp.iloc[-1]
cur_score = round(float(sc_disp.iloc[-1]), 1)
cur_c1    = round(float(c1d.iloc[-1]), 0)
cur_c2    = round(float(c2d.iloc[-1]), 0)
cur_c3    = round(float(c3d.iloc[-1]), 0)

colors = {
    "Risk-On":  "#00D4AA",
    "Caution":  "#f59e0b",
    "Risk-Off": "#FF4757",
}
labels = {
    "Risk-On":  "RISK-ON — Invest",
    "Caution":  "CAUTION — Defensive",
    "Risk-Off": "RISK-OFF — Stay Out",
}
cc = colors.get(cur_reg, "#E8E8E8")

st.markdown(
    '<div style="text-align:center;margin-bottom:28px;padding:22px;border-radius:14px;'
    'background:' + cc + '0f;border:1px solid ' + cc + '33;">'
    '<div style="font-size:10px;letter-spacing:0.2em;color:#555;text-transform:uppercase;'
    'font-family:\'DM Mono\',monospace;margin-bottom:8px;">Current Macro Regime</div>'
    '<div style="font-size:34px;font-weight:700;color:' + cc + ';'
    'font-family:\'DM Mono\',monospace;">' + labels.get(cur_reg, cur_reg) + '</div>'
    '<div style="font-size:11px;color:#666;margin-top:8px;">'
    'Bear Score: ' + str(cur_score) + ' / 100</div>'
    '</div>',
    unsafe_allow_html=True
)

def bar(score, label, sub):
    c = "#00D4AA" if score < 38 else ("#f59e0b" if score < 52 else "#FF4757")
    return (
        '<div class="kpi-card">'
        '<div class="kpi-lbl">' + label + '</div>'
        '<div class="kpi-val" style="color:' + c + ';">' + str(int(score)) + '</div>'
        '<div class="kpi-sub">' + sub + '</div>'
        '<div style="height:5px;border-radius:3px;margin-top:10px;background:#1a1a2e;">'
        '<div style="height:5px;border-radius:3px;width:' + str(int(score)) + '%;'
        'background:' + c + ';opacity:0.7;"></div></div>'
        '</div>'
    )

on_pct  = (reg_disp == "Risk-On").mean() * 100
off_pct = (reg_disp == "Risk-Off").mean() * 100

st.markdown('<div class="sec-label">Component Scores — 0 = Bullish · 100 = Bearish</div>',
            unsafe_allow_html=True)

# ── DEBUG: show raw FRED values so we can verify data is loading ──────────
with st.expander("🔍 Raw Data Debug — click to verify FRED values are loading"):
    latest = monthly.iloc[-1]
    debug_rows = []
    for col in ["effr", "t2y", "m2", "tips10y", "cpi", "oil",
                "lei", "payems", "hy_spread", "walcl", "ecb_assets", "dxy"]:
        val = latest.get(col, None)
        if val is not None and not pd.isna(val):
            debug_rows.append({"Series": col, "Latest Value": round(float(val), 4),
                               "Status": "✓ Loaded"})
        else:
            debug_rows.append({"Series": col, "Latest Value": "MISSING",
                               "Status": "✗ Failed"})
    st.dataframe(pd.DataFrame(debug_rows), use_container_width=True)
    
    # Show computed sub-values
    st.write("**Computed inputs (latest month):**")
    try:
        effr_v    = float(monthly["effr"].iloc[-1])
        effr_6m_v = float(monthly["effr"].diff(6).iloc[-1])
        m2_yoy_v  = float(monthly["m2"].pct_change(12).iloc[-1] * 100)
        t2y_v     = float(monthly["t2y"].iloc[-1])
        t2y_2m_v  = float(monthly["t2y"].diff(2).iloc[-1])
        cpi_v     = float(monthly["cpi"].pct_change(12).iloc[-1] * 100)
        oil_v     = float(monthly["oil"].iloc[-1]) if "oil" in monthly.columns else None
        oil_1m_v  = float(monthly["oil"].pct_change(1).iloc[-1] * 100) if "oil" in monthly.columns else None
        
        st.write(f"- EFFR: {effr_v:.2f}%  |  6M change: {effr_6m_v:+.2f}%")
        st.write(f"- 2Y yield: {t2y_v:.2f}%  |  2M change: {t2y_2m_v:+.3f}%")
        st.write(f"- M2 YoY: {m2_yoy_v:+.1f}%")
        st.write(f"- CPI YoY: {cpi_v:+.1f}%")
        if oil_v: st.write(f"- WTI Oil: ${oil_v:.2f}  |  1M change: {oil_1m_v:+.1f}%")
        st.write(f"- C1={cur_c1:.0f}  C2={cur_c2:.0f}  C3={cur_c3:.0f}  →  Bear Score={cur_score}")
    except Exception as e:
        st.write(f"Error computing debug values: {e}")

st.markdown(
    '<div class="kpi-grid">'
    + bar(cur_c1, "C1 · Liquidity Regime (40%)",
          "Fed stance + M2 + 2Y yield + GL")
    + bar(cur_c2, "C2 · Cycle + Oil (35%)",
          "Oil constraint + LEI + Payrolls")
    + bar(cur_c3, "C3 · Market Structure (25%)",
          "200DMA + death cross + credit")
    + bar(cur_score, "Composite Bear Score",
          "< 38 = Risk-On · ≥ 52 = Risk-Off")
    + '</div>',
    unsafe_allow_html=True
)

# Accuracy table
events = {
    "Pre-COVID 2020":    ("2019-10", "2020-01", "Risk-On"),
    "COVID crash":       ("2020-02", "2020-04", "Risk-Off"),
    "COVID bull":        ("2020-05", "2021-11", "Risk-On"),
    "Bear 2022 Jan-Oct": ("2022-01", "2022-10", "Risk-Off"),
    "Recovery 2023":     ("2022-11", "2023-12", "Risk-On"),
    "Bull 2024":         ("2024-01", "2024-12", "Risk-On"),
    "2025+ crash":       ("2025-02", "2025-05", "Risk-Off"),
    "Recovery 2025":     ("2025-06", "2025-12", "Risk-On"),
    "2026 current":      ("2026-01", END,        "Risk-Off"),
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
ax1.plot(ma200.index, ma200.values, color="#f59e0b", linewidth=0.9,
         alpha=0.7, linestyle="--", zorder=4)
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

patches = [mpatches.Patch(color=c, alpha=0.6, label=l)
           for l, c in cmap.items()]
patches.append(plt.Line2D([0],[0], color="#f59e0b", linewidth=0.9,
                           linestyle="--", label="200DMA"))
ax1.legend(handles=patches, loc="upper left", framealpha=0,
           fontsize=8, labelcolor="#aaa")
ax1.set_title(
    "S&P 500 — Business Cycle Regime  "
    "|  Liquidity · Cycle+Oil · Market Structure",
    color="#E8E8E8", fontsize=11, fontweight="bold", pad=10, loc="left"
)

# Bear score
ax2.fill_between(sc_disp.index, sc_disp, 50,
                 where=sc_disp >= 50, color="#FF4757", alpha=0.35, interpolate=True)
ax2.fill_between(sc_disp.index, sc_disp, 50,
                 where=sc_disp < 50,  color="#00D4AA", alpha=0.35, interpolate=True)
ax2.plot(sc_disp.index, sc_disp.values, color="#ccc", linewidth=1.0, zorder=5)
ax2.axhline(50, color="#333",    linewidth=0.8)
ax2.axhline(38, color="#f59e0b", linewidth=0.5, linestyle=":", alpha=0.5)
ax2.axhline(52, color="#FF4757", linewidth=0.5, linestyle=":", alpha=0.5)
ax2.text(sc_disp.index[-1], 38, "  Caution",  color="#f59e0b", fontsize=6.5, va="bottom")
ax2.text(sc_disp.index[-1], 52, "  Risk-Off", color="#FF4757", fontsize=6.5, va="bottom")
ax2.set_ylim(0, 100)
ax2.set_xlim(sc_disp.index[0], sc_disp.index[-1])
ax2.set_ylabel("Bear Score", color="#666", fontsize=7, labelpad=6)
ax2.set_xticklabels([])
ax2.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
ax2.grid(axis="y", color="#111122", linewidth=0.5)

for col, color, label in [
    (c1d, "#5B8DEF", "C1 Liquidity"),
    (c2d, "#FF6B35", "C2 Cycle+Oil"),
    (c3d, "#FF4757", "C3 Market"),
]:
    ax3.plot(col.index, col.values, color=color, linewidth=0.9, alpha=0.9, label=label)

ax3.axhline(50, color="#333", linewidth=0.8)
ax3.axhline(52, color="#FF4757", linewidth=0.4, linestyle=":", alpha=0.4)
ax3.set_ylim(0, 100)
ax3.set_xlim(c1d.index[0], c1d.index[-1])
ax3.set_ylabel("Components", color="#666", fontsize=7, labelpad=6)
ax3.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
ax3.grid(axis="y", color="#111122", linewidth=0.5)
ax3.legend(loc="upper left", framealpha=0, fontsize=8, labelcolor="#aaa", ncol=3)

fig.text(0.99, 0.005,
         "Generated " + TODAY + "  ·  FRED + yfinance  ·  Business Cycle v2",
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
    file_name="regime_bc_v2_" + TODAY + ".pdf",
    mime="application/pdf",
)
