import { useState, useEffect } from "react";

const CACHE_KEY     = "macro-regime-v1";
const HISTORY_KEY   = (y, m) => `macro-history-${y}-${String(m+1).padStart(2,"0")}`;
const CACHE_TTL_HOURS = 24;
const HISTORY_MONTHS  = 12;

const SYSTEM_PROMPT = `You are a macroeconomic analyst. Research current economic data and calculate Growth and Inflation scores.

GROWTH SCORE FRAMEWORK (cap final ±100):
Monetary Policy (25%): rate cut prob >70%=+20, 40-70%=+10, neutral=0, hike 40-70%=-10, hike >70%=-20; real rates falling >0.5%=+10, stable=0, rising >0.5%=-10; Fed BS expanding >2% YoY=+10, stable=0, shrinking=-10; yield curve steepening >50bps=+5, flat=0, inverted >25bps=-10.
Global Liquidity (20%): global CB BS >5% YoY=+20, 2-5%=+10, stable=0, -2-5%=-10, >-5%=-20.
Fiscal Policy (15%): govt spending >5% YoY=+15, 2-5%=+5, flat=0, contracting=-10; deficit growing >1% GDP=+10, stable=0, shrinking=-10; major stimulus >2% GDP=+20, moderate=+10, tightening=-10.
Labor Market (15%): unemployment falling >0.3% 6mo=+15, stable=+5, rising 0.3-0.7%=-10, rising >0.7%=-20; claims falling=+5, stable=0, rising=-10.
Leading Indicators (15%, clamp ±30): Mfg PMI >55=+10,52-55=+5,48-52=0,45-48=-5,<45=-10,trend±5; Services PMI >55=+8,52-55=+4,48-52=0,45-48=-4,<45=-8; LEI >1% 6mo=+8,slight rise=+3,flat=0,slight fall=-5,fall >1%=-10; Retail sales >4% YoY=+6,2-4%=+3,0-2%=0,contracting=-5,<-2%=-8,momentum±3; GDPNow >3%=+6,2-3%=+3,1-2%=0,0-1%=-3,<0%=-6.
Dollar (10%): DXY falling >5% 3mo=+15, falling 2-5%=+5, stable=0, rising 2-5%=-5, rising >5%=-15.

INFLATION SCORE FRAMEWORK (cap final ±100):
Inflation Data (25%): CPI MoM >0.3%=+20,0.1-0.3%=+10,stable=0,declining=-10,sharply=-20; Core PCE >3%=+10,2-3%=+5,near 2%=0,<2%=-10; PPI rising rapidly=+10,falling=-10.
Commodities (20%): BCOM 6mo >10%=+15,5-10%=+5,flat=0,-5to-10%=-5,<-10%=-10.
Monetary Policy (20%): aggressive cuts=+15,moderate easing=+5,neutral=0,moderate tightening=-10,aggressive tightening=-20; real rates rising=-10,falling=+10; Fed BS expanding=+10,shrinking=-10.
Labor/Wages (20%): wage growth >5% YoY=+15,3-5%=+5,2-3%=0,<2%=-10.
Inflation Expectations (15%): 5Y breakeven rising >0.5% 3mo=+15,slightly=+5,stable=0,falling=-10.

Return ONLY valid JSON:
{"timestamp":"ISO","growthScore":<-100to100>,"inflationScore":<-100to100>,"regime":"<Risk-On Inflation|Risk-On Disinflation|Risk-Off Inflation|Risk-Off Disinflation>","growthComponents":{"monetaryPolicy":{"score":<n>,"details":"data+reasoning"},"globalLiquidity":{"score":<n>,"details":"data+reasoning"},"fiscalPolicy":{"score":<n>,"details":"data+reasoning"},"laborMarket":{"score":<n>,"details":"data+reasoning"},"leadingIndicators":{"score":<n>,"details":"data+reasoning"},"dollarStrength":{"score":<n>,"details":"data+reasoning"}},"inflationComponents":{"inflationData":{"score":<n>,"details":"data+reasoning"},"commodityPrices":{"score":<n>,"details":"data+reasoning"},"monetaryPolicy":{"score":<n>,"details":"data+reasoning"},"laborMarket":{"score":<n>,"details":"data+reasoning"},"inflationExpectations":{"score":<n>,"details":"data+reasoning"}},"keyDataPoints":[{"label":"name","value":"val","source":"src"}],"summary":"2-3 sentence macro summary"}`;

const HISTORY_PROMPT = (monthLabel, year, month) => `You are a macroeconomic analyst. Analyze the macro environment for ${monthLabel} and calculate Growth and Inflation scores using historical data from that period.

Use the same scoring framework as follows (cap final ±100):

GROWTH SCORE: Monetary Policy 25%, Global Liquidity 20%, Fiscal Policy 15%, Labor Market 15%, Leading Indicators 15%, Dollar 10%.
INFLATION SCORE: Inflation Data 25%, Commodities 20%, Monetary Policy 20%, Labor/Wages 20%, Inflation Expectations 15%.

Search for the economic data that was available at the end of ${monthLabel} — use indicators released during or just before that month (e.g. ISM PMI for that month, CPI for that month, unemployment rate, etc).

Return ONLY valid JSON:
{"timestamp":"${new Date(year, month, 15).toISOString()}","growthScore":<-100to100>,"inflationScore":<-100to100>,"regime":"<Risk-On Inflation|Risk-On Disinflation|Risk-Off Inflation|Risk-Off Disinflation>","growthComponents":{"monetaryPolicy":{"score":<n>,"details":"brief"},"globalLiquidity":{"score":<n>,"details":"brief"},"fiscalPolicy":{"score":<n>,"details":"brief"},"laborMarket":{"score":<n>,"details":"brief"},"leadingIndicators":{"score":<n>,"details":"brief"},"dollarStrength":{"score":<n>,"details":"brief"}},"inflationComponents":{"inflationData":{"score":<n>,"details":"brief"},"commodityPrices":{"score":<n>,"details":"brief"},"monetaryPolicy":{"score":<n>,"details":"brief"},"laborMarket":{"score":<n>,"details":"brief"},"inflationExpectations":{"score":<n>,"details":"brief"}},"keyDataPoints":[],"summary":"1-2 sentence summary of macro conditions in ${monthLabel}"}`;

