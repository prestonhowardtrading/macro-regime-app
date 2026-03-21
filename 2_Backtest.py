"""
Macro Regime Backtest — 200DMA + Global Liquidity
==================================================
Two signals only:

  SIGNAL 1: S&P 500 vs 200-day moving average
    - Price above 200DMA = bullish trend intact
    - Price below 200DMA = trend broken

  SIGNAL 2: Global Liquidity 3-month rate of change
    - Combined Fed + ECB + BOJ balance sheets + M2
    - Positive ROC = liquidity expanding = fuel for assets
    - Negative ROC = liquidity contracting = headwind

REGIME RULES:
  RISK-ON:  Price above 200DMA  AND/OR  GL expanding
  RISK-OFF: Price below 200DMA  AND     GL contracting

  The AND condition means both must agree to flip Risk-Off.
  This prevents false signals — either the trend OR liquidity
  being positive keeps you in the market.

  Minimum 2-month hold before switching to avoid whipsaw.

Why this works:
  - 200DMA catches 2022 (price broke below in Jan 2022)
  - GL catches COVID recovery (liquidity flooded in Apr 2020)
  - Together they avoid false alarms during 2023-2024 bull
  - Simple enough to use the same model on the main app page
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

st.set_page_config(layout="wide", page_title="Regime Backtest")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500;600&display=swap');
html, body, [class*="st-"], [data-testid] {
    font-family: 'DM Sans', sans-serif !important;
    background-color: #0A0A0F; color: #E8E8E8;
}
[data-testid="stAppViewContainer"], [data-testid="stHeader"],
section[data-testid="stMain"] { background: #0A0A0F; }
.stat-grid { display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px; }
.stat-card { background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:16px; }
.stat-lbl  { font-size:9px;letter-spacing:0.15em;color:#555;font-family:'DM Mono',monospace;margin-bottom:6px;text-transform:uppercase; }
.stat-val  { font-size:22px;font-weight:700;font-family:'DM Mono',monospace;line-height:1; }
.bear-table { width:100%;border-collapse:collapse; }
.bear-table th { font-size:9px;letter-spacing:0.15em;color:#555;text-transform:uppercase;font-family:'DM Mono',monospace;padding:10px 14px;text-align:left;border-bottom:1px solid rgba(255,255,255,0.06); }
.bear-table td { font-size:12px;color:#aaa;padding:10px 14px;border-bottom:1px solid rgba(255,255,255,0.04);font-family:'DM Mono',monospace; }
.sec-label { font-size:10px;letter-spacing:0.15em;color:#555;text-transform:uppercase;font-family:'DM Mono',monospace;margin-bottom:14px;margin-top:28px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,0.06); }
.signal-grid { display:grid;grid-template-columns:1fr 1fr;gap:16px;margin-bottom:24px; }
.signal-card { border-radius:12px;padding:18px;border:1px solid; }
</style>
""", unsafe_allow_html=True)

