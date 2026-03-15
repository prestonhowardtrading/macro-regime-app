"""
Macro Regime Backtest — Full Data Stack
========================================
Sources:
  1. FRED API          — macro indicators (your key)
  2. yfinance          — DXY, BCOM, S&P 500 (free)
  3. CME FedWatch      — rate cut probabilities (scraped)
  4. BIS Statistics    — PBOC balance sheet (scraped)
  5. Atlanta Fed       — GDPNow (scraped)
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
.hdr-dot { width:6px;height:6px;border-radius:50%;background:#00D4AA;box-shadow:0 0 8px #00D4AA;display:inline-block;margin-right:8px;vertical-align:middle; }
.stat-grid { display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px; }
.stat-card { background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:16px; }
.stat-lbl  { font-size:9px;letter-spacing:0.15em;color:#555;font-family:'DM Mono',monospace;margin-bottom:6px;text-transform:uppercase; }
.stat-val  { font-size:22px;font-weight:700;font-family:'DM Mono',monospace;line-height:1; }
.src-grid  { display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:24px; }
.src-card  { background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:8px;padding:12px; }
.src-name  { font-size:10px;font-weight:600;color:#E8E8E8;margin-bottom:4px; }
.src-stat  { font-size:10px;color:#555;font-family:'DM Mono',monospace; }
.src-ok    { color:#00D4AA !important; }
.src-warn  { color:#f59e0b !important; }
.bear-table { width:100%;border-collapse:collapse; }
.bear-table th { font-size:9px;letter-spacing:0.15em;color:#555;text-transform:uppercase;font-family:'DM Mono',monospace;padding:10px 14px;text-align:left;border-bottom:1px solid rgba(255,255,255,0.06); }
.bear-table td { font-size:12px;color:#aaa;padding:10px 14px;border-bottom:1px solid rgba(255,255,255,0.04);font-family:'DM Mono',monospace; }
.sec-label { font-size:10px;letter-spacing:0.15em;color:#555;text-transform:uppercase;font-family:'DM Mono',monospace;margin-bottom:14px;margin-top:28px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,0.06); }
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div style="font-size:10px;letter-spacing:0.2em;color:#555;text-transform:uppercase;'
    'font-family:\'DM Mono\',monospace;margin-bottom:4px;">'
    '<span class="hdr-dot"></span>Macro Regime Monitor</div>'
    '<h1 style="margin:0;font-size:28px;font-weight:600;letter-spacing:-0.02em;color:#E8E8E8;">'
    'Regime Backtest</h1>'
    '<p style="margin:6px 0 24px;font-size:12px;color:#555;">'
    '20-year S&P 500 overlay using full 5-source data stack</p>',
    unsafe_allow_html=True
)

# ─────────────────────────────────────────────────────────────────────────────
# FRED KEY
# ─────────────────────────────────────────────────────────────────────────────

fred_key = st.secrets.get("FRED_API_KEY", None)
if not fred_key:
    fred_key = st.text_input(
        "Enter your FRED API Key", type="password",
        placeholder="fred.stlouisfed.org/docs/api/api_key.html"
    )
if not fred_key:
    st.markdown(
        '<div style="padding:20px;border-radius:12px;background:rgba(255,255,255,0.02);'
        'border:1px dashed rgba(255,255,255,0.08);text-align:center;color:#555;">'
        'Enter your FRED API key above to run the backtest.</div>',
        unsafe_allow_html=True
    )
    st.stop()

START = "2004-01-01"
END   = date.today().strftime("%Y-%m-%d")
TODAY = str(date.today())

# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 1: FRED
# ─────────────────────────────────────────────────────────────────────────────

FRED_SERIES = {
    "unrate":      "UNRATE",
    "icsa":        "ICSA",
    "t10y2y":      "T10Y2Y",
    "t2y":         "DGS2",
    "tips10y":     "DFII10",
    "walcl":       "WALCL",
    "ism_mfg":     "NAPM",
    "ism_svc":     "NMFSL",
    "retail":      "RSAFS",
    "lei":         "USSLIND",
    "gdpc1":       "GDPC1",
    "dxy_proxy":   "DTWEXBGS",
    "cpi":         "CPIAUCSL",
    "core_pce":    "PCEPILFE",
    "ppi":         "PPIACO",
    "breakeven5y": "T5YIE",
    "wages":       "CES0500000003",
    "m2":          "M2SL",
    "rrp":         "RRPONTSYD",
    "tga":         "WTREGEN",
    "nfci":        "NFCI",
    "hy_spread":   "BAMLH0A0HYM2",
    "ig_spread":   "BAMLC0A0CM",
    "lending_std": "DRTSCILM",
    "ecb_assets":  "ECBASSETSW",
    "boj_assets":  "JPNASSETS",
}


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_fred_data(today_str, api_key):
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
    monthly = df.resample("ME").last().ffill().bfill()
    return monthly, failed


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 2: yfinance
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_yfinance_data(today_str):
    import yfinance as yf
    results = {}
    failed = []
    tickers = {"sp500": "^GSPC", "dxy": "DX-Y.NYB", "bcom": "^BCOM"}
    for name, ticker in tickers.items():
        try:
            raw = yf.download(ticker, start=START, end=END,
                              progress=False, auto_adjust=True)
            if isinstance(raw.columns, pd.MultiIndex):
                s = raw["Close"][ticker]
            else:
                s = raw["Close"]
            s = s.squeeze()
            s.index = pd.to_datetime(s.index).tz_localize(None)
            results[name] = s
        except Exception:
            failed.append(ticker)
    return results, failed


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 3: CME FedWatch
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_fedwatch_current():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json, text/plain, */*",
        "Referer": "https://www.cmegroup.com/markets/interest-rates/cme-fedwatch-tool.html",
    }
    endpoints = [
        "https://www.cmegroup.com/CmeWS/mvc/MeetingDatesProbabilities/FEDWATCH?meetingDates=currentMeeting",
        "https://www.cmegroup.com/CmeWS/mvc/MeetingDatesProbabilities/FEDWATCH",
    ]
    for url in endpoints:
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code == 200:
                text = resp.text
                cp = re.search(r'"cutProbability"[:\s]+([\d.]+)', text)
                hp = re.search(r'"hikeProbability"[:\s]+([\d.]+)', text)
                if cp:
                    cut  = float(cp.group(1))
                    hike = float(hp.group(1)) if hp else 0.0
                    return cut, hike, 100 - cut - hike, "CME FedWatch (live)"
        except Exception:
            pass
    return None, None, None, "unavailable"


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 4: BIS — PBOC
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_pboc(today_str):
    try:
        url = (
            "https://stats.bis.org/api/v2/data/dataflow/BIS/CBS/1.0/"
            "A.5J.N.A.A.TO1.A?format=csv&startPeriod=2004-01&endPeriod="
            + today_str[:7]
        )
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200 and len(resp.text) > 200:
            from io import StringIO
            df = pd.read_csv(StringIO(resp.text))
            if "TIME_PERIOD" in df.columns and "OBS_VALUE" in df.columns:
                df["date"] = pd.to_datetime(df["TIME_PERIOD"])
                s = df.set_index("date")["OBS_VALUE"].astype(float)
                s.index = s.index.tz_localize(None)
                return s.resample("ME").last().ffill(), "BIS (live)"
    except Exception:
        pass
    return None, "unavailable"


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE 5: Atlanta Fed GDPNow
# ─────────────────────────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_gdpnow():
    try:
        url = "https://www.atlantafed.org/ceres/real-time-analysis/gdpnow"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if resp.status_code == 200:
            for pattern in [
                r'GDPNow[^<]*?(\-?\d+\.\d+)\s*%',
                r'current estimate[^<]*?(\-?\d+\.\d+)',
                r'(\-?\d+\.\d+)\s*percent',
            ]:
                m = re.search(pattern, resp.text[:8000], re.IGNORECASE)
                if m:
                    val = float(m.group(1))
                    if -20 < val < 20:
                        return val, "Atlanta Fed (live)"
    except Exception:
        pass
    return None, "unavailable"


# ─────────────────────────────────────────────────────────────────────────────
# SCORING
# ─────────────────────────────────────────────────────────────────────────────

def pct_chg(s, n):
    return s.pct_change(n) * 100


def fw_score(t2y):
    chg = t2y.diff(3)
    return pd.Series(
        np.where(chg < -0.75, 20, np.where(chg < -0.35, 10,
        np.where(chg >  0.75, -20, np.where(chg > 0.35, -10, 0)))),
        index=t2y.index
    )


def score_growth(m):
    s = pd.Series(0.0, index=m.index)

    # Monetary Policy 25%
    mp = fw_score(m["t2y"])
    tc = m["tips10y"].diff(3)
    mp += np.where(tc < -0.5, 10, np.where(tc > 0.5, -10, 0))
    wy = pct_chg(m["walcl"], 12)
    mp += np.where(wy > 2, 10, np.where(wy < -0.5, -10, 0))
    ycc = m["t10y2y"].diff(3)
    mp += np.where(ycc > 0.5, 5, np.where(m["t10y2y"] < -0.25, -10, 0))
    s += mp * 0.25

    # Global Liquidity 20%
    gl = np.where(wy > 5, 20, np.where(wy > 2, 10,
         np.where(wy < -5, -20, np.where(wy < -2, -10, 0))))
    s += pd.Series(gl, index=m.index) * 0.20

    # Labor Market 15%
    uc = m["unrate"].diff(6)
    lab = np.where(uc < -0.3, 15, np.where(uc < 0.1, 5,
          np.where(uc < 0.7, -10, -20)))
    s += pd.Series(lab, index=m.index) * 0.15
    if "icsa" in m.columns:
        ic = pct_chg(m["icsa"], 3)
        s += pd.Series(np.where(ic < -5, 5, np.where(ic > 10, -10, 0)),
                       index=m.index) * 0.05

    # Leading Indicators 15%
    ld = pd.Series(0.0, index=m.index)
    if "ism_mfg" in m.columns:
        pmi = m["ism_mfg"]
        ld += np.where(pmi > 55, 10, np.where(pmi > 52, 5,
              np.where(pmi > 48, 0, np.where(pmi > 45, -5, -10))))
        ld += np.where(pmi.diff(3) > 2, 5, np.where(pmi.diff(3) < -2, -5, 0))
    if "ism_svc" in m.columns:
        svc = m["ism_svc"]
        ld += np.where(svc > 55, 8, np.where(svc > 52, 4,
              np.where(svc > 48, 0, np.where(svc > 45, -4, -8))))
    lc = pct_chg(m["lei"], 6)
    ld += np.where(lc > 1, 8, np.where(lc > 0, 3, np.where(lc > -1, -5, -10)))
    rc = pct_chg(m["retail"], 12)
    ld += np.where(rc > 4, 6, np.where(rc > 2, 3,
          np.where(rc > 0, 0, np.where(rc > -2, -5, -8))))
    ld += np.where(m["retail"].pct_change(3) * 100 > 1, 3,
          np.where(m["retail"].pct_change(3) * 100 < -1, -3, 0))
    gc = pct_chg(m["gdpc1"].ffill(), 4)
    ld += np.where(gc > 3, 6, np.where(gc > 2, 3,
          np.where(gc > 1, 0, np.where(gc > 0, -3, -6))))
    s += ld.clip(-30, 30) * 0.15

    # Dollar Strength 10%
    dxy_col = "dxy" if ("dxy" in m.columns and not m["dxy"].isna().all()) else "dxy_proxy"
    dc = pct_chg(m[dxy_col], 3)
    dx = np.where(dc < -5, 15, np.where(dc < -2, 5,
         np.where(dc > 5, -15, np.where(dc > 2, -5, 0))))
    s += pd.Series(dx, index=m.index) * 0.10

    return s.clip(-100, 100)


def score_inflation(m):
    s = pd.Series(0.0, index=m.index)

    # Inflation Data 25%
    cm = m["cpi"].pct_change(1) * 100
    id_ = np.where(cm > 0.3, 20, np.where(cm > 0.1, 10,
          np.where(cm > -0.1, 0, np.where(cm > -0.3, -10, -20))))
    py = pct_chg(m["core_pce"], 12)
    id_ = id_ + np.where(py > 3, 10, np.where(py > 2, 5, np.where(py > 1.5, 0, -10)))
    pc = pct_chg(m["ppi"], 3)
    id_ = id_ + np.where(pc > 1, 10, np.where(pc < -1, -10, 0))
    s += pd.Series(id_, index=m.index) * 0.25

    # Commodity Prices 20% — true BCOM if available
    bcom_col = "bcom" if ("bcom" in m.columns and not m["bcom"].isna().all()) else "ppi"
    bc = pct_chg(m[bcom_col], 6)
    co = np.where(bc > 10, 15, np.where(bc > 5, 5,
         np.where(bc > -5, 0, np.where(bc > -10, -5, -10))))
    s += pd.Series(co, index=m.index) * 0.20

    # Monetary Policy Inflation Lens 20%
    mi = fw_score(m["t2y"]) * 0.75
    tc = m["tips10y"].diff(3)
    mi += np.where(tc > 0.5, -10, np.where(tc < -0.5, 10, 0))
    mi += np.where(pct_chg(m["walcl"], 12) > 2, 10,
          np.where(pct_chg(m["walcl"], 12) < -0.5, -10, 0))
    s += mi * 0.20

    # Wages 20%
    if "wages" in m.columns:
        wy = pct_chg(m["wages"], 12)
        wg = np.where(wy > 5, 15, np.where(wy > 3, 5,
             np.where(wy > 2, 0, -10)))
        s += pd.Series(wg, index=m.index) * 0.20

    # Inflation Expectations 15%
    bc_chg = m["breakeven5y"].diff(3)
    be = np.where(bc_chg > 0.5, 15, np.where(bc_chg > 0.1, 5,
         np.where(bc_chg > -0.1, 0, -10)))
    s += pd.Series(be, index=m.index) * 0.15

    return s.clip(-100, 100)


def score_liquidity(m):
    s = pd.Series(0.0, index=m.index)

    # CB Balance Sheets 40% — Fed 50%, ECB 20%, BOJ 20%, PBOC 10%
    def cb_score(yoy):
        return np.where(yoy > 10, 40, np.where(yoy > 5, 25,
               np.where(yoy > 1, 10, np.where(yoy > -1, 0,
               np.where(yoy > -5, -10, np.where(yoy > -10, -25, -40))))))

    fed_yoy = pct_chg(m["walcl"], 12)
    cb = pd.Series(cb_score(fed_yoy), index=m.index) * 0.50

    if "ecb_assets" in m.columns and not m["ecb_assets"].isna().all():
        ecb_yoy = pct_chg(m["ecb_assets"], 12)
        cb += pd.Series(cb_score(ecb_yoy), index=m.index) * 0.20
    if "boj_assets" in m.columns and not m["boj_assets"].isna().all():
        boj_yoy = pct_chg(m["boj_assets"], 12)
        cb += pd.Series(cb_score(boj_yoy), index=m.index) * 0.20
    if "pboc_assets" in m.columns and not m["pboc_assets"].isna().all():
        pboc_yoy = pct_chg(m["pboc_assets"], 12)
        cb += pd.Series(cb_score(pboc_yoy), index=m.index) * 0.10
    # PBOC neutral if unavailable (0 * 0.10)

    s += cb * 0.40

    # TGA / RRP 20%
    tl = pd.Series(0.0, index=m.index)
    if "tga" in m.columns:
        tc = m["tga"].diff(3)
        tl += np.where(tc < -200, 20, np.where(tc < -100, 10,
              np.where(tc > 200, -20, np.where(tc > 100, -10, 0))))
    if "rrp" in m.columns:
        rc = m["rrp"].diff(3).fillna(0)
        tl += np.where(rc < -200, 15, np.where(rc < -50, 5,
              np.where(rc > 200, -15, np.where(rc > 50, -5, 0))))
    s += tl * 0.20

    # Market Conditions 15%
    mk = pd.Series(0.0, index=m.index)
    my = pct_chg(m["m2"], 12)
    mk += np.where(my > 8, 10, np.where(my > 4, 5,
          np.where(my > 0, 0, np.where(my > -4, -5, -10))))
    if "nfci" in m.columns:
        nc = m["nfci"].diff(3).fillna(0)
        mk += np.where(nc < -0.4, 15, np.where(nc < -0.2, 10,
              np.where(nc < -0.05, 5, np.where(nc < 0.05, 0,
              np.where(nc < 0.2, -5, np.where(nc < 0.4, -10, -15))))))
    s += mk * 0.15

    # Dollar Liquidity 15%
    dxy_col = "dxy" if ("dxy" in m.columns and not m["dxy"].isna().all()) else "dxy_proxy"
    dc = pct_chg(m[dxy_col], 3)
    dl = np.where(dc < -5, 15, np.where(dc < -2, 10,
         np.where(dc < 0, 5, np.where(dc < 2, -5,
         np.where(dc < 5, -10, -15)))))
    s += pd.Series(dl, index=m.index) * 0.15

    # Credit Liquidity 10%
    cr = pd.Series(0.0, index=m.index)
    if "hy_spread" in m.columns:
        hc = m["hy_spread"].diff(3).fillna(0)
        cr += pd.Series(np.where(hc < -1, 10, np.where(hc < -0.5, 5,
              np.where(hc > 1, -10, np.where(hc > 0.5, -5, 0)))),
              index=m.index) * 0.50
    if "ig_spread" in m.columns:
        ic = m["ig_spread"].diff(3).fillna(0)
        cr += pd.Series(np.where(ic < -0.4, 10, np.where(ic < -0.2, 6,
              np.where(ic < -0.05, 3, np.where(ic < 0.05, 0,
              np.where(ic < 0.2, -3, np.where(ic < 0.4, -6, -10)))))),
              index=m.index) * 0.30
    if "lending_std" in m.columns:
        lc = m["lending_std"].diff(2).fillna(0)
        cr += pd.Series(np.where(lc < -10, 10, np.where(lc < -5, 6,
              np.where(lc < -1, 3, np.where(lc < 1, 0,
              np.where(lc < 5, -3, np.where(lc < 10, -6, -10)))))),
              index=m.index) * 0.20
    s += cr * 0.10

    return s.clip(-100, 100)


# ─────────────────────────────────────────────────────────────────────────────
# FETCH ALL DATA
# ─────────────────────────────────────────────────────────────────────────────

pb = st.progress(0, text="Fetching FRED data (1/5)...")
monthly, fred_failed = fetch_fred_data(TODAY, fred_key)

pb.progress(25, text="Fetching market data — DXY, BCOM, S&P 500 (2/5)...")
yf_data, yf_failed = fetch_yfinance_data(TODAY)

pb.progress(50, text="Fetching CME FedWatch probabilities (3/5)...")
cut_prob, hike_prob, hold_prob, fw_src = fetch_fedwatch_current()

pb.progress(65, text="Fetching PBOC balance sheet from BIS (4/5)...")
pboc_series, pboc_src = fetch_pboc(TODAY)

pb.progress(80, text="Fetching Atlanta Fed GDPNow (5/5)...")
gdpnow_val, gdpnow_src = fetch_gdpnow()

pb.progress(90, text="Merging and calculating scores...")

# Merge yfinance into monthly frame
for name, series in yf_data.items():
    if series is not None and not series.empty:
        series.index = pd.to_datetime(series.index).tz_localize(None)
        monthly[name] = series.resample("ME").last().reindex(monthly.index).ffill()

# Merge PBOC
if pboc_series is not None:
    monthly["pboc_assets"] = pboc_series.resample("ME").last().reindex(monthly.index).ffill()

# ─────────────────────────────────────────────────────────────────────────────
# CALCULATE SCORES
# ─────────────────────────────────────────────────────────────────────────────

g  = score_growth(monthly)
i  = score_inflation(monthly)
l  = score_liquidity(monthly)
ra = (0.5 * l + 0.3 * g + 0.2 * i).clip(-100, 100)

regime = pd.Series("Risk-Off", index=monthly.index)
regime[ra > 0] = "Risk-On"

pb.progress(100, text="Done!")
pb.empty()

# ─────────────────────────────────────────────────────────────────────────────
# ALIGN S&P 500
# ─────────────────────────────────────────────────────────────────────────────

sp_daily = yf_data.get("sp500", pd.Series(dtype=float))
if sp_daily is None or sp_daily.empty:
    st.error("Could not fetch S&P 500 from yfinance. Please try again.")
    st.stop()

sp_daily.index = pd.to_datetime(sp_daily.index).tz_localize(None)
sp_monthly = sp_daily.resample("ME").last()

combined = pd.DataFrame({
    "sp500":  sp_monthly,
    "growth": g,
    "infl":   i,
    "liq":    l,
    "ra":     ra,
    "regime": regime,
}).dropna(subset=["sp500", "ra"])

if combined.empty:
    st.error("No overlapping data between S&P 500 and FRED series. Please try again.")
    st.stop()

start_date   = combined.index[0]
sp_aligned   = sp_daily[sp_daily.index >= start_date].dropna()
daily_regime = regime.reindex(sp_aligned.index, method="ffill").ffill()

# ─────────────────────────────────────────────────────────────────────────────
# DATA SOURCE STATUS PANEL
# ─────────────────────────────────────────────────────────────────────────────

fred_ok    = len(FRED_SERIES) - len(fred_failed)
dxy_src    = "True DXY (ICE)" if ("dxy" in monthly.columns and not monthly["dxy"].isna().all()) else "Trade-weighted proxy"
bcom_src   = "True BCOM" if ("bcom" in monthly.columns and not monthly["bcom"].isna().all()) else "PPI proxy"
fw_txt     = (str(round(cut_prob, 1)) + "% cut prob") if cut_prob is not None else "Using 2Y yield proxy"
pboc_txt   = "Live BIS data" if pboc_series is not None else "Neutral fallback"
gdpnow_txt = (str(gdpnow_val) + "% current est.") if gdpnow_val else "Using GDPC1 quarterly"

st.markdown('<div class="sec-label">Data Source Status</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="src-grid">'

    '<div class="src-card">'
    '<div class="src-name">FRED API</div>'
    '<div class="src-stat src-ok">✓ ' + str(fred_ok) + "/" + str(len(FRED_SERIES)) + ' series</div>'
    '<div class="src-stat">Core macro indicators</div>'
    '</div>'

    '<div class="src-card">'
    '<div class="src-name">yfinance</div>'
    '<div class="src-stat ' + ("src-ok" if not yf_failed else "src-warn") + '">✓ DXY + BCOM + S&P</div>'
    '<div class="src-stat">' + dxy_src + ' · ' + bcom_src + '</div>'
    '</div>'

    '<div class="src-card">'
    '<div class="src-name">CME FedWatch</div>'
    '<div class="src-stat ' + ("src-ok" if cut_prob is not None else "src-warn") + '">'
    + ("✓ " if cut_prob is not None else "⚠ ") + fw_txt +
    '</div>'
    '<div class="src-stat">Rate cut probabilities</div>'
    '</div>'

    '<div class="src-card">'
    '<div class="src-name">BIS / PBOC</div>'
    '<div class="src-stat ' + ("src-ok" if pboc_series is not None else "src-warn") + '">'
    + ("✓ " if pboc_series is not None else "⚠ ") + pboc_txt +
    '</div>'
    '<div class="src-stat">PBOC balance sheet</div>'
    '</div>'

    '<div class="src-card">'
    '<div class="src-name">Atlanta Fed</div>'
    '<div class="src-stat ' + ("src-ok" if gdpnow_val else "src-warn") + '">'
    + ("✓ " if gdpnow_val else "⚠ ") + gdpnow_txt +
    '</div>'
    '<div class="src-stat">GDPNow real-time</div>'
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

# Bear market verdicts
bears = {
    "Dot-com 2000-02":  ("2000-03", "2002-10"),
    "GFC 2007-09":      ("2007-10", "2009-03"),
    "COVID 2020":       ("2020-02", "2020-05"),
    "Bear Market 2022": ("2022-01", "2022-10"),
}

st.markdown('<div class="sec-label">Key Bear Markets — Was the Model Risk-Off?</div>', unsafe_allow_html=True)

bear_rows = ""
for name, (bs, be) in bears.items():
    try:
        window = combined.loc[bs:be, "regime"]
        if len(window) == 0:
            continue
        off_p   = (window == "Risk-Off").mean() * 100
        on_p    = 100 - off_p
        color   = "#00D4AA" if off_p >= 60 else ("#f59e0b" if off_p >= 40 else "#FF4757")
        verdict = "✓ Defensive" if off_p >= 60 else ("~ Partial" if off_p >= 40 else "✗ Missed")
        bear_rows += (
            '<tr><td>' + name + '</td>'
            '<td style="color:#FF4757;">' + str(round(off_p)) + '% Risk-Off</td>'
            '<td style="color:#00D4AA;">' + str(round(on_p)) + '% Risk-On</td>'
            '<td style="color:' + color + ';font-weight:600;">' + verdict + '</td></tr>'
        )
    except Exception:
        pass

st.markdown(
    '<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);'
    'border-radius:12px;overflow:hidden;">'
    '<table class="bear-table"><thead><tr>'
    '<th>Period</th><th>Risk-Off %</th><th>Risk-On %</th><th>Verdict</th>'
    '</tr></thead><tbody>' + bear_rows + '</tbody></table></div>',
    unsafe_allow_html=True
)

# ─────────────────────────────────────────────────────────────────────────────
# CHART
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="sec-label">S&P 500 with Macro Regime Overlay</div>', unsafe_allow_html=True)

fig, (ax1, ax2) = plt.subplots(
    2, 1, figsize=(16, 10), facecolor="#0A0A0F",
    gridspec_kw={"height_ratios": [3, 1], "hspace": 0.05}
)

for ax in [ax1, ax2]:
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

ax1.plot(sp_aligned.index, sp_aligned.values, color="#E8E8E8", linewidth=1.1, zorder=5)
ax1.set_yscale("log")
ax1.set_ylabel("S&P 500 (log scale)", color="#666", fontsize=8, labelpad=8)
ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))
ax1.set_xlim(sp_aligned.index[0], sp_aligned.index[-1])
ax1.set_xticklabels([])
ax1.grid(axis="y", color="#111122", linewidth=0.6)
ax1.xaxis.set_major_locator(mdates.YearLocator(2))

for ds, lbl in [("2008-10", "GFC"), ("2020-03", "COVID"), ("2022-01", "2022 Bear")]:
    try:
        ed = pd.Timestamp(ds)
        if sp_aligned.index[0] <= ed <= sp_aligned.index[-1]:
            ax1.axvline(ed, color="#333", linewidth=0.8, linestyle="--", zorder=3)
            ax1.text(ed, sp_aligned.max() * 0.92, lbl, color="#666", fontsize=7.5,
                     ha="center", bbox=dict(boxstyle="round,pad=0.2",
                     facecolor="#0A0A0F", edgecolor="#333", alpha=0.9))
    except Exception:
        pass

p1 = mpatches.Patch(color="#00D4AA", alpha=0.5, label="Risk-On  (stay invested)")
p2 = mpatches.Patch(color="#FF4757", alpha=0.5, label="Risk-Off  (hold cash / hedge)")
ax1.legend(handles=[p1, p2], loc="upper left", framealpha=0, fontsize=8.5, labelcolor="#aaa")
ax1.set_title(
    "S&P 500 — 20-Year Macro Regime Overlay  |  FRED + yfinance + CME + BIS + Atlanta Fed",
    color="#E8E8E8", fontsize=11, fontweight="bold", pad=12, loc="left"
)

ra_m = combined["ra"]
ax2.fill_between(ra_m.index, ra_m, 0, where=ra_m >= 0, color="#00D4AA", alpha=0.3, interpolate=True)
ax2.fill_between(ra_m.index, ra_m, 0, where=ra_m < 0,  color="#FF4757", alpha=0.3, interpolate=True)
ax2.plot(ra_m.index, ra_m.values, color="#888", linewidth=0.9, zorder=5)
ax2.axhline(0, color="#333", linewidth=0.8)
ax2.set_ylim(-100, 100)
ax2.set_xlim(ra_m.index[0], ra_m.index[-1])
ax2.set_ylabel("Risk Appetite", color="#666", fontsize=8, labelpad=8)
ax2.xaxis.set_major_locator(mdates.YearLocator(2))
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax2.grid(axis="y", color="#111122", linewidth=0.6)

fig.text(0.99, 0.01,
         "Generated " + TODAY + "  ·  FRED + yfinance + CME FedWatch + BIS + Atlanta Fed GDPNow",
         ha="right", va="bottom", color="#333", fontsize=7, fontfamily="monospace")

plt.tight_layout(rect=[0, 0.015, 1, 1])
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
    file_name="regime_backtest_" + TODAY + ".pdf",
    mime="application/pdf",
)