const REGIME_CONFIG = {
  "Risk-On Inflation":     { color:"#BA7517", bg:"rgba(186,117,23,0.08)",  border:"rgba(186,117,23,0.25)", icon:"↗", desc:"Growth accelerating · Prices rising",    assets:["Commodities","Energy","Financials","TIPS","EM equities"],    short:"ROI"  },
  "Risk-On Disinflation":  { color:"#0F6E56", bg:"rgba(15,110,86,0.08)",   border:"rgba(15,110,86,0.25)",  icon:"↗", desc:"Growth accelerating · Prices cooling", assets:["Growth equities","Tech","Small caps","Corp bonds","Crypto"],  short:"ROD"  },
  "Risk-Off Inflation":    { color:"#993C1D", bg:"rgba(153,60,29,0.08)",   border:"rgba(153,60,29,0.25)",  icon:"↘", desc:"Growth slowing · Prices rising",      assets:["Gold","Short-dur bonds","Cash","Defensives"],                  short:"ROFI" },
  "Risk-Off Disinflation": { color:"#185FA5", bg:"rgba(24,95,165,0.08)",   border:"rgba(24,95,165,0.25)",  icon:"↘", desc:"Growth slowing · Prices cooling",     assets:["Long Treasuries","Gold","Cash","Utilities","REITs"],          short:"ROFD" },
};

const MONTH_NAMES = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function getMonthSlots(n) {
  const slots = [];
  const now = new Date();
  for (let i = n - 1; i >= 0; i--) {
    const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
    slots.push({ year: d.getFullYear(), month: d.getMonth(), label: `${MONTH_NAMES[d.getMonth()]} ${d.getFullYear()}`, short: `${MONTH_NAMES[d.getMonth()]} '${String(d.getFullYear()).slice(2)}`, isCurrent: i === 0 });
  }
  return slots;
}

function hoursAgo(iso) { return (Date.now() - new Date(iso).getTime()) / 36e5; }
function formatAge(iso) {
  const h = hoursAgo(iso);
  if (h < 1) return `${Math.round(h*60)}m ago`;
  if (h < 24) return `${Math.round(h)}h ago`;
  return `${Math.round(h/24)}d ago`;
}

async function callClaude(systemPrompt, userMsg) {
  const res = await fetch("https://api.anthropic.com/v1/messages", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model: "claude-sonnet-4-20250514",
      max_tokens: 3000,
      tools: [{ type: "web_search_20250305", name: "web_search" }],
      system: systemPrompt,
      messages: [{ role: "user", content: userMsg }],
    }),
  });
  const raw = await res.json();
  const text = (raw.content||[]).filter(b=>b.type==="text").map(b=>b.text).join("");
  const match = text.match(/\{[\s\S]*\}/);
  if (!match) throw new Error("No JSON in response");
  return JSON.parse(match[0]);
}

// ── Sub-components ──────────────────────────────────────────────────────────

function ScoreGauge({ score, label, color }) {
  return (
    <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
      <div style={{ display:"flex", justifyContent:"space-between", alignItems:"baseline" }}>
        <span style={{ fontSize:10, letterSpacing:"0.12em", textTransform:"uppercase", color:"var(--color-text-secondary)", fontFamily:"var(--font-mono)" }}>{label}</span>
        <span style={{ fontSize:26, fontWeight:500, color, fontFamily:"var(--font-mono)", lineHeight:1 }}>{score>=0?"+":""}{score}</span>
      </div>
      <div style={{ height:6, background:"var(--color-border-tertiary)", borderRadius:3, overflow:"hidden", position:"relative" }}>
        <div style={{ position:"absolute", left:"50%", top:0, width:"0.5px", height:"100%", background:"var(--color-border-secondary)", zIndex:2 }} />
        <div style={{ position:"absolute", height:"100%", background:color, borderRadius:3, transition:"all 1s cubic-bezier(0.16,1,0.3,1)", left: score>=0?"50%":`${50+score/2}%`, width:`${Math.abs(score)/2}%` }} />
      </div>
      <div style={{ display:"flex", justifyContent:"space-between" }}>
        <span style={{ fontSize:9, color:"var(--color-text-secondary)", fontFamily:"var(--font-mono)", opacity:0.5 }}>-100</span>
        <span style={{ fontSize:9, color:"var(--color-text-secondary)", fontFamily:"var(--font-mono)", opacity:0.5 }}>+100</span>
      </div>
    </div>
  );
}

