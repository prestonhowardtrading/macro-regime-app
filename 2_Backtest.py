"""
Macro Regime Backtest — Binary Threshold Model
================================================
Philosophy: A FEW high-conviction signals with clear thresholds.
ANY trigger fires = Risk-Off. ALL clear = Risk-On.
No weighted averages diluting strong signals.

RISK-OFF TRIGGERS (any one = Risk-Off):
  T1. Yield curve inverted (10Y-2Y < -0.1%) for 2+ months
  T2. HY credit spreads > 500bps  OR  widening > 150bps in 3 months
  T3. Rate shock: 2Y yield rises > 1.0% in 4 months
  T4. PMI below 48 for 2+ consecutive months (contraction confirmed)
  T5. Sahm Rule triggered (unemployment +0.5% from 12M low)

RISK-ON CONDITIONS (all must hold):
  All 5 triggers cleared, PLUS 2-month minimum hold before switching back.
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

st.set_page_config(layout="wide", page_title="Regime Backtest — Binary Model")

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
.trig-grid { display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-bottom:20px; }
.trig-card { border-radius:10px;padding:14px;border:1px solid rgba(255,71,87,0.25);background:rgba(255,71,87,0.05); }
.trig-title { font-size:10px;font-weight:600;letter-spacing:0.1em;text-transform:uppercase;font-family:'DM Mono',monospace;color:#FF4757;margin-bottom:6px; }
.trig-desc  { font-size:11px;color:#888;line-height:1.5; }
.trig-thresh { font-size:10px;color:#FF6B35;font-family:'DM Mono',monospace;margin-top:6px; }
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
    '— Binary Threshold Model</span></h1>'
    '<p style="margin:6px 0 24px;font-size:12px;color:#555;">'
    'Any single trigger fires = Risk-Off. All triggers clear = Risk-On. '
    'Simple, high-conviction, no dilution.</p>',
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
    "t10y2y":    "T10Y2Y",        # Yield curve 10Y-2Y
    "t10y3m":    "T10Y3M",        # Yield curve 10Y-3M
    "t2y":       "DGS2",          # 2Y Treasury yield
    "effr":      "FEDFUNDS",      # Fed funds rate
    "hy_spread": "BAMLH0A0HYM2",  # HY OAS spread
    "ig_spread": "BAMLC0A0CM",    # IG OAS spread
    "ism_mfg":   "NAPM",          # ISM Manufacturing PMI
    "ism_svc":   "NMFSL",         # ISM Services PMI
    "unrate":    "UNRATE",        # Unemployment rate
    "icsa":      "ICSA",          # Initial jobless claims
    "lei":       "USSLIND",       # Conference Board LEI
    "nfci":      "NFCI",          # Chicago Fed NFCI
    "cpi":       "CPIAUCSL",      # CPI
    "core_pce":  "PCEPILFE",      # Core PCE
    "walcl":     "WALCL",         # Fed balance sheet
    "m2":        "M2SL",          # M2
    "breakeven5y":"T5YIE",        # 5Y breakeven
    "tips10y":   "DFII10",        # 10Y TIPS
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
# BINARY TRIGGER ENGINE
# ─────────────────────────────────────────────────────────────────────────────

def compute_triggers(m):
    """
    Returns a DataFrame of boolean triggers (True = that trigger is firing).
    Any True = Risk-Off.
    """
    triggers = pd.DataFrame(index=m.index)

    # ── T1: YIELD CURVE INVERSION ─────────────────────────────────────────
    # 10Y-2Y below -0.1% — use rolling to require persistence
    yc = m["t10y2y"]
    inverted = yc < -0.1
    # Require 2 consecutive months inverted before triggering
    triggers["T1_yield_curve"] = inverted.rolling(2).sum() >= 2

    # Also check 10Y-3M (even better recession predictor per Fed research)
    if "t10y3m" in m.columns and not m["t10y3m"].isna().all():
        yc2      = m["t10y3m"]
        inv2     = yc2 < -0.1
        triggers["T1b_yield_curve_3m"] = inv2.rolling(2).sum() >= 2
    else:
        triggers["T1b_yield_curve_3m"] = False

    # ── T2: CREDIT STRESS ─────────────────────────────────────────────────
    # HY spreads elevated OR spiking fast
    if "hy_spread" in m.columns:
        hy      = m["hy_spread"]
        hy_chg  = hy.diff(3)   # 3-month change
        hy_lvl  = hy > 500     # spread above 500bps = elevated stress
        hy_spk  = hy_chg > 150 # widening 150bps in 3 months = rapid deterioration
        triggers["T2_credit_stress"] = hy_lvl | hy_spk
    else:
        triggers["T2_credit_stress"] = False

    # ── T3: RATE SHOCK ────────────────────────────────────────────────────
    # 2Y yield rises > 1.0% in 4 months — catches pure rate-driven bears (2022)
    t2y_chg4 = m["t2y"].diff(4)
    triggers["T3_rate_shock"] = t2y_chg4 > 1.0

    # Also catch very aggressive Fed hiking: effr up > 1.25% in 6 months
    effr_chg6 = m["effr"].diff(6)
    triggers["T3b_fed_hike"] = effr_chg6 > 1.25

    # ── T4: PMI CONTRACTION ───────────────────────────────────────────────
    # Manufacturing PMI below 48 for 2+ months (confirmed contraction, not noise)
    if "ism_mfg" in m.columns:
        pmi        = m["ism_mfg"]
        contracting = pmi < 48
        triggers["T4_pmi_contraction"] = contracting.rolling(2).sum() >= 2
    else:
        triggers["T4_pmi_contraction"] = False

    # ── T5: LABOR DETERIORATION (SAHM RULE) ───────────────────────────────
    # Unemployment rises 0.5% from its 12-month low = recession signal
    # This has triggered before or at the start of every recession since 1970
    unrate_12m_low = m["unrate"].rolling(12).min()
    sahm_indicator = m["unrate"] - unrate_12m_low
    triggers["T5_sahm_rule"] = sahm_indicator >= 0.5

    return triggers.fillna(False)


def apply_regime(triggers, min_duration=2):
    """
    ANY trigger = Risk-Off.
    ALL clear = Risk-On.
    Enforce minimum duration before switching.
    """
    # Any trigger firing = risk off signal
    any_trigger = triggers.any(axis=1)

    # Raw regime
    raw_regime = pd.Series("Risk-On", index=triggers.index)
    raw_regime[any_trigger] = "Risk-Off"

    # Enforce minimum duration
    final   = raw_regime.copy()
    current = raw_regime.iloc[0]
    dur     = 1

    for i in range(1, len(raw_regime)):
        proposed = raw_regime.iloc[i]
        if proposed != current:
            if dur >= min_duration:
                current = proposed
                dur     = 1
            else:
                dur += 1
        else:
            dur += 1
        final.iloc[i] = current

    return final, any_trigger


# ─────────────────────────────────────────────────────────────────────────────
# FETCH + COMPUTE
# ─────────────────────────────────────────────────────────────────────────────

pb = st.progress(0, text="Fetching FRED data...")
monthly, fred_failed = fetch_fred(TODAY, fred_key)

pb.progress(60, text="Fetching market data (S&P 500, DXY, BCOM)...")
yf_data, yf_failed = fetch_market(TODAY)

pb.progress(90, text="Computing binary triggers...")

for name, series in yf_data.items():
    if series is not None and not series.empty:
        series.index = pd.to_datetime(series.index).tz_localize(None)
        monthly[name] = series.resample("ME").last().reindex(monthly.index).ffill()

triggers        = compute_triggers(monthly)
regime, any_trig = apply_regime(triggers, min_duration=2)

pb.progress(100, text="Done!")
pb.empty()

# Align S&P 500
sp_daily = yf_data.get("sp500", pd.Series(dtype=float))
if sp_daily is None or sp_daily.empty:
    st.error("Could not fetch S&P 500. Please try again.")
    st.stop()

sp_daily.index = pd.to_datetime(sp_daily.index).tz_localize(None)
sp_monthly     = sp_daily.resample("ME").last()

combined = pd.DataFrame({
    "sp500":  sp_monthly,
    "regime": regime,
}).join(triggers).join(any_trig.rename("any_trigger"))
combined = combined.dropna(subset=["sp500"])

if combined.empty:
    st.error("No overlapping data. Please try again.")
    st.stop()

start_date   = combined.index[0]
sp_aligned   = sp_daily[sp_daily.index >= start_date].dropna()
daily_regime = regime.reindex(sp_aligned.index, method="ffill").ffill()

# ─────────────────────────────────────────────────────────────────────────────
# TRIGGER EXPLANATION
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="sec-label">Risk-Off Triggers — Any One Fires = Risk-Off</div>',
            unsafe_allow_html=True)

# Current trigger status
def trigger_status(col):
    if col in combined.columns and not combined[col].empty:
        return combined[col].iloc[-1]
    return False

t_cols = ["T1_yield_curve", "T1b_yield_curve_3m", "T2_credit_stress",
          "T3_rate_shock", "T3b_fed_hike", "T4_pmi_contraction", "T5_sahm_rule"]

st.markdown(
    '<div class="trig-grid">'

    '<div class="trig-card">'
    '<div class="trig-title">T1 — Yield Curve</div>'
    '<div class="trig-desc">10Y-2Y below -0.1% for 2+ consecutive months. '
    'Best leading recession predictor, fires 12-18 months early.</div>'
    '<div class="trig-thresh">Threshold: 10Y-2Y &lt; -0.10%</div>'
    '</div>'

    '<div class="trig-card">'
    '<div class="trig-title">T2 — Credit Stress</div>'
    '<div class="trig-desc">HY spreads above 500bps (elevated stress) '
    'OR widening more than 150bps in 3 months (rapid deterioration).</div>'
    '<div class="trig-thresh">HY &gt; 500bps OR &Delta;3M &gt; 150bps</div>'
    '</div>'

    '<div class="trig-card">'
    '<div class="trig-title">T3 — Rate Shock</div>'
    '<div class="trig-desc">2Y Treasury rises more than 1.0% in 4 months. '
    'Catches rate-driven bear markets like 2022. '
    'Also fires on Fed hiking >1.25% in 6 months.</div>'
    '<div class="trig-thresh">&Delta;4M 2Y &gt; 1.0% OR &Delta;6M EFFR &gt; 1.25%</div>'
    '</div>'

    '<div class="trig-card">'
    '<div class="trig-title">T4 — PMI Contraction</div>'
    '<div class="trig-desc">ISM Manufacturing PMI below 48 for 2+ '
    'consecutive months. Confirms economic contraction, '
    'not just a soft patch.</div>'
    '<div class="trig-thresh">PMI &lt; 48 for 2+ months</div>'
    '</div>'

    '<div class="trig-card">'
    '<div class="trig-title">T5 — Sahm Rule</div>'
    '<div class="trig-desc">Unemployment rises 0.5% from its 12-month low. '
    'Has triggered before every recession since 1970. '
    'Confirms labor market deterioration.</div>'
    '<div class="trig-thresh">Unemp - 12M low &ge; 0.5%</div>'
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

# Current trigger count
current_triggers = [c for c in t_cols
                    if c in combined.columns and combined[c].iloc[-1]]
current_status   = "RISK-OFF" if combined["regime"].iloc[-1] == "Risk-Off" else "RISK-ON"
status_color     = "#FF4757" if current_status == "RISK-OFF" else "#00D4AA"

st.markdown('<div class="sec-label">Regime Statistics</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="stat-grid">'
    '<div class="stat-card"><div class="stat-lbl">Date Range</div>'
    '<div class="stat-val" style="font-size:13px;color:#aaa;">' + date_range + '</div></div>'
    '<div class="stat-card"><div class="stat-lbl">Current Regime</div>'
    '<div class="stat-val" style="color:' + status_color + ';font-size:16px;">'
    + current_status + '</div></div>'
    '<div class="stat-card"><div class="stat-lbl">Risk-On %</div>'
    '<div class="stat-val" style="color:#00D4AA;">' + str(round(on_pct)) + '%</div></div>'
    '<div class="stat-card"><div class="stat-lbl">Risk-Off %</div>'
    '<div class="stat-val" style="color:#FF4757;">' + str(round(off_pct)) + '%</div></div>'
    '<div class="stat-card"><div class="stat-lbl">Regime Switches</div>'
    '<div class="stat-val" style="color:#E8E8E8;">' + str(transitions) + '</div></div>'
    '</div>',
    unsafe_allow_html=True
)

# ─────────────────────────────────────────────────────────────────────────────
# ACCURACY TABLE
# ─────────────────────────────────────────────────────────────────────────────

events = {
    "Dot-com 2000-02":     ("2000-03", "2002-10", "bear"),
    "GFC 2007-09":         ("2007-10", "2009-03", "bear"),
    "COVID crash 2020":    ("2020-02", "2020-05", "bear"),
    "COVID bull 2020-21":  ("2020-05", "2021-12", "bull"),
    "Bear Market 2022":    ("2022-01", "2022-10", "bear"),
    "Bull 2023-2024":      ("2022-10", "2024-12", "bull"),
}

st.markdown('<div class="sec-label">Key Market Periods — Model Accuracy</div>',
            unsafe_allow_html=True)

rows = ""
for name, (bs, be, kind) in events.items():
    try:
        window = combined.loc[bs:be, "regime"]
        if len(window) == 0:
            continue
        off_p = (window == "Risk-Off").mean() * 100
        on_p  = 100 - off_p

        if kind == "bear":
            pct_c   = off_p
            want    = "Risk-Off"
            color   = "#00D4AA" if off_p >= 60 else ("#f59e0b" if off_p >= 40 else "#FF4757")
            verdict = "✓ Avoided"  if off_p >= 60 else ("~ Partial" if off_p >= 40 else "✗ Missed")
        else:
            pct_c   = on_p
            want    = "Risk-On"
            color   = "#00D4AA" if on_p >= 70 else ("#f59e0b" if on_p >= 50 else "#FF4757")
            verdict = "✓ Captured" if on_p >= 70 else ("~ Partial" if on_p >= 50 else "✗ Missed")

        # Which triggers were active during this period?
        active = []
        for tc in t_cols:
            if tc in combined.columns:
                pct_active = combined.loc[bs:be, tc].mean() * 100
                if pct_active > 30:
                    active.append(tc.split("_")[0])

        tc_color = "#FF4757" if kind == "bear" else "#00D4AA"
        rows += (
            '<tr>'
            '<td><span style="color:' + tc_color + ';margin-right:6px;">'
            + ("▼" if kind == "bear" else "▲") + '</span>' + name + '</td>'
            '<td style="color:#aaa;">' + want + '</td>'
            '<td style="color:' + tc_color + ';">' + str(round(pct_c)) + '%</td>'
            '<td style="color:' + color + ';font-weight:600;">' + verdict + '</td>'
            '<td style="color:#555;font-size:10px;">' + (", ".join(active) if active else "—") + '</td>'
            '</tr>'
        )
    except Exception:
        pass

st.markdown(
    '<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);'
    'border-radius:12px;overflow:hidden;">'
    '<table class="bear-table"><thead><tr>'
    '<th>Period</th><th>Target</th><th>Correct %</th>'
    '<th>Verdict</th><th>Active Triggers</th>'
    '</tr></thead><tbody>' + rows + '</tbody></table></div>',
    unsafe_allow_html=True
)

# ─────────────────────────────────────────────────────────────────────────────
# CHART
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="sec-label">S&P 500 with Binary Regime Overlay</div>',
            unsafe_allow_html=True)

fig = plt.figure(figsize=(18, 12), facecolor="#0A0A0F")
gs  = fig.add_gridspec(2, 1, height_ratios=[3, 1], hspace=0.05)
ax1 = fig.add_subplot(gs[0])
ax2 = fig.add_subplot(gs[1])

for ax in [ax1, ax2]:
    ax.set_facecolor("#0A0A0F")
    ax.tick_params(colors="#555", labelsize=8)
    for spine in ax.spines.values():
        spine.set_edgecolor("#1a1a2e")

# ── Regime shading ────────────────────────────────────────────────────────
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

# ── Price line ────────────────────────────────────────────────────────────
ax1.plot(sp_aligned.index, sp_aligned.values, color="#E8E8E8",
         linewidth=1.2, zorder=5)
ax1.set_yscale("log")
ax1.set_ylabel("S&P 500 (log scale)", color="#666", fontsize=8, labelpad=8)
ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))
ax1.set_xlim(sp_aligned.index[0], sp_aligned.index[-1])
ax1.set_xticklabels([])
ax1.grid(axis="y", color="#111122", linewidth=0.5)
ax1.xaxis.set_major_locator(mdates.YearLocator(2))

# Key event markers
for ds, lbl in [("2000-03", "Dot-com top"), ("2007-07", "GFC lead"),
                ("2009-03", "GFC bottom"), ("2020-02", "COVID"),
                ("2021-11", "2021 peak"), ("2022-10", "2022 low")]:
    try:
        ed = pd.Timestamp(ds)
        if sp_aligned.index[0] <= ed <= sp_aligned.index[-1]:
            ax1.axvline(ed, color="#2a2a3a", linewidth=0.7,
                        linestyle="--", zorder=3)
            ax1.text(ed, sp_aligned.max() * 0.88, lbl, color="#555",
                     fontsize=6.5, ha="center",
                     bbox=dict(boxstyle="round,pad=0.2", facecolor="#0A0A0F",
                               edgecolor="#2a2a3a", alpha=0.9))
    except Exception:
        pass

p1 = mpatches.Patch(color="#00D4AA", alpha=0.5, label="Risk-On  (invest)")
p2 = mpatches.Patch(color="#FF4757", alpha=0.5, label="Risk-Off  (cash/hedge)")
ax1.legend(handles=[p1, p2], loc="upper left", framealpha=0,
           fontsize=8.5, labelcolor="#aaa")
ax1.set_title(
    "S&P 500 — Binary Threshold Regime Model  "
    "|  Any trigger fires = Risk-Off, all clear = Risk-On",
    color="#E8E8E8", fontsize=11, fontweight="bold", pad=10, loc="left"
)

# ── Trigger activity panel ────────────────────────────────────────────────
trig_colors = {
    "T1_yield_curve":    "#FF4757",
    "T1b_yield_curve_3m":"#FF6B35",
    "T2_credit_stress":  "#f59e0b",
    "T3_rate_shock":     "#FF4757",
    "T3b_fed_hike":      "#FF6B35",
    "T4_pmi_contraction":"#5B8DEF",
    "T5_sahm_rule":      "#00D4AA",
}
trig_labels = {
    "T1_yield_curve":    "T1 Yield Curve",
    "T1b_yield_curve_3m":"T1b 10Y-3M",
    "T2_credit_stress":  "T2 Credit",
    "T3_rate_shock":     "T3 Rate Shock",
    "T3b_fed_hike":      "T3b Fed Hike",
    "T4_pmi_contraction":"T4 PMI",
    "T5_sahm_rule":      "T5 Sahm",
}

# Stack triggers as horizontal bands (1 = firing, 0 = clear)
y_pos = 0
band_h = 1.0 / len(trig_colors)
for tc, color in trig_colors.items():
    if tc in combined.columns:
        vals = combined[tc].astype(float)
        # Shade when trigger is active
        for idx in range(len(combined) - 1):
            if vals.iloc[idx]:
                ax2.axvspan(combined.index[idx], combined.index[idx + 1],
                            ymin=y_pos, ymax=y_pos + band_h,
                            alpha=0.8, color=color, linewidth=0)
    y_pos += band_h

# Y-axis labels for trigger bands
ax2.set_xlim(combined.index[0], combined.index[-1])
ax2.set_ylim(0, 1)
ax2.set_yticks([i * band_h + band_h / 2 for i in range(len(trig_colors))])
ax2.set_yticklabels(list(trig_labels.values()), fontsize=6.5, color="#666")
ax2.xaxis.set_major_locator(mdates.YearLocator(2))
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax2.set_ylabel("Active Triggers", color="#666", fontsize=7, labelpad=8)
ax2.grid(axis="x", color="#111122", linewidth=0.5)
ax2.set_title("Trigger Heatmap — colored = firing, dark = clear",
              color="#555", fontsize=7, pad=4, loc="left")

fig.text(0.99, 0.005,
         "Generated " + TODAY + "  ·  FRED + yfinance  ·  Binary Threshold Model",
         ha="right", va="bottom", color="#333", fontsize=7,
         fontfamily="monospace")

plt.tight_layout(rect=[0, 0.01, 1, 1])
st.pyplot(fig, use_container_width=True)

# ─────────────────────────────────────────────────────────────────────────────
# PDF DOWNLOAD
# ─────────────────────────────────────────────────────────────────────────────

pdf_buf = io.BytesIO()
with PdfPages(pdf_buf) as pdf:
    pdf.savefig(fig, facecolor="#0A0A0F", dpi=180)
plt.close(fig)
pdf_buf.seek(0)

st.download_button(
    label="Download PDF",
    data=pdf_buf,
    file_name="regime_binary_" + TODAY + ".pdf",
    mime="application/pdf",
)