st.markdown(
    '<div style="font-size:10px;letter-spacing:0.2em;color:#555;text-transform:uppercase;'
    'font-family:\'DM Mono\',monospace;margin-bottom:4px;">Macro Regime Monitor</div>'
    '<h1 style="margin:0;font-size:28px;font-weight:600;letter-spacing:-0.02em;color:#E8E8E8;">'
    'Regime Backtest</h1>'
    '<p style="margin:6px 0 24px;font-size:12px;color:#555;">'
    'Two signals: 200-day moving average + Global Liquidity ROC · '
    'Both must confirm Risk-Off before switching</p>',
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

FETCH_START   = "2015-01-01"   # warmup for 200DMA
DISPLAY_START = "2019-01-01"
END           = date.today().strftime("%Y-%m-%d")
TODAY         = str(date.today())

# ─────────────────────────────────────────────────────────────────────────────
# DATA FETCH
# ─────────────────────────────────────────────────────────────────────────────

FRED_GL = {
    "walcl":      "WALCL",       # Fed balance sheet
    "ecb_assets": "ECBASSETSW",  # ECB balance sheet
    "boj_assets": "JPNASSETS",   # BOJ balance sheet
    "m2":         "M2SL",        # US M2 money supply
}


@st.cache_data(ttl=86400, show_spinner=False)
def fetch_gl_data(today_str, api_key):
    from fredapi import Fred
    fred   = Fred(api_key=api_key)
    frames = {}
    for name, sid in FRED_GL.items():
        try:
            s = fred.get_series(sid, observation_start=FETCH_START,
                                observation_end=END)
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
    for attempt in range(3):
        try:
            raw = yf.download("^GSPC", start=FETCH_START, end=END,
                              progress=False, auto_adjust=True)
            if raw.empty:
                continue
            if isinstance(raw.columns, pd.MultiIndex):
                s = raw["Close"].iloc[:, 0]
            else:
                s = raw["Close"]
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
# GLOBAL LIQUIDITY SCORE
# ─────────────────────────────────────────────────────────────────────────────

def compute_gl_score(monthly):
    """
    Global Liquidity 3-month rate of change.
    Combines Fed + ECB + BOJ balance sheets + M2.
    Returns score: positive = expanding, negative = contracting.
    Neutralizes crisis-pace QE (reactive, not bullish).
    """
    gl = pd.Series(0.0, index=monthly.index)
    count = 0

    # Fed balance sheet
    if "walcl" in monthly.columns:
        fed_3m = monthly["walcl"].pct_change(3) * 100
        fed_1m = monthly["walcl"].pct_change(1) * 100
        crisis = fed_1m > 8   # crisis QE = neutralize
        raw = np.where(fed_3m > 4,   1.0,
              np.where(fed_3m > 1.5, 0.5,
              np.where(fed_3m > 0,   0.1,
              np.where(fed_3m > -1.5,-0.5,
              np.where(fed_3m > -4, -1.0,
                                    -1.5)))))
        gl += pd.Series(np.where(crisis, 0, raw), index=monthly.index)
        count += 1

    # ECB
    if "ecb_assets" in monthly.columns and not monthly["ecb_assets"].isna().all():
        ecb_3m = monthly["ecb_assets"].pct_change(3) * 100
        ecb_1m = monthly["ecb_assets"].pct_change(1) * 100
        crisis = ecb_1m > 6
        raw = np.where(ecb_3m > 3,   0.8,
              np.where(ecb_3m > 1,   0.4,
              np.where(ecb_3m > 0,   0.1,
              np.where(ecb_3m > -1, -0.4,
              np.where(ecb_3m > -3, -0.8,
                                    -1.2)))))
        gl += pd.Series(np.where(crisis, 0, raw), index=monthly.index)
        count += 1

    # BOJ
    if "boj_assets" in monthly.columns and not monthly["boj_assets"].isna().all():
        boj_3m = monthly["boj_assets"].pct_change(3) * 100
        raw = np.where(boj_3m > 3,   0.6,
              np.where(boj_3m > 1,   0.3,
              np.where(boj_3m > 0,   0.1,
              np.where(boj_3m > -2, -0.4,
                                    -0.8))))
        gl += pd.Series(raw, index=monthly.index)
        count += 1

    # M2
    if "m2" in monthly.columns:
        m2_3m = monthly["m2"].pct_change(3) * 100
        raw = np.where(m2_3m > 2,   0.5,
              np.where(m2_3m > 0.5, 0.2,
              np.where(m2_3m > 0,   0.1,
              np.where(m2_3m > -1, -0.3,
              np.where(m2_3m > -2, -0.6,
                                   -1.0)))))
        gl += pd.Series(raw, index=monthly.index)
        count += 1

    # Normalize to -1 to +1 range
    if count > 0:
        gl = gl / count

    return gl.clip(-1, 1)


# ─────────────────────────────────────────────────────────────────────────────
# REGIME CLASSIFICATION
# ─────────────────────────────────────────────────────────────────────────────

def classify_regime(sp_daily, gl_monthly, min_months=2):
    """
    SIGNAL 1: Is price above or below 200-day MA? (daily)
    SIGNAL 2: Is global liquidity expanding or contracting? (monthly)

    RISK-OFF only when BOTH signals are negative.
    RISK-ON when EITHER signal is positive.

    Min 2-month hold before switching.
    """
    # Signal 1: price vs 200DMA (daily)
    ma200       = sp_daily.rolling(200).mean()
    above_200   = sp_daily > ma200
    above_200_m = above_200.resample("ME").last()

    # Signal 2: GL expanding (monthly)
    gl_positive = gl_monthly > 0

    # Align to same monthly index
    idx = gl_positive.index
    above_200_m = above_200_m.reindex(idx).ffill()

    # Raw regime: Risk-Off only when BOTH are negative
    raw = pd.Series("Risk-On", index=idx)
    both_negative = (~above_200_m) & (~gl_positive)
    raw[both_negative] = "Risk-Off"

    # Minimum hold
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

    return final, above_200_m, gl_positive


# ─────────────────────────────────────────────────────────────────────────────
# FETCH AND COMPUTE
# ─────────────────────────────────────────────────────────────────────────────

pb = st.progress(0, text="Fetching S&P 500...")
sp_daily = fetch_sp500(TODAY)

if sp_daily.empty:
    st.error("Could not fetch S&P 500 from yfinance. Please try again.")
    st.stop()

pb.progress(50, text="Fetching Global Liquidity data from FRED...")
monthly = fetch_gl_data(TODAY, fred_key)

pb.progress(85, text="Computing regime...")

gl_score = compute_gl_score(monthly)
regime, above_200_m, gl_pos = classify_regime(sp_daily, gl_score, min_months=2)

pb.progress(100, text="Done!")
pb.empty()

# Restrict display to 2019+
sp_disp    = sp_daily[sp_daily.index >= DISPLAY_START]
reg_disp   = regime[regime.index >= DISPLAY_START]
gl_disp    = gl_score[gl_score.index >= DISPLAY_START]
a200_disp  = above_200_m[above_200_m.index >= DISPLAY_START]
glpos_disp = gl_pos[gl_pos.index >= DISPLAY_START]

daily_regime = regime.reindex(sp_disp.index, method="ffill").ffill()

# ─────────────────────────────────────────────────────────────────────────────
# CURRENT SIGNAL STATUS
# ─────────────────────────────────────────────────────────────────────────────

cur_regime  = reg_disp.iloc[-1]
cur_color   = "#00D4AA" if cur_regime == "Risk-On" else "#FF4757"
cur_200     = a200_disp.iloc[-1]
cur_gl      = gl_disp.iloc[-1]
cur_200_str = "Above ✓" if cur_200 else "Below ✗"
cur_gl_str  = "Expanding ✓" if cur_gl > 0 else "Contracting ✗"
cur_200_col = "#00D4AA" if cur_200 else "#FF4757"
cur_gl_col  = "#00D4AA" if cur_gl > 0 else "#FF4757"

st.markdown('<div class="sec-label">Current Signal Status</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="signal-grid">'
    '<div class="signal-card" style="border-color:' + cur_200_col + '33;background:' + cur_200_col + '08;">'
    '<div style="font-size:9px;letter-spacing:0.15em;color:#555;text-transform:uppercase;'
    'font-family:\'DM Mono\',monospace;margin-bottom:8px;">Signal 1 — Price vs 200DMA</div>'
    '<div style="font-size:24px;font-weight:700;color:' + cur_200_col + ';font-family:\'DM Mono\',monospace;">'
    + cur_200_str + '</div>'
    '<div style="font-size:11px;color:#666;margin-top:6px;">'
    'S&P 500 ' + ('above' if cur_200 else 'below') + ' its 200-day moving average</div>'
    '</div>'
    '<div class="signal-card" style="border-color:' + cur_gl_col + '33;background:' + cur_gl_col + '08;">'
    '<div style="font-size:9px;letter-spacing:0.15em;color:#555;text-transform:uppercase;'
    'font-family:\'DM Mono\',monospace;margin-bottom:8px;">Signal 2 — Global Liquidity ROC</div>'
    '<div style="font-size:24px;font-weight:700;color:' + cur_gl_col + ';font-family:\'DM Mono\',monospace;">'
    + cur_gl_str + '</div>'
    '<div style="font-size:11px;color:#666;margin-top:6px;">'
    'Fed + ECB + BOJ + M2 combined 3-month rate of change: '
    + ('+' if cur_gl > 0 else '') + str(round(float(cur_gl), 3)) + '</div>'
    '</div>'
    '</div>',
    unsafe_allow_html=True
)

# Overall regime badge
st.markdown(
    '<div style="text-align:center;margin-bottom:28px;">'
    '<div style="display:inline-block;padding:10px 28px;border-radius:8px;'
    'background:' + cur_color + '18;border:1px solid ' + cur_color + '44;">'
    '<span style="font-size:11px;letter-spacing:0.2em;color:#555;font-family:\'DM Mono\',monospace;'
    'text-transform:uppercase;">Current Regime</span><br>'
    '<span style="font-size:26px;font-weight:700;color:' + cur_color + ';font-family:\'DM Mono\',monospace;">'
    + cur_regime.upper() + '</span>'
    '</div></div>',
    unsafe_allow_html=True
)

# ─────────────────────────────────────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────────────────────────────────────

on_pct      = (reg_disp == "Risk-On").mean() * 100
off_pct     = 100 - on_pct
transitions = int((reg_disp != reg_disp.shift()).sum() - 1)
date_range  = reg_disp.index[0].strftime("%b %Y") + " — " + reg_disp.index[-1].strftime("%b %Y")

st.markdown('<div class="sec-label">Regime Statistics</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="stat-grid">'
    '<div class="stat-card"><div class="stat-lbl">Period</div>'
    '<div class="stat-val" style="font-size:13px;color:#aaa;">' + date_range + '</div></div>'
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
    "COVID crash 2020":      ("2020-02", "2020-05", "bear"),
    "COVID bull 2020-2021":  ("2020-05", "2021-12", "bull"),
    "Bear 2022":             ("2022-01", "2022-10", "bear"),
    "Bull 2023-2024":        ("2022-10", "2024-12", "bull"),
    "Early 2025 crash":      ("2025-01", "2025-04", "bear"),
    "2025+ recovery":        ("2025-05", END,       "bull"),
}

st.markdown('<div class="sec-label">Key Market Periods</div>', unsafe_allow_html=True)
rows = ""
for name, (bs, be, kind) in events.items():
    try:
        w = reg_disp.loc[bs:be]
        if len(w) < 1:
            continue
        off_p = (w == "Risk-Off").mean() * 100
        on_p  = 100 - off_p
        pct_c   = off_p if kind == "bear" else on_p
        want    = "Risk-Off" if kind == "bear" else "Risk-On"
        color   = "#00D4AA" if pct_c >= 60 else ("#f59e0b" if pct_c >= 40 else "#FF4757")
        verdict = "✓ Correct" if pct_c >= 60 else ("~ Partial" if pct_c >= 40 else "✗ Missed")
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

# ── Regime shading ────────────────────────────────────────────────────────
in_reg, span_start = None, None
for d, r in zip(daily_regime.index, daily_regime.values):
    if r != in_reg:
        if in_reg is not None:
            c = "#00D4AA" if in_reg == "Risk-On" else "#FF4757"
            ax1.axvspan(span_start, d, alpha=0.18, color=c, linewidth=0)
        in_reg, span_start = r, d
if in_reg:
    c = "#00D4AA" if in_reg == "Risk-On" else "#FF4757"
    ax1.axvspan(span_start, daily_regime.index[-1], alpha=0.18, color=c, linewidth=0)

# ── Price + MAs ───────────────────────────────────────────────────────────
ax1.plot(sp_disp.index, sp_disp.values, color="#E8E8E8", linewidth=1.2, zorder=5)
ma200_d = sp_disp.rolling(200).mean()
ma50_d  = sp_disp.rolling(50).mean()
ax1.plot(ma200_d.index, ma200_d.values, color="#f59e0b", linewidth=1.0,
         alpha=0.8, linestyle="--", zorder=4, label="200DMA")
ax1.plot(ma50_d.index,  ma50_d.values,  color="#5B8DEF", linewidth=0.8,
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

p1 = mpatches.Patch(color="#00D4AA", alpha=0.5, label="Risk-On")
p2 = mpatches.Patch(color="#FF4757", alpha=0.5, label="Risk-Off")
p3 = plt.Line2D([0],[0], color="#f59e0b", linewidth=1.0, linestyle="--", label="200DMA")
p4 = plt.Line2D([0],[0], color="#5B8DEF", linewidth=0.8, label="50DMA")
ax1.legend(handles=[p1, p2, p3, p4], loc="upper left", framealpha=0,
           fontsize=8, labelcolor="#aaa")
ax1.set_title(
    "S&P 500 — Regime Model  |  Risk-Off only when price BELOW 200DMA AND GL contracting",
    color="#E8E8E8", fontsize=11, fontweight="bold", pad=10, loc="left"
)

# ── Signal 1: price vs 200DMA ─────────────────────────────────────────────
# Show % distance from 200DMA daily
pct_vs_200 = ((sp_disp / ma200_d) - 1) * 100
ax2.fill_between(pct_vs_200.index, pct_vs_200, 0,
                 where=pct_vs_200 >= 0, color="#00D4AA", alpha=0.3, interpolate=True)
ax2.fill_between(pct_vs_200.index, pct_vs_200, 0,
                 where=pct_vs_200 < 0,  color="#FF4757", alpha=0.3, interpolate=True)
ax2.plot(pct_vs_200.index, pct_vs_200.values, color="#aaa", linewidth=0.8, zorder=5)
ax2.axhline(0, color="#333", linewidth=0.8)
ax2.set_ylabel("% vs 200DMA", color="#666", fontsize=7, labelpad=6)
ax2.set_xlim(sp_disp.index[0], sp_disp.index[-1])
ax2.set_xticklabels([])
ax2.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
ax2.grid(axis="y", color="#111122", linewidth=0.5)
ax2.set_title("Signal 1 — Price vs 200DMA  (green = above, red = below)",
              color="#555", fontsize=7, pad=3, loc="left")

# ── Signal 2: Global Liquidity ROC ───────────────────────────────────────
gl_disp_vals = gl_disp.values
ax3.fill_between(gl_disp.index, gl_disp_vals, 0,
                 where=gl_disp_vals >= 0, color="#00D4AA", alpha=0.35, interpolate=True)
ax3.fill_between(gl_disp.index, gl_disp_vals, 0,
                 where=gl_disp_vals < 0,  color="#FF4757", alpha=0.35, interpolate=True)
ax3.plot(gl_disp.index, gl_disp_vals, color="#aaa", linewidth=0.9, zorder=5)
ax3.axhline(0, color="#333", linewidth=0.8)
ax3.set_ylim(-1, 1)
ax3.set_ylabel("GL ROC", color="#666", fontsize=7, labelpad=6)
ax3.set_xlim(gl_disp.index[0], gl_disp.index[-1])
ax3.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 4, 7, 10]))
ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b '%y"))
ax3.grid(axis="y", color="#111122", linewidth=0.5)
ax3.set_title("Signal 2 — Global Liquidity ROC  (green = expanding, red = contracting)",
              color="#555", fontsize=7, pad=3, loc="left")

fig.text(0.99, 0.005,
         "Generated " + TODAY + "  ·  FRED + yfinance  ·  200DMA + Global Liquidity",
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
    file_name="regime_200dma_gl_" + TODAY + ".pdf",
    mime="application/pdf",
)