function QuadrantChart({ growthScore, inflationScore, regime }) {
  const cfg = REGIME_CONFIG[regime] || {};
  const x = 50 + (growthScore/100)*42, y = 50 - (inflationScore/100)*42;
  return (
    <div style={{ position:"relative", width:"100%", paddingBottom:"100%", background:"var(--color-background-secondary)", borderRadius:"var(--border-radius-lg)", border:"0.5px solid var(--color-border-tertiary)", overflow:"hidden" }}>
      <div style={{ position:"absolute", inset:0 }}>
        <div style={{ position:"absolute", left:"50%", top:0, bottom:0, width:"0.5px", background:"var(--color-border-secondary)" }} />
        <div style={{ position:"absolute", top:"50%", left:0, right:0, height:"0.5px", background:"var(--color-border-secondary)" }} />
        <span style={{ position:"absolute", top:5, left:"50%", transform:"translateX(-50%)", fontSize:7, color:"var(--color-text-secondary)", fontFamily:"var(--font-mono)", opacity:0.5 }}>INFL</span>
        <span style={{ position:"absolute", bottom:5, left:"50%", transform:"translateX(-50%)", fontSize:7, color:"var(--color-text-secondary)", fontFamily:"var(--font-mono)", opacity:0.5 }}>DISINFL</span>
        <div style={{ position:"absolute", width:12, height:12, borderRadius:"50%", background:cfg.color||"#888", left:`calc(${x}% - 6px)`, top:`calc(${y}% - 6px)`, transition:"all 1s cubic-bezier(0.16,1,0.3,1)", boxShadow:`0 0 0 3px ${(cfg.color||"#888")}30`, zIndex:10 }} />
      </div>
    </div>
  );
}

function ComponentRow({ label, score, maxAbs, color, details }) {
  const [open, setOpen] = useState(false);
  const pct = Math.abs(score)/maxAbs*50;
  return (
    <div style={{ borderBottom:"0.5px solid var(--color-border-tertiary)", paddingBottom:10, marginBottom:10 }}>
      <div style={{ display:"flex", alignItems:"center", gap:10, cursor:"pointer" }} onClick={()=>setOpen(o=>!o)}>
        <span style={{ fontSize:10, color:"var(--color-text-secondary)", width:12, flexShrink:0, fontFamily:"var(--font-mono)" }}>{open?"▾":"▸"}</span>
        <span style={{ flex:1, fontSize:12, color:"var(--color-text-primary)" }}>{label}</span>
        <div style={{ width:80, height:4, background:"var(--color-border-tertiary)", borderRadius:2, overflow:"hidden", position:"relative", flexShrink:0 }}>
          <div style={{ position:"absolute", left:"50%", top:0, width:"0.5px", height:"100%", background:"var(--color-border-secondary)" }} />
          <div style={{ position:"absolute", height:"100%", background:color, borderRadius:2, left:score>=0?"50%":`${50-pct}%`, width:`${pct}%` }} />
        </div>
        <span style={{ fontSize:12, fontWeight:500, color, fontFamily:"var(--font-mono)", width:32, textAlign:"right" }}>{score>=0?"+":""}{score}</span>
      </div>
      {open && details && (
        <div style={{ marginTop:6, marginLeft:22, padding:"8px 12px", background:"var(--color-background-secondary)", borderRadius:"var(--border-radius-md)", borderLeft:`2px solid ${color}50`, fontSize:11, color:"var(--color-text-secondary)", lineHeight:1.7 }}>{details}</div>
      )}
    </div>
  );
}

// ── Timeline chart ───────────────────────────────────────────────────────────

