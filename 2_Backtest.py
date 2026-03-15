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

# ─────────────────────────────────────────────────────────────────────────────
# STYLING
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500;600&display=swap');
html, body, [class*="st-"], [data-testid] {
    font-family: 'DM Sans', sans-serif !important;
    background-color: #0A0A0F;
    color: #E8E8E8;
}
[data-testid="stAppViewContainer"] { background: #0A0A0F; }
[data-testid="stHeader"]           { background: #0A0A0F; }
section[data-testid="stMain"]      { background: #0A0A0F; }
.hdr-dot { width:6px;height:6px;border-radius:50%;background:#00D4AA;box-shadow:0 0 8px #00D4AA;display:inline-block;margin-right:8px;vertical-align:middle; }
.hdr-eyebrow { font-size:10px;letter-spacing:0.2em;color:#555;text-transform:uppercase;font-family:'DM Mono',monospace;margin-bottom:4px; }
.stat-grid { display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:24px; }
.stat-card { background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:10px;padding:16px; }
.stat-lbl  { font-size:9px;letter-spacing:0.15em;color:#555;font-family:'DM Mono',monospace;margin-bottom:6px;text-transform:uppercase; }
.stat-val  { font-size:22px;font-weight:700;font-family:'DM Mono',monospace;line-height:1; }
.bear-table { width:100%;border-collapse:collapse; }
.bear-table th { font-size:9px;letter-spacing:0.15em;color:#555;text-transform:uppercase;font-family:'DM Mono',monospace;padding:10px 14px;text-align:left;border-bottom:1px solid rgba(255,255,255,0.06); }
.bear-table td { font-size:12px;color:#aaa;padding:10px 14px;border-bottom:1px solid rgba(255,255,255,0.04);font-family:'DM Mono',monospace; }
.sec-label { font-size:10px;letter-spacing:0.15em;color:#555;text-transform:uppercase;font-family:'DM Mono',monospace;margin-bottom:14px;margin-top:28px;padding-bottom:10px;border-bottom:1px solid rgba(255,255,255,0.06); }
</style>
""", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# HEADER
# ─────────────────────────────────────────────────────────────────────────────

st.markdown(
    '<div class="hdr-eyebrow"><span class="hdr-dot"></span>Macro Regime Monitor</div>'
    '<h1 style="margin:0;font-size:28px;font-weight:600;letter-spacing:-0.02em;color:#E8E8E8;">Regime Backtest</h1>'
    '<p style="margin:6px 0 24px;font-size:12px;color:#555;">20-year S&P 500 overlay — green = Risk-On, red = Risk-Off</p>',
    unsafe_allow_html=True
)

# ─────────────────────────────────────────────────────────────────────────────
# FRED KEY INPUT
# ─────────────────────────────────────────────────────────────────────────────

# Try to get FRED key from Streamlit secrets first, fall back to text input
fred_key = st.secrets.get("FRED_API_KEY", None)

if not fred_key:
    fred_key = st.text_input(
        "Enter your FRED API Key",
        type="password",
        placeholder="Get a free key at fred.stlouisfed.org/docs/api/api_key.html",
        help="Free at fred.stlouisfed.org — takes 2 minutes to get"
    )
    if not fred_key:
        st.markdown(
            '<div style="padding:20px 24px;border-radius:12px;background:rgba(255,255,255,0.02);'
            'border:1px dashed rgba(255,255,255,0.08);text-align:center;color:#555;font-size:13px;">'
            'Enter your FRED API key above to run the backtest.<br>'
            '<span style="font-size:11px;color:#444;">Free key at '
            '<a href="https://fred.stlouisfed.org/docs/api/api_key.html" '
            'style="color:#00D4AA;">fred.stlouisfed.org</a></span>'
            '</div>',
            unsafe_allow_html=True
        )
        st.stop()

# ─────────────────────────────────────────────────────────────────────────────
# DATA FETCH  (cached 24h)
# ─────────────────────────────────────────────────────────────────────────────

START = "2004-01-01"
END   = date.today().strftime("%Y-%m-%d")

FRED_SERIES = {
    "unrate":      "UNRATE",
    "t10y2y":      "T10Y2Y",
    "tips10y":     "DFII10",
    "walcl":       "WALCL",
    "retail":      "RSAFS",
    "lei":         "USSLIND",
    "gdp_now":     "GDPC1",
    "dxy_proxy":   "DTWEXBGS",
    "cpi":         "CPIAUCSL",
    "core_pce":    "PCEPILFE",
    "ppi":         "PPIACO",
    "breakeven5y": "T5YIE",
    "oil":         "DCOILWTICO",
    "m2":          "M2SL",
    "rrp":         "RRPONTSYD",
    "tga":         "WTREGEN",
    "nfci":        "NFCI",
    "hy_spread":   "BAMLH0A0HYM2",
    "effr":        "FEDFUNDS",
}


@st.cache_data(ttl=86400, show_spinner=False)
def load_all_data(today_str: str, api_key: str):
    from fredapi import Fred
    import yfinance as yf

    fred = Fred(api_key=api_key)
    frames = {}
    failed = []
    for name, series_id in FRED_SERIES.items():
        try:
            s = fred.get_series(series_id, observation_start=START, observation_end=END)
            frames[name] = s
        except Exception as e:
            failed.append(series_id)

    df = pd.DataFrame(frames)
    df.index = pd.to_datetime(df.index)
    monthly = df.resample("ME").last().ffill().bfill()

    # S&P 500 daily
    sp_raw = yf.download("^GSPC", start=START, end=END, progress=False)["Close"]
    sp_daily = sp_raw.squeeze()
    sp_daily.index = pd.to_datetime(sp_daily.index)

    return monthly, sp_daily, failed


# ─────────────────────────────────────────────────────────────────────────────
# SCORING
# ─────────────────────────────────────────────────────────────────────────────

def pct_chg(s, n): return s.pct_change(n) * 100

def score_growth(m):
    s = pd.Series(0.0, index=m.index)

    # Monetary policy (25%)
    mp = pd.Series(0.0, index=m.index)
    ec = m["effr"].diff(3)
    mp += np.where(ec < -0.5, 20, np.where(ec < -0.25, 10, np.where(ec > 0.5, -20, np.where(ec > 0.25, -10, 0))))
    tc = m["tips10y"].diff(3)
    mp += np.where(tc < -0.5, 10, np.where(tc > 0.5, -10, 0))
    wy = pct_chg(m["walcl"], 12)
    mp += np.where(wy > 2, 10, np.where(wy < -0.5, -10, 0))
    yc = m["t10y2y"]; ycc = yc.diff(3)
    mp += np.where(ycc > 0.5, 5, np.where(yc < -0.25, -10, 0))
    s += mp * 0.25

    # Global liquidity (20%)
    gl = pd.Series(0.0, index=m.index)
    gl += np.where(wy > 5, 20, np.where(wy > 2, 10, np.where(wy < -5, -20, np.where(wy < -2, -10, 0))))
    s += gl * 0.20

    # Labor (15%)
    lb = pd.Series(0.0, index=m.index)
    uc = m["unrate"].diff(6)
    lb += np.where(uc < -0.3, 15, np.where(uc < 0.1, 5, np.where(uc < 0.7, -10, -20)))
    s += lb * 0.15

    # Leading (15%)
    ld = pd.Series(0.0, index=m.index)
    lc = pct_chg(m["lei"], 6)
    ld += np.where(lc > 1, 8, np.where(lc > 0, 3, np.where(lc > -1, -5, -10)))
    rc = pct_chg(m["retail"], 12)
    ld += np.where(rc > 4, 6, np.where(rc > 2, 3, np.where(rc > 0, 0, np.where(rc > -2, -5, -8))))
    gc = pct_chg(m["gdp_now"], 12)
    ld += np.where(gc > 3, 6, np.where(gc > 2, 3, np.where(gc > 1, 0, np.where(gc > 0, -3, -6))))
    s += ld.clip(-30, 30) * 0.15

    # Dollar (10%)
    dx = pd.Series(0.0, index=m.index)
    dc = pct_chg(m["dxy_proxy"], 3)
    dx += np.where(dc < -5, 15, np.where(dc < -2, 5, np.where(dc > 5, -15, np.where(dc > 2, -5, 0))))
    s += dx * 0.10

    return s.clip(-100, 100)


def score_inflation(m):
    s = pd.Series(0.0, index=m.index)

    # Inflation data (25%)
    id_ = pd.Series(0.0, index=m.index)
    cm = m["cpi"].pct_change(1) * 100
    id_ += np.where(cm > 0.3, 20, np.where(cm > 0.1, 10, np.where(cm > -0.1, 0, np.where(cm > -0.3, -10, -20))))
    py = pct_chg(m["core_pce"], 12)
    id_ += np.where(py > 3, 10, np.where(py > 2, 5, np.where(py > 1.5, 0, -10)))
    pc = pct_chg(m["ppi"], 3)
    id_ += np.where(pc > 1, 10, np.where(pc < -1, -10, 0))
    s += id_ * 0.25

    # Commodities (20%)
    oc = pct_chg(m["oil"], 6)
    co = np.where(oc > 10, 15, np.where(oc > 5, 5, np.where(oc > -5, 0, np.where(oc > -10, -5, -10))))
    s += pd.Series(co, index=m.index) * 0.20

    # Monetary policy inflation lens (20%)
    mi = pd.Series(0.0, index=m.index)
    ec = m["effr"].diff(3)
    mi += np.where(ec < -0.5, 15, np.where(ec < -0.25, 5, np.where(ec > 0.5, -20, np.where(ec > 0.25, -10, 0))))
    tc = m["tips10y"].diff(3)
    mi += np.where(tc > 0.5, -10, np.where(tc < -0.5, 10, 0))
    wy = pct_chg(m["walcl"], 12)
    mi += np.where(wy > 2, 10, np.where(wy < -0.5, -10, 0))
    s += mi * 0.20

    # Expectations (15%)
    bc = m["breakeven5y"].diff(3)
    be = np.where(bc > 0.5, 15, np.where(bc > 0.1, 5, np.where(bc > -0.1, 0, -10)))
    s += pd.Series(be, index=m.index) * 0.15

    return s.clip(-100, 100)


def score_liquidity(m):
    s = pd.Series(0.0, index=m.index)

    # CB balance sheet (40%)
    wy = pct_chg(m["walcl"], 12)
    cb = np.where(wy > 10, 40, np.where(wy > 5, 25, np.where(wy > 1, 10,
         np.where(wy > -1, 0, np.where(wy > -5, -10, np.where(wy > -10, -25, -40))))))
    s += pd.Series(cb, index=m.index) * 0.40

    # TGA/RRP (20%)
    tl = pd.Series(0.0, index=m.index)
    tc = m["tga"].diff(3)
    tl += np.where(tc < -200, 20, np.where(tc < -100, 10, np.where(tc > 200, -20, np.where(tc > 100, -10, 0))))
    rc = m["rrp"].diff(3).fillna(0)
    tl += np.where(rc < -200, 15, np.where(rc < -50, 5, np.where(rc > 200, -15, np.where(rc > 50, -5, 0))))
    s += tl * 0.20

    # Market conditions (15%)
    mk = pd.Series(0.0, index=m.index)
    my = pct_chg(m["m2"], 12)
    mk += np.where(my > 8, 10, np.where(my > 4, 5, np.where(my > 0, 0, np.where(my > -4, -5, -10))))
    nc = m["nfci"].diff(3).fillna(0)
    mk += np.where(nc < -0.4, 15, np.where(nc < -0.2, 10, np.where(nc < -0.05, 5,
          np.where(nc < 0.05, 0, np.where(nc < 0.2, -5, np.where(nc < 0.4, -10, -15))))))
    s += mk * 0.15

    # Dollar (15%)
    dc = pct_chg(m["dxy_proxy"], 3)
    dl = np.where(dc < -5, 15, np.where(dc < -2, 10, np.where(dc < 0, 5,
         np.where(dc < 2, -5, np.where(dc < 5, -10, -15)))))
    s += pd.Series(dl, index=m.index) * 0.15

    # Credit (10%)
    hc = m["hy_spread"].diff(3).fillna(0)
    cr = np.where(hc < -1, 10, np.where(hc < -0.5, 5, np.where(hc > 1, -10, np.where(hc > 0.5, -5, 0))))
    s += pd.Series(cr, index=m.index) * 0.10

    return s.clip(-100, 100)


# ─────────────────────────────────────────────────────────────────────────────
# RUN
# ─────────────────────────────────────────────────────────────────────────────

with st.spinner("Fetching 20 years of data from FRED + Yahoo Finance..."):
    try:
        monthly, sp_daily, failed = load_all_data(str(date.today()), fred_key)
    except Exception as e:
        st.error("Failed to load data: " + str(e))
        st.stop()

if failed:
    st.warning("Some FRED series unavailable: " + ", ".join(failed))

# Calculate scores
g  = score_growth(monthly)
i  = score_inflation(monthly)
l  = score_liquidity(monthly)
ra = (0.5 * l + 0.3 * g + 0.2 * i).clip(-100, 100)

regime = pd.Series("Risk-Off", index=monthly.index)
regime[ra > 0] = "Risk-On"

# Align S&P
sp_monthly = sp_daily.resample("ME").last()
combined = pd.DataFrame({
    "sp500":  sp_monthly,
    "growth": g,
    "infl":   i,
    "liq":    l,
    "ra":     ra,
    "regime": regime,
}).dropna(subset=["sp500"])

# Daily regime for shading
sp_aligned = sp_daily[sp_daily.index >= combined.index[0]]
daily_regime = regime.reindex(sp_aligned.index, method="ffill")

# ─────────────────────────────────────────────────────────────────────────────
# STATS
# ─────────────────────────────────────────────────────────────────────────────

on_pct  = (combined["regime"] == "Risk-On").mean() * 100
off_pct = 100 - on_pct
transitions = int((combined["regime"] != combined["regime"].shift()).sum() - 1)
date_range  = f"{combined.index[0].strftime('%b %Y')} — {combined.index[-1].strftime('%b %Y')}"

st.markdown('<div class="sec-label">Regime Statistics</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="stat-grid">'
    '<div class="stat-card"><div class="stat-lbl">Date Range</div>'
    '<div class="stat-val" style="font-size:14px;color:#aaa;">' + date_range + '</div></div>'
    '<div class="stat-card"><div class="stat-lbl">Risk-On</div>'
    '<div class="stat-val" style="color:#00D4AA;">' + f"{on_pct:.0f}%" + '</div></div>'
    '<div class="stat-card"><div class="stat-lbl">Risk-Off</div>'
    '<div class="stat-val" style="color:#FF4757;">' + f"{off_pct:.0f}%" + '</div></div>'
    '<div class="stat-card"><div class="stat-lbl">Regime Switches</div>'
    '<div class="stat-val" style="color:#E8E8E8;">' + str(transitions) + '</div></div>'
    '</div>',
    unsafe_allow_html=True
)

# Bear market check
bears = {
    "Dot-com 2000–02":  ("2000-03", "2002-10"),
    "GFC 2007–09":      ("2007-10", "2009-03"),
    "COVID 2020":       ("2020-02", "2020-05"),
    "Bear Market 2022": ("2022-01", "2022-10"),
}

st.markdown('<div class="sec-label">Key Bear Markets — Was the Model Risk-Off?</div>', unsafe_allow_html=True)

bear_rows = ""
for name, (s, e) in bears.items():
    try:
        window = combined.loc[s:e, "regime"]
        if len(window) == 0:
            continue
        off_p = (window == "Risk-Off").mean() * 100
        on_p  = 100 - off_p
        color = "#00D4AA" if off_p >= 60 else ("#f59e0b" if off_p >= 40 else "#FF4757")
        verdict = "✓ Defensive" if off_p >= 60 else ("~ Partial" if off_p >= 40 else "✗ Missed")
        bear_rows += (
            '<tr>'
            '<td>' + name + '</td>'
            '<td style="color:#FF4757;">' + f"{off_p:.0f}%" + ' Risk-Off</td>'
            '<td style="color:#00D4AA;">' + f"{on_p:.0f}%" + ' Risk-On</td>'
            '<td style="color:' + color + ';font-weight:600;">' + verdict + '</td>'
            '</tr>'
        )
    except:
        pass

st.markdown(
    '<div style="background:rgba(255,255,255,0.02);border:1px solid rgba(255,255,255,0.06);border-radius:12px;overflow:hidden;">'
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
    2, 1, figsize=(16, 10),
    facecolor="#0A0A0F",
    gridspec_kw={"height_ratios": [3, 1], "hspace": 0.05}
)

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
            ax1.axvspan(span_start, d, alpha=0.15, color=c, linewidth=0)
        in_regime, span_start = r, d
if in_regime:
    c = "#00D4AA" if in_regime == "Risk-On" else "#FF4757"
    ax1.axvspan(span_start, daily_regime.index[-1], alpha=0.15, color=c, linewidth=0)

# ── Price line ────────────────────────────────────────────────────────────
ax1.plot(sp_aligned.index, sp_aligned.values, color="#E8E8E8", linewidth=1.1, zorder=5)
ax1.set_yscale("log")
ax1.set_ylabel("S&P 500 (log scale)", color="#666", fontsize=8, labelpad=8)
ax1.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{x:,.0f}"))
ax1.set_xlim(sp_aligned.index[0], sp_aligned.index[-1])
ax1.set_xticklabels([])
ax1.grid(axis="y", color="#111122", linewidth=0.6)
ax1.xaxis.set_major_locator(mdates.YearLocator(2))

# ── Event markers ─────────────────────────────────────────────────────────
events = [("2008-10", "GFC"), ("2020-03", "COVID"), ("2022-01", "2022 Bear")]
for ds, lbl in events:
    try:
        ed = pd.Timestamp(ds)
        if sp_aligned.index[0] <= ed <= sp_aligned.index[-1]:
            ax1.axvline(ed, color="#333", linewidth=0.8, linestyle="--", zorder=3)
            ypos = sp_aligned.max() * 0.92
            ax1.text(ed, ypos, lbl, color="#666", fontsize=7.5, ha="center",
                     bbox=dict(boxstyle="round,pad=0.2", facecolor="#0A0A0F", edgecolor="#333", alpha=0.9))
    except:
        pass

# ── Legend ────────────────────────────────────────────────────────────────
p1 = mpatches.Patch(color="#00D4AA", alpha=0.5, label="Risk-On  (stay invested)")
p2 = mpatches.Patch(color="#FF4757", alpha=0.5, label="Risk-Off  (hold cash / hedge)")
ax1.legend(handles=[p1, p2], loc="upper left", framealpha=0,
           fontsize=8.5, labelcolor="#aaa")

ax1.set_title("S&P 500 — 20-Year Macro Regime Overlay",
              color="#E8E8E8", fontsize=11, fontweight="bold", pad=12, loc="left")

# ── Risk Appetite panel ───────────────────────────────────────────────────
ra_m = combined["ra"]
ax2.fill_between(ra_m.index, ra_m, 0, where=ra_m >= 0,
                 color="#00D4AA", alpha=0.3, interpolate=True)
ax2.fill_between(ra_m.index, ra_m, 0, where=ra_m < 0,
                 color="#FF4757", alpha=0.3, interpolate=True)
ax2.plot(ra_m.index, ra_m.values, color="#888", linewidth=0.9, zorder=5)
ax2.axhline(0, color="#333", linewidth=0.8)
ax2.set_ylim(-100, 100)
ax2.set_xlim(ra_m.index[0], ra_m.index[-1])
ax2.set_ylabel("Risk Appetite", color="#666", fontsize=8, labelpad=8)
ax2.xaxis.set_major_locator(mdates.YearLocator(2))
ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
ax2.grid(axis="y", color="#111122", linewidth=0.6)

fig.text(0.99, 0.01,
         f"Generated {date.today()}  ·  FRED + Yahoo Finance  ·  Risk Appetite = 0.5×Liquidity + 0.3×Growth + 0.2×Inflation",
         ha="right", va="bottom", color="#333", fontsize=7, fontfamily="monospace")

plt.tight_layout(rect=[0, 0.015, 1, 1])

# Show chart in Streamlit
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
    label="⬇ Download PDF",
    data=pdf_buf,
    file_name=f"regime_backtest_{date.today()}.pdf",
    mime="application/pdf",
    use_container_width=False,
)