function TimelineChart({ slots, history, fetchingMonths, onFetchMonth, selectedMonth, onSelectMonth }) {
  const [tooltip, setTooltip] = useState(null);

  return (
    <div style={{ background:"var(--color-background-primary)", border:"0.5px solid var(--color-border-tertiary)", borderRadius:"var(--border-radius-lg)", overflow:"hidden", marginBottom:16 }}>
      {/* Header */}
      <div style={{ padding:"12px 20px", borderBottom:"0.5px solid var(--color-border-tertiary)", display:"flex", alignItems:"center", justifyContent:"space-between" }}>
        <div>
          <span style={{ fontSize:11, fontWeight:500, color:"var(--color-text-primary)" }}>Regime shift timeline</span>
          <span style={{ fontSize:11, color:"var(--color-text-secondary)", marginLeft:8 }}>Last {HISTORY_MONTHS} months</span>
        </div>
        {/* Legend */}
        <div style={{ display:"flex", gap:12, flexWrap:"wrap" }}>
          {Object.entries(REGIME_CONFIG).map(([k,v]) => (
            <div key={k} style={{ display:"flex", alignItems:"center", gap:4 }}>
              <div style={{ width:8, height:8, borderRadius:2, background:v.color, flexShrink:0 }} />
              <span style={{ fontSize:10, color:"var(--color-text-secondary)", fontFamily:"var(--font-mono)" }}>{v.short}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Score lines + regime bars */}
      <div style={{ padding:"20px 20px 0" }}>

        {/* Score line chart area */}
        <div style={{ position:"relative", height:80, marginBottom:4 }}>
          {/* Zero line */}
          <div style={{ position:"absolute", left:0, right:0, top:"50%", height:"0.5px", background:"var(--color-border-tertiary)" }} />
          {/* +50 / -50 guides */}
          <div style={{ position:"absolute", left:0, right:0, top:"25%", height:"0.5px", background:"var(--color-border-tertiary)", opacity:0.4 }} />
          <div style={{ position:"absolute", left:0, right:0, top:"75%", height:"0.5px", background:"var(--color-border-tertiary)", opacity:0.4 }} />
          {/* Y labels */}
          <span style={{ position:"absolute", right:0, top:0, fontSize:8, fontFamily:"var(--font-mono)", color:"var(--color-text-secondary)", opacity:0.5 }}>+100</span>
          <span style={{ position:"absolute", right:0, top:"48%", fontSize:8, fontFamily:"var(--font-mono)", color:"var(--color-text-secondary)", opacity:0.5 }}>0</span>
          <span style={{ position:"absolute", right:0, bottom:0, fontSize:8, fontFamily:"var(--font-mono)", color:"var(--color-text-secondary)", opacity:0.5 }}>-100</span>

          <svg style={{ position:"absolute", inset:0, width:"100%", height:"100%", overflow:"visible" }} preserveAspectRatio="none">
            {/* Growth line */}
            {slots.map((s, i) => {
              const d = history[`${s.year}-${s.month}`];
              if (!d || i === slots.length-1) return null;
              const next = slots[i+1];
              const nd = history[`${next.year}-${next.month}`];
              if (!nd) return null;
              const x1 = (i / (slots.length-1)) * 100;
              const x2 = ((i+1) / (slots.length-1)) * 100;
              const y1 = 50 - (d.growthScore/100)*45;
              const y2 = 50 - (nd.growthScore/100)*45;
              return <line key={`g${i}`} x1={`${x1}%`} y1={`${y1}%`} x2={`${x2}%`} y2={`${y2}%`} stroke="#0F6E56" strokeWidth="1.5" strokeOpacity="0.7" />;
            })}
            {/* Inflation line */}
            {slots.map((s, i) => {
              const d = history[`${s.year}-${s.month}`];
              if (!d || i === slots.length-1) return null;
              const next = slots[i+1];
              const nd = history[`${next.year}-${next.month}`];
              if (!nd) return null;
              const x1 = (i / (slots.length-1)) * 100;
              const x2 = ((i+1) / (slots.length-1)) * 100;
              const y1 = 50 - (d.inflationScore/100)*45;
              const y2 = 50 - (nd.inflationScore/100)*45;
              return <line key={`inf${i}`} x1={`${x1}%`} y1={`${y1}%`} x2={`${x2}%`} y2={`${y2}%`} stroke="#BA7517" strokeWidth="1.5" strokeOpacity="0.7" strokeDasharray="3,2" />;
            })}
            {/* Dots */}
            {slots.map((s, i) => {
              const d = history[`${s.year}-${s.month}`];
              if (!d) return null;
              const x = (i / (slots.length-1)) * 100;
              const gy = 50 - (d.growthScore/100)*45;
              const iy = 50 - (d.inflationScore/100)*45;
              const isSelected = selectedMonth === `${s.year}-${s.month}`;
              return (
                <g key={`dots${i}`}>
                  <circle cx={`${x}%`} cy={`${gy}%`} r={isSelected?4:2.5} fill="#0F6E56" opacity="0.9" style={{cursor:"pointer"}} onClick={()=>onSelectMonth(`${s.year}-${s.month}`)} />
                  <circle cx={`${x}%`} cy={`${iy}%`} r={isSelected?4:2.5} fill="#BA7517" opacity="0.9" style={{cursor:"pointer"}} onClick={()=>onSelectMonth(`${s.year}-${s.month}`)} />
                </g>
              );
            })}
          </svg>
        </div>

        {/* Line legend */}
        <div style={{ display:"flex", gap:16, marginBottom:12, justifyContent:"flex-end" }}>
          <div style={{ display:"flex", alignItems:"center", gap:5 }}>
            <svg width="20" height="3"><line x1="0" y1="1.5" x2="20" y2="1.5" stroke="#0F6E56" strokeWidth="1.5"/></svg>
            <span style={{ fontSize:10, color:"var(--color-text-secondary)", fontFamily:"var(--font-mono)" }}>Growth</span>
          </div>
          <div style={{ display:"flex", alignItems:"center", gap:5 }}>
            <svg width="20" height="3"><line x1="0" y1="1.5" x2="20" y2="1.5" stroke="#BA7517" strokeWidth="1.5" strokeDasharray="3,2"/></svg>
            <span style={{ fontSize:10, color:"var(--color-text-secondary)", fontFamily:"var(--font-mono)" }}>Inflation</span>
          </div>
        </div>
      </div>

      {/* Regime bar row */}
      <div style={{ display:"grid", gridTemplateColumns:`repeat(${slots.length}, 1fr)`, gap:2, padding:"0 20px 16px" }}>
        {slots.map((s) => {
          const key = `${s.year}-${s.month}`;
          const d = history[key];
          const cfg = d ? (REGIME_CONFIG[d.regime] || {}) : null;
          const isFetching = fetchingMonths.has(key);
          const isSelected = selectedMonth === key;

          return (
            <div
              key={key}
              onClick={() => d && onSelectMonth(isSelected ? null : key)}
              style={{
                display:"flex", flexDirection:"column", alignItems:"center", gap:4,
                cursor: d ? "pointer" : "default",
              }}
            >
              {/* Regime color block */}
              <div style={{
                width:"100%", height:28, borderRadius:4,
                background: isFetching ? "var(--color-border-tertiary)"
                  : d ? cfg.color
                  : "var(--color-background-secondary)",
                border: isSelected ? `2px solid var(--color-text-primary)` : `0.5px solid ${d ? cfg.color+"50" : "var(--color-border-tertiary)"}`,
                display:"flex", alignItems:"center", justifyContent:"center",
                transition:"all 0.2s", opacity: d ? 1 : 0.4,
                position:"relative", overflow:"hidden",
              }}>
                {isFetching && (
                  <div style={{ width:8, height:8, border:"1px solid rgba(255,255,255,0.5)", borderTopColor:"transparent", borderRadius:"50%", animation:"spin 0.8s linear infinite" }} />
                )}
                {!isFetching && !d && (
                  <button
                    onClick={(e) => { e.stopPropagation(); onFetchMonth(s); }}
                    style={{ background:"none", border:"none", cursor:"pointer", fontSize:12, color:"var(--color-text-secondary)", padding:0, lineHeight:1 }}
                    title={`Fetch ${s.label}`}
                  >+</button>
                )}
                {!isFetching && d && (
                  <span style={{ fontSize:8, fontFamily:"var(--font-mono)", color:"white", fontWeight:500, opacity:0.85, letterSpacing:"0.05em" }}>{cfg.short}</span>
                )}
                {s.isCurrent && (
                  <div style={{ position:"absolute", top:2, right:2, width:4, height:4, borderRadius:"50%", background:"white", opacity:0.6 }} />
                )}
              </div>
              {/* Month label */}
              <span style={{ fontSize:9, fontFamily:"var(--font-mono)", color: isSelected ? "var(--color-text-primary)" : "var(--color-text-secondary)", letterSpacing:"0.04em", opacity: isSelected ? 1 : 0.7 }}>{s.short}</span>
            </div>
          );
        })}
      </div>

      {/* Selected month detail */}
      {selectedMonth && history[selectedMonth] && (() => {
        const d = history[selectedMonth];
        const cfg = REGIME_CONFIG[d.regime] || {};
        return (
          <div style={{ borderTop:"0.5px solid var(--color-border-tertiary)", padding:"12px 20px", background:"var(--color-background-secondary)", display:"flex", alignItems:"center", gap:16, flexWrap:"wrap" }}>
            <div style={{ display:"flex", alignItems:"center", gap:8 }}>
              <div style={{ width:10, height:10, borderRadius:2, background:cfg.color }} />
              <span style={{ fontSize:13, fontWeight:500, color:cfg.color }}>{d.regime}</span>
            </div>
            <div style={{ display:"flex", gap:16 }}>
              <span style={{ fontSize:11, fontFamily:"var(--font-mono)", color:"var(--color-text-secondary)" }}>
                Growth: <span style={{ color:"#0F6E56", fontWeight:500 }}>{d.growthScore>=0?"+":""}{Math.round(d.growthScore)}</span>
              </span>
              <span style={{ fontSize:11, fontFamily:"var(--font-mono)", color:"var(--color-text-secondary)" }}>
                Inflation: <span style={{ color:"#BA7517", fontWeight:500 }}>{d.inflationScore>=0?"+":""}{Math.round(d.inflationScore)}</span>
              </span>
            </div>
            {d.summary && <p style={{ flex:1, margin:0, fontSize:11, color:"var(--color-text-secondary)", lineHeight:1.6 }}>{d.summary}</p>}
            <button onClick={()=>onSelectMonth(null)} style={{ background:"none", border:"none", cursor:"pointer", fontSize:13, color:"var(--color-text-secondary)", padding:"2px 6px" }}>✕</button>
          </div>
        );
      })()}
    </div>
  );
}

// ── Main dashboard ───────────────────────────────────────────────────────────

export default function MacroDashboard() {
  const [data, setData]             = useState(null);
  const [status, setStatus]         = useState("loading");
  const [cacheAge, setCacheAge]     = useState(null);
  const [tab, setTab]               = useState("growth");
  const [errorMsg, setErrorMsg]     = useState("");
  const [history, setHistory]       = useState({});       // { "2025-2": {...} }
  const [fetchingMonths, setFetchingMonths] = useState(new Set());
  const [selectedMonth, setSelectedMonth]  = useState(null);

  const slots = getMonthSlots(HISTORY_MONTHS);
  const nowSlot = slots[slots.length - 1];

  useEffect(() => { loadFromCache(); }, []);

  async function loadFromCache() {
    setStatus("loading");
    try {
      const result = await window.storage.get(CACHE_KEY, true);
      if (result && result.value) {
        const cached = JSON.parse(result.value);
        setData(cached);
        setCacheAge(formatAge(cached.timestamp));
        // seed current month in history
        setHistory(h => ({ ...h, [`${nowSlot.year}-${nowSlot.month}`]: cached }));
        setStatus("cached");
      } else {
        setStatus("empty");
      }
    } catch { setStatus("empty"); }

    // Load existing history slots from shared cache
    for (const s of slots.slice(0, -1)) {
      const key = HISTORY_KEY(s.year, s.month);
      try {
        const r = await window.storage.get(key, true);
        if (r && r.value) {
          setHistory(h => ({ ...h, [`${s.year}-${s.month}`]: JSON.parse(r.value) }));
        }
      } catch {}
    }
  }

  async function runRefresh() {
    setStatus("refreshing");
    setErrorMsg("");
    try {
      const today = new Date().toLocaleDateString("en-US", { month:"long", day:"numeric", year:"numeric" });
      const parsed = await callClaude(SYSTEM_PROMPT,
        `Today is ${today}. Fetch latest values for: CME FedWatch rate cut probability, 10Y TIPS real yield + 3mo change, Fed balance sheet YoY, 10Y-2Y spread, global CB balance sheets, US govt spending YoY, unemployment rate + 6mo trend, ISM Manufacturing PMI + trend, ISM Services PMI, Conference Board LEI 6mo, retail sales YoY + momentum, Atlanta Fed GDPNow, DXY 3mo change, CPI MoM, Core PCE, PPI trend, BCOM 6mo change, average hourly earnings YoY, 5Y breakeven + 3mo change. Calculate both scores. Return only JSON.`
      );
      parsed.timestamp = parsed.timestamp || new Date().toISOString();

      await window.storage.set(CACHE_KEY, JSON.stringify(parsed), true);
      // Also save to this month's history slot
      await window.storage.set(HISTORY_KEY(nowSlot.year, nowSlot.month), JSON.stringify(parsed), true);

      setData(parsed);
      setCacheAge(formatAge(parsed.timestamp));
      setHistory(h => ({ ...h, [`${nowSlot.year}-${nowSlot.month}`]: parsed }));
      setStatus("cached");
    } catch(e) {
      setErrorMsg(e.message);
      setStatus(data ? "cached" : "error");
    }
  }

  async function fetchHistoryMonth(slot) {
    const key = `${slot.year}-${slot.month}`;
    setFetchingMonths(s => new Set([...s, key]));
    try {
      const parsed = await callClaude(
        HISTORY_PROMPT(slot.label, slot.year, slot.month),
        `Analyze the macro environment for ${slot.label}. Search for economic data from that period and calculate the regime scores. Return only JSON.`
      );
      parsed.timestamp = parsed.timestamp || new Date(slot.year, slot.month, 15).toISOString();
      await window.storage.set(HISTORY_KEY(slot.year, slot.month), JSON.stringify(parsed), true);
      setHistory(h => ({ ...h, [key]: parsed }));
    } catch(e) {
      setErrorMsg(`Failed to fetch ${slot.label}: ${e.message}`);
    } finally {
      setFetchingMonths(s => { const n = new Set(s); n.delete(key); return n; });
    }
  }

  const isStale = data ? hoursAgo(data.timestamp) >= CACHE_TTL_HOURS : true;
  const cfg = data ? (REGIME_CONFIG[data.regime] || {}) : {};

  const activeComps = tab === "growth"
    ? [
        { label:"Monetary Policy",    key:"monetaryPolicy",    max:55 },
        { label:"Global Liquidity",   key:"globalLiquidity",   max:20 },
        { label:"Fiscal Policy",      key:"fiscalPolicy",      max:40 },
        { label:"Labor Market",       key:"laborMarket",       max:25 },
        { label:"Leading Indicators", key:"leadingIndicators", max:30 },
        { label:"Dollar Strength",    key:"dollarStrength",    max:15 },
      ]
    : [
        { label:"Inflation Data (CPI/PCE/PPI)", key:"inflationData",        max:40 },
        { label:"Commodity Prices",             key:"commodityPrices",       max:15 },
        { label:"Monetary Policy",              key:"monetaryPolicy",        max:40 },
        { label:"Labor Market (Wages)",         key:"laborMarket",           max:15 },
        { label:"Inflation Expectations",       key:"inflationExpectations", max:15 },
      ];
  const activeSource = tab === "growth" ? data?.growthComponents : data?.inflationComponents;
  const activeColor  = tab === "growth" ? "#0F6E56" : "#BA7517";

  return (
    <div style={{ minHeight:"100vh", background:"var(--color-background-tertiary)", padding:"24px 20px", fontFamily:"var(--font-sans)" }}>
      <style>{`
        @keyframes spin { to { transform:rotate(360deg); } }
        @keyframes fadeIn { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:translateY(0)} }
        .fade-in { animation: fadeIn 0.5s ease forwards; }
      `}</style>

      <div style={{ maxWidth:900, margin:"0 auto" }}>

        {/* Header */}
        <div style={{ display:"flex", alignItems:"flex-start", justifyContent:"space-between", flexWrap:"wrap", gap:12, marginBottom:24 }}>
          <div>
            <div style={{ fontSize:10, fontFamily:"var(--font-mono)", color:"var(--color-text-secondary)", letterSpacing:"0.18em", marginBottom:4 }}>MACRO REGIME MONITOR</div>
            <h1 style={{ margin:0, fontSize:22, fontWeight:500, color:"var(--color-text-primary)", letterSpacing:"-0.01em" }}>Regime<span style={{ color:"var(--color-text-secondary)" }}>.</span>ai</h1>
            <p style={{ margin:"4px 0 0", fontSize:12, color:"var(--color-text-secondary)" }}>Live economic data → regime classification</p>
          </div>
          <div style={{ display:"flex", flexDirection:"column", alignItems:"flex-end", gap:6 }}>
            {data && (
              <div style={{ display:"flex", alignItems:"center", gap:6 }}>
                <div style={{ width:6, height:6, borderRadius:"50%", background:isStale?"#BA7517":"#0F6E56" }} />
                <span style={{ fontSize:11, fontFamily:"var(--font-mono)", color:"var(--color-text-secondary)" }}>
                  {isStale?"Stale":"Fresh"} · {cacheAge} · shared cache
                </span>
              </div>
            )}
            <button
              onClick={runRefresh}
              disabled={status==="refreshing"||status==="loading"}
              style={{ display:"flex", alignItems:"center", gap:8, padding:"9px 18px", background:"var(--color-background-primary)", border:"0.5px solid var(--color-border-secondary)", borderRadius:"var(--border-radius-md)", cursor:(status==="refreshing"||status==="loading")?"not-allowed":"pointer", fontSize:11, fontFamily:"var(--font-mono)", letterSpacing:"0.08em", color:"var(--color-text-primary)", opacity:(status==="refreshing"||status==="loading")?0.5:1, transition:"all 0.2s" }}
            >
              {status==="refreshing"
                ? <><div style={{ width:11, height:11, border:"1.5px solid var(--color-border-secondary)", borderTopColor:"#0F6E56", borderRadius:"50%", animation:"spin 0.8s linear infinite" }} /> Fetching...</>
                : <>{isStale?"⟳ Refresh data":"⟳ Force refresh"}</>
              }
            </button>
            {isStale && data && status!=="refreshing" && (
              <span style={{ fontSize:10, color:"#BA7517", fontFamily:"var(--font-mono)" }}>Data is {Math.round(hoursAgo(data.timestamp))}h old · refresh recommended</span>
            )}
          </div>
        </div>

        {errorMsg && (
          <div style={{ padding:"10px 14px", background:"var(--color-background-danger)", border:"0.5px solid var(--color-border-danger)", borderRadius:"var(--border-radius-md)", marginBottom:16, fontSize:12, color:"var(--color-text-danger)" }}>
            {errorMsg}
          </div>
        )}

        {status==="loading" && (
          <div style={{ textAlign:"center", padding:"60px 20px" }}>
            <div style={{ width:24, height:24, border:"2px solid var(--color-border-tertiary)", borderTopColor:"#0F6E56", borderRadius:"50%", animation:"spin 0.8s linear infinite", margin:"0 auto 12px" }} />
            <div style={{ fontSize:13, color:"var(--color-text-secondary)" }}>Loading shared cache...</div>
          </div>
        )}

        {(status==="empty"||(status==="refreshing"&&!data)) && (
          <div style={{ textAlign:"center", padding:"60px 20px", border:"0.5px dashed var(--color-border-secondary)", borderRadius:"var(--border-radius-lg)" }}>
            {status==="refreshing"
              ? <><div style={{ width:28, height:28, border:"2px solid var(--color-border-tertiary)", borderTopColor:"#0F6E56", borderRadius:"50%", animation:"spin 1s linear infinite", margin:"0 auto 16px" }} /><div style={{ fontSize:13, color:"var(--color-text-secondary)" }}>Searching live economic databases...</div><div style={{ marginTop:10, padding:"7px 14px", background:"var(--color-background-secondary)", borderRadius:"var(--border-radius-md)", display:"inline-block", fontSize:11, color:"var(--color-text-secondary)", fontFamily:"var(--font-mono)" }}>Result shared with all users for {CACHE_TTL_HOURS}h</div></>
              : <><div style={{ fontSize:24, marginBottom:12, color:"var(--color-text-secondary)" }}>◎</div><div style={{ fontSize:13, color:"var(--color-text-secondary)" }}>No cached data. Click <strong style={{ color:"var(--color-text-primary)" }}>Refresh data</strong> to run the first analysis.</div><div style={{ fontSize:11, color:"var(--color-text-secondary)", marginTop:6, opacity:0.6 }}>Result shared with all users · {CACHE_TTL_HOURS}h TTL</div></>
            }
          </div>
        )}

        {data && (
          <div className="fade-in">

            {status==="refreshing" && (
              <div style={{ padding:"10px 14px", background:"var(--color-background-info)", border:"0.5px solid var(--color-border-info)", borderRadius:"var(--border-radius-md)", marginBottom:16, fontSize:12, color:"var(--color-text-info)", display:"flex", alignItems:"center", gap:8 }}>
                <div style={{ width:11, height:11, border:"1.5px solid currentColor", borderTopColor:"transparent", borderRadius:"50%", animation:"spin 0.8s linear infinite", opacity:0.6, flexShrink:0 }} />
                Refreshing in background — current results shown below
              </div>
            )}

            {/* Regime banner */}
            <div style={{ padding:"16px 20px", background:cfg.bg, border:`0.5px solid ${cfg.border}`, borderRadius:"var(--border-radius-lg)", marginBottom:16, display:"flex", alignItems:"center", gap:16, flexWrap:"wrap" }}>
              <div style={{ fontSize:28, lineHeight:1 }}>{cfg.icon}</div>
              <div style={{ flex:1 }}>
                <div style={{ fontSize:9, fontFamily:"var(--font-mono)", letterSpacing:"0.14em", color:cfg.color, opacity:0.7, marginBottom:2 }}>CURRENT REGIME</div>
                <div style={{ fontSize:20, fontWeight:500, color:cfg.color }}>{data.regime}</div>
                <div style={{ fontSize:12, color:"var(--color-text-secondary)", marginTop:2 }}>{cfg.desc}</div>
              </div>
              <div style={{ borderLeft:"0.5px solid var(--color-border-tertiary)", paddingLeft:16 }}>
                <div style={{ fontSize:9, fontFamily:"var(--font-mono)", color:"var(--color-text-secondary)", letterSpacing:"0.1em", marginBottom:8 }}>FAVORED ASSETS</div>
                <div style={{ display:"flex", flexWrap:"wrap", gap:5 }}>
                  {(cfg.assets||[]).map(a=>(
                    <span key={a} style={{ fontSize:10, padding:"3px 8px", borderRadius:"var(--border-radius-md)", border:`0.5px solid ${cfg.border}`, color:cfg.color, fontFamily:"var(--font-mono)", background:cfg.bg }}>{a}</span>
                  ))}
                </div>
              </div>
            </div>

            {/* Scores + quadrant */}
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 130px", gap:12, marginBottom:16 }}>
              <div style={{ padding:16, background:"var(--color-background-primary)", border:"0.5px solid var(--color-border-tertiary)", borderRadius:"var(--border-radius-lg)" }}>
                <ScoreGauge score={Math.round(data.growthScore)} label="Growth Score" color={data.growthScore>=0?"#0F6E56":"#993C1D"} />
              </div>
              <div style={{ padding:16, background:"var(--color-background-primary)", border:"0.5px solid var(--color-border-tertiary)", borderRadius:"var(--border-radius-lg)" }}>
                <ScoreGauge score={Math.round(data.inflationScore)} label="Inflation Score" color={data.inflationScore>=0?"#BA7517":"#185FA5"} />
              </div>
              <QuadrantChart growthScore={Math.round(data.growthScore)} inflationScore={Math.round(data.inflationScore)} regime={data.regime} />
            </div>

            {/* Summary */}
            {data.summary && (
              <div style={{ padding:"12px 16px", background:"var(--color-background-secondary)", borderRadius:"var(--border-radius-md)", marginBottom:16, fontSize:12, color:"var(--color-text-secondary)", lineHeight:1.7 }}>
                {data.summary}
              </div>
            )}

            {/* ── TIMELINE ── */}
            <TimelineChart
              slots={slots}
              history={history}
              fetchingMonths={fetchingMonths}
              onFetchMonth={fetchHistoryMonth}
              selectedMonth={selectedMonth}
              onSelectMonth={setSelectedMonth}
            />

            {/* Component breakdown */}
            <div style={{ background:"var(--color-background-primary)", border:"0.5px solid var(--color-border-tertiary)", borderRadius:"var(--border-radius-lg)", overflow:"hidden", marginBottom:16 }}>
              <div style={{ display:"flex", borderBottom:"0.5px solid var(--color-border-tertiary)" }}>
                {["growth","inflation"].map(t=>(
                  <button key={t} onClick={()=>setTab(t)} style={{ flex:1, padding:"11px 16px", background:"transparent", border:"none", borderBottom:tab===t?`2px solid ${t==="growth"?"#0F6E56":"#BA7517"}`:"2px solid transparent", cursor:"pointer", fontSize:11, fontFamily:"var(--font-mono)", letterSpacing:"0.08em", color:tab===t?"var(--color-text-primary)":"var(--color-text-secondary)", fontWeight:tab===t?500:400, transition:"all 0.2s" }}>
                    {t==="growth"?`Growth · ${data.growthScore>=0?"+":""}${Math.round(data.growthScore)}`:`Inflation · ${data.inflationScore>=0?"+":""}${Math.round(data.inflationScore)}`}
                  </button>
                ))}
              </div>
              <div style={{ padding:"16px 20px" }}>
                {activeComps.map(c => {
                  const comp=(activeSource||{})[c.key]||{};
                  return <ComponentRow key={c.label} label={c.label} score={Math.round(comp.score||0)} maxAbs={c.max} color={activeColor} details={comp.details} />;
                })}
              </div>
            </div>

            {/* Data snapshot */}
            {(data.keyDataPoints||[]).length>0 && (
              <div style={{ background:"var(--color-background-secondary)", borderRadius:"var(--border-radius-lg)", padding:"14px 18px", marginBottom:16 }}>
                <div style={{ fontSize:10, fontFamily:"var(--font-mono)", color:"var(--color-text-secondary)", letterSpacing:"0.14em", marginBottom:12 }}>LIVE DATA SNAPSHOT</div>
                <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill,minmax(150px,1fr))", gap:8 }}>
                  {data.keyDataPoints.map((dp,i)=>(
                    <div key={i} style={{ padding:"10px 12px", background:"var(--color-background-primary)", borderRadius:"var(--border-radius-md)", border:"0.5px solid var(--color-border-tertiary)" }}>
                      <div style={{ fontSize:9, fontFamily:"var(--font-mono)", color:"var(--color-text-secondary)", textTransform:"uppercase", letterSpacing:"0.07em", marginBottom:3 }}>{dp.label}</div>
                      <div style={{ fontSize:14, fontWeight:500, fontFamily:"var(--font-mono)", color:"var(--color-text-primary)" }}>{dp.value}</div>
                      <div style={{ fontSize:9, color:"var(--color-text-secondary)", marginTop:2, opacity:0.7 }}>{dp.source}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", flexWrap:"wrap", gap:8 }}>
              <span style={{ fontSize:10, fontFamily:"var(--font-mono)", color:"var(--color-text-secondary)", opacity:0.4 }}>Shared cache · stale after {CACHE_TTL_HOURS}h · history stored per month</span>
              <span style={{ fontSize:10, fontFamily:"var(--font-mono)", color:"var(--color-text-secondary)", opacity:0.4 }}>Updated: {new Date(data.timestamp).toLocaleString()}</span>
            </div>

          </div>
        )}
      </div>
    </div>
  );
}
