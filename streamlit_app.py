import { useState, useEffect } from "react";

const SYSTEM_PROMPT = `You are a macroeconomic analyst. Your job is to research current economic data and calculate Growth and Inflation scores based on a specific scoring framework.

You have access to web search. Use it to find the LATEST available data for each indicator. Search for real, current values.

# GROWTH SCORE FRAMEWORK (capped at +/-100):

MONETARY POLICY (25% weight, max ±55 raw points):
- Rate cut probability next 3 months (from CME FedWatch): >70% = +20, 40-70% = +10, neutral = 0, hike 40-70% = -10, hike >70% = -20
- Real rates (10Y TIPS yield): falling >0.5% over 3 months = +10, stable = 0, rising >0.5% = -10
- Fed balance sheet YoY: expanding >2% = +10, stable = 0, shrinking (QT) = -10
- Yield curve (10Y-2Y spread): steepening >50bps = +5, flat = 0, inverted >25bps = -10

GLOBAL LIQUIDITY (20% weight, max ±20 raw points):
- Global central bank balance sheets YoY: expanding >5% = +20, 2-5% = +10, stable = 0, contracting 2-5% = -10, contracting >5% = -20

FISCAL POLICY (15% weight, max ±40 raw points):
- Government spending growth YoY: >5% = +15, 2-5% = +5, flat = 0, contracting = -10
- Federal deficit change: increasing >1% GDP = +10, stable = 0, shrinking >1% GDP = -10
- Stimulus legislation: major >2% GDP = +20, moderate = +10, tightening = -10

LABOR MARKET (15% weight, max ±25 raw points):
- Unemployment rate change over 6 months: falling >0.3% = +15, stable = +5, rising 0.3-0.7% = -10, rising >0.7% = -20
- Initial jobless claims trend: falling = +5, stable = 0, rising = -10

LEADING INDICATORS (15% weight, capped ±30 raw points):
- Manufacturing PMI: >55=+10, 52-55=+5, 48-52=0, 45-48=-5, <45=-10; trend ±5
- Services PMI: >55=+8, 52-55=+4, 48-52=0, 45-48=-4, <45=-8
- LEI 6-month change: >1%=+8, slightly rising=+3, flat=0, slightly falling=-5, falling >1%=-10
- Retail sales YoY: >4%=+6, 2-4%=+3, 0-2%=0, contracting=-5, <-2%=-8; momentum ±3
- GDPNow forecast: >3%=+6, 2-3%=+3, 1-2%=0, 0-1%=-3, <0%=-6
(Clamp leading indicators subtotal to ±30)

DOLLAR STRENGTH (10% weight, max ±15 raw points):
- DXY 3-month change: falling >5% = +15, falling 2-5% = +5, stable = 0, rising 2-5% = -5, rising >5% = -15

GROWTH SCORE CALCULATION:
Raw subscores weighted: (MonPol_raw × 0.25) + (GlobalLiq_raw × 0.20) + (Fiscal_raw × 0.15) + (Labor_raw × 0.15) + (Leading_raw_clamped × 0.15) + (DXY_raw × 0.10)
Scale to ±100 and clamp.

INFLATION SCORE FRAMEWORK (capped at ±100):

INFLATION DATA (25% weight):
- CPI MoM: accelerating >0.3% = +20, 0.1-0.3% = +10, stable = 0, declining = -10, sharply declining = -20
- Core PCE: >3% = +10, 2-3% = +5, near 2% = 0, <2% = -10
- PPI trend: rising rapidly = +10, falling = -10

COMMODITY PRICES (20% weight):
- BCOM 6-month change: >10% = +15, 5-10% = +5, flat = 0, -5 to -10% = -5, < -10% = -10

MONETARY POLICY - INFLATION LENS (20% weight):
- Rate cut expectations: aggressive cuts = +15, moderate easing = +5, neutral = 0, moderate tightening = -10, aggressive tightening = -20
- Real rates: rising >0.5% = -10, falling >0.5% = +10
- Fed balance sheet: expanding = +10, shrinking = -10

LABOR MARKET - WAGES (20% weight):
- Wage growth YoY: >5% = +15, 3-5% = +5, 2-3% = 0, <2% = -10

INFLATION EXPECTATIONS (15% weight):
- 5Y breakeven 3-month change: rising >0.5% = +15, rising slightly = +5, stable = 0, falling = -10

INFLATION SCORE CALCULATION:
Weighted sum of subscores, scaled to ±100, clamped.

INSTRUCTIONS:
1. Search for current values of each indicator
2. Apply the scoring rules
3. Show your data findings and reasoning
4. Return ONLY valid JSON in this exact format:

{
  "timestamp": "ISO date string",
  "growthScore": <number -100 to 100>,
  "inflationScore": <number -100 to 100>,
  "regime": "<Risk-On Inflation|Risk-On Disinflation|Risk-Off Inflation|Risk-Off Disinflation>",
  "growthComponents": {
    "monetaryPolicy": { "score": <-55 to 55>, "details": "brief explanation with actual data values" },
    "globalLiquidity": { "score": <-20 to 20>, "details": "brief explanation with actual data values" },
    "fiscalPolicy": { "score": <-40 to 40>, "details": "brief explanation with actual data values" },
    "laborMarket": { "score": <-25 to 25>, "details": "brief explanation with actual data values" },
    "leadingIndicators": { "score": <-30 to 30>, "details": "brief explanation with actual data values" },
    "dollarStrength": { "score": <-15 to 15>, "details": "brief explanation with actual data values" }
  },
  "inflationComponents": {
    "inflationData": { "score": <number>, "details": "brief explanation with actual data values" },
    "commodityPrices": { "score": <number>, "details": "brief explanation with actual data values" },
    "monetaryPolicy": { "score": <number>, "details": "brief explanation with actual data values" },
    "laborMarket": { "score": <number>, "details": "brief explanation with actual data values" },
    "inflationExpectations": { "score": <number>, "details": "brief explanation with actual data values" }
  },
  "keyDataPoints": [
    { "label": "indicator name", "value": "current value", "source": "source name" }
  ],
  "summary": "2-3 sentence macro regime summary"
}

Return ONLY the JSON, no other text.`;

const REGIME_CONFIG = {
  "Risk-On Inflation": {
    color: "#FF6B35",
    bg: "rgba(255,107,53,0.12)",
    border: "rgba(255,107,53,0.4)",
    icon: "↗",
    desc: "Growth accelerating + Prices rising",
    favor: ["Commodities", "Energy", "Financials", "TIPS", "EM equities"],
  },
  "Risk-On Disinflation": {
    color: "#00D4AA",
    bg: "rgba(0,212,170,0.12)",
    border: "rgba(0,212,170,0.4)",
    icon: "↗",
    desc: "Growth accelerating + Prices cooling",
    favor: ["Growth equities", "Tech", "Small caps", "Corp bonds", "Crypto"],
  },
  "Risk-Off Inflation": {
    color: "#FF4757",
    bg: "rgba(255,71,87,0.12)",
    border: "rgba(255,71,87,0.4)",
    icon: "↘",
    desc: "Growth slowing + Prices rising",
    favor: ["Gold", "Commodities", "Short-dur bonds", "Cash", "Defensives"],
  },
  "Risk-Off Disinflation": {
    color: "#5B8DEF",
    bg: "rgba(91,141,239,0.12)",
    border: "rgba(91,141,239,0.4)",
    icon: "↘",
    desc: "Growth slowing + Prices cooling",
    favor: ["Long-duration Treasuries", "Gold", "Cash", "Utilities", "REITs"],
  },
};

function ScoreGauge({ score, label, color }) {
  const pct = ((score + 100) / 200) * 100;
  const isPositive = score >= 0;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={{ fontSize: 11, letterSpacing: "0.12em", textTransform: "uppercase", color: "#888", fontFamily: "'DM Mono', monospace" }}>{label}</span>
        <span style={{ fontSize: 28, fontWeight: 700, color, fontFamily: "'DM Mono', monospace", lineHeight: 1 }}>
          {isPositive ? "+" : ""}{score}
        </span>
      </div>
      <div style={{ height: 6, background: "rgba(255,255,255,0.06)", borderRadius: 3, overflow: "hidden", position: "relative" }}>
        <div style={{ position: "absolute", left: "50%", top: 0, width: 1, height: "100%", background: "rgba(255,255,255,0.2)", zIndex: 2 }} />
        <div style={{
          position: "absolute",
          height: "100%",
          background: color,
          borderRadius: 3,
          transition: "all 1s cubic-bezier(0.16,1,0.3,1)",
          left: score >= 0 ? "50%" : `${pct}%`,
          width: `${Math.abs(score) / 2}%`,
        }} />
      </div>
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span style={{ fontSize: 9, color: "#555", fontFamily: "'DM Mono', monospace" }}>-100 RISK-OFF</span>
        <span style={{ fontSize: 9, color: "#555", fontFamily: "'DM Mono', monospace" }}>RISK-ON +100</span>
      </div>
    </div>
  );
}

function ComponentBar({ label, score, maxAbs, color, details }) {
  const [open, setOpen] = useState(false);
  const pct = Math.abs(score) / maxAbs * 100;
  return (
    <div style={{ borderBottom: "1px solid rgba(255,255,255,0.05)", paddingBottom: 10, marginBottom: 10 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, cursor: "pointer" }} onClick={() => setOpen(o => !o)}>
        <span style={{ fontSize: 10, color: "#666", width: 14, flexShrink: 0, fontFamily: "'DM Mono', monospace" }}>{open ? "▾" : "▸"}</span>
        <span style={{ flex: 1, fontSize: 11, color: "#aaa", letterSpacing: "0.05em" }}>{label}</span>
        <div style={{ width: 80, height: 4, background: "rgba(255,255,255,0.06)", borderRadius: 2, overflow: "hidden", position: "relative" }}>
          <div style={{ position: "absolute", left: "50%", top: 0, width: 1, height: "100%", background: "rgba(255,255,255,0.15)" }} />
          <div style={{
            position: "absolute", height: "100%", background: color, borderRadius: 2,
            left: score >= 0 ? "50%" : `${50 - pct / 2}%`,
            width: `${pct / 2}%`,
          }} />
        </div>
        <span style={{ fontSize: 12, fontWeight: 600, color, fontFamily: "'DM Mono', monospace", width: 32, textAlign: "right" }}>
          {score >= 0 ? "+" : ""}{score}
        </span>
      </div>
      {open && details && (
        <div style={{ marginTop: 8, marginLeft: 24, padding: "8px 12px", background: "rgba(255,255,255,0.03)", borderRadius: 6, borderLeft: `2px solid ${color}40` }}>
          <p style={{ margin: 0, fontSize: 11, color: "#777", lineHeight: 1.6 }}>{details}</p>
        </div>
      )}
    </div>
  );
}

function QuadrantChart({ growthScore, inflationScore, regime }) {
  const x = 50 + (growthScore / 100) * 45;
  const y = 50 - (inflationScore / 100) * 45;
  const cfg = REGIME_CONFIG[regime] || {};
  return (
    <div style={{ position: "relative", width: "100%", paddingBottom: "100%", background: "rgba(255,255,255,0.02)", borderRadius: 12, border: "1px solid rgba(255,255,255,0.06)", overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: 0 }}>
        {/* Quadrant backgrounds */}
        <div style={{ position: "absolute", left: "50%", top: 0, right: 0, bottom: "50%", background: "rgba(255,107,53,0.04)" }} />
        <div style={{ position: "absolute", left: 0, top: 0, right: "50%", bottom: "50%", background: "rgba(255,71,87,0.04)" }} />
        <div style={{ position: "absolute", left: "50%", top: "50%", right: 0, bottom: 0, background: "rgba(0,212,170,0.04)" }} />
        <div style={{ position: "absolute", left: 0, top: "50%", right: "50%", bottom: 0, background: "rgba(91,141,239,0.04)" }} />
        {/* Axes */}
        <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 1, background: "rgba(255,255,255,0.08)" }} />
        <div style={{ position: "absolute", top: "50%", left: 0, right: 0, height: 1, background: "rgba(255,255,255,0.08)" }} />
        {/* Labels */}
        <span style={{ position: "absolute", top: 8, left: "50%", transform: "translateX(-50%)", fontSize: 8, color: "#FF4757", letterSpacing: "0.1em", fontFamily: "'DM Mono', monospace" }}>INFLATION</span>
        <span style={{ position: "absolute", bottom: 8, left: "50%", transform: "translateX(-50%)", fontSize: 8, color: "#5B8DEF", letterSpacing: "0.1em", fontFamily: "'DM Mono', monospace" }}>DISINFLATION</span>
        <span style={{ position: "absolute", right: 6, top: "50%", transform: "translateY(-50%) rotate(90deg)", fontSize: 8, color: "#00D4AA", letterSpacing: "0.1em", fontFamily: "'DM Mono', monospace", transformOrigin: "center" }}>RISK-ON</span>
        <span style={{ position: "absolute", left: 6, top: "50%", transform: "translateY(-50%) rotate(-90deg)", fontSize: 8, color: "#FF6B35", letterSpacing: "0.1em", fontFamily: "'DM Mono', monospace", transformOrigin: "center" }}>RISK-OFF</span>
        {/* Point */}
        <div style={{
          position: "absolute", width: 14, height: 14, borderRadius: "50%",
          background: cfg.color || "#fff",
          boxShadow: `0 0 16px ${cfg.color || "#fff"}80`,
          left: `calc(${x}% - 7px)`, top: `calc(${y}% - 7px)`,
          transition: "all 1s cubic-bezier(0.16,1,0.3,1)",
          zIndex: 10,
        }} />
        <div style={{
          position: "absolute", width: 28, height: 28, borderRadius: "50%",
          border: `1px solid ${cfg.color || "#fff"}40`,
          left: `calc(${x}% - 14px)`, top: `calc(${y}% - 14px)`,
          transition: "all 1s cubic-bezier(0.16,1,0.3,1)",
          animation: "pulse 2s infinite",
        }} />
      </div>
    </div>
  );
}

export default function MacroDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [tab, setTab] = useState("growth");

  async function fetchRegime() {
    setLoading(true);
    setError(null);
    setData(null);
    try {
      const res = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          model: "claude-sonnet-4-20250514",
          max_tokens: 4000,
          tools: [{ type: "web_search_20250305", name: "web_search" }],
          system: SYSTEM_PROMPT,
          messages: [{
            role: "user",
            content: `Today is ${new Date().toLocaleDateString("en-US", { month: "long", day: "numeric", year: "numeric" })}. 
            
Search for the latest values for ALL of these indicators and calculate the macro regime scores:

1. CME FedWatch - current rate cut probability next 3 months
2. 10Y TIPS real yield - current level and 3-month change
3. Federal Reserve balance sheet - current size and YoY change
4. 10Y-2Y Treasury yield spread (current)
5. Global central bank balance sheets - aggregate YoY change
6. US government spending YoY growth (latest)
7. US federal deficit as % of GDP and recent trend
8. US unemployment rate - current and 6-month change
9. Initial jobless claims - recent trend
10. ISM Manufacturing PMI - latest and 3-month trend
11. ISM Services PMI - latest reading
12. Conference Board LEI - latest 6-month change
13. US Retail Sales - latest YoY and 3-month momentum
14. Atlanta Fed GDPNow - latest forecast
15. DXY US Dollar Index - current level and 3-month change
16. CPI MoM - latest reading
17. Core PCE - latest reading
18. PPI - latest trend
19. Bloomberg Commodity Index (BCOM) - 6-month change
20. Average hourly earnings YoY wage growth
21. 5-Year breakeven inflation rate - current and 3-month change

After gathering data, calculate both Growth Score and Inflation Score using the frameworks provided. Return the JSON result.`
          }],
        }),
      });

      const raw = await res.json();
      
      // Extract text from response (may include tool use blocks)
      let jsonText = "";
      for (const block of raw.content || []) {
        if (block.type === "text") jsonText += block.text;
      }

      // Parse JSON
      const match = jsonText.match(/\{[\s\S]*\}/);
      if (!match) throw new Error("No JSON found in response");
      const parsed = JSON.parse(match[0]);
      setData(parsed);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  const regime = data?.regime;
  const cfg = regime ? REGIME_CONFIG[regime] : null;

  const growthComponents = data ? [
    { label: "Monetary Policy", score: data.growthComponents?.monetaryPolicy?.score ?? 0, max: 55, details: data.growthComponents?.monetaryPolicy?.details },
    { label: "Global Liquidity", score: data.growthComponents?.globalLiquidity?.score ?? 0, max: 20, details: data.growthComponents?.globalLiquidity?.details },
    { label: "Fiscal Policy", score: data.growthComponents?.fiscalPolicy?.score ?? 0, max: 40, details: data.growthComponents?.fiscalPolicy?.details },
    { label: "Labor Market", score: data.growthComponents?.laborMarket?.score ?? 0, max: 25, details: data.growthComponents?.laborMarket?.details },
    { label: "Leading Indicators", score: data.growthComponents?.leadingIndicators?.score ?? 0, max: 30, details: data.growthComponents?.leadingIndicators?.details },
    { label: "Dollar Strength", score: data.growthComponents?.dollarStrength?.score ?? 0, max: 15, details: data.growthComponents?.dollarStrength?.details },
  ] : [];

  const inflationComponents = data ? [
    { label: "Inflation Data", score: data.inflationComponents?.inflationData?.score ?? 0, max: 40, details: data.inflationComponents?.inflationData?.details },
    { label: "Commodity Prices", score: data.inflationComponents?.commodityPrices?.score ?? 0, max: 15, details: data.inflationComponents?.commodityPrices?.details },
    { label: "Monetary Policy", score: data.inflationComponents?.monetaryPolicy?.score ?? 0, max: 40, details: data.inflationComponents?.monetaryPolicy?.details },
    { label: "Labor Market (Wages)", score: data.inflationComponents?.laborMarket?.score ?? 0, max: 15, details: data.inflationComponents?.laborMarket?.details },
    { label: "Inflation Expectations", score: data.inflationComponents?.inflationExpectations?.score ?? 0, max: 15, details: data.inflationComponents?.inflationExpectations?.details },
  ] : [];

  return (
    <div style={{ minHeight: "100vh", background: "#0A0A0F", color: "#E8E8E8", fontFamily: "'DM Sans', sans-serif", padding: "24px 20px" }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500;600&display=swap');
        @keyframes pulse { 0%,100%{opacity:0.4;transform:scale(1)} 50%{opacity:0.8;transform:scale(1.1)} }
        @keyframes spin { to{transform:rotate(360deg)} }
        @keyframes fadeIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:translateY(0)} }
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 4px; } 
        ::-webkit-scrollbar-track { background: #111; } 
        ::-webkit-scrollbar-thumb { background: #333; border-radius: 2px; }
      `}</style>

      <div style={{ maxWidth: 900, margin: "0 auto" }}>
        {/* Header */}
        <div style={{ marginBottom: 32, display: "flex", alignItems: "flex-start", justifyContent: "space-between", flexWrap: "wrap", gap: 16 }}>
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
              <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#00D4AA", boxShadow: "0 0 8px #00D4AA" }} />
              <span style={{ fontSize: 10, letterSpacing: "0.2em", color: "#555", textTransform: "uppercase", fontFamily: "'DM Mono', monospace" }}>Macro Regime Monitor</span>
            </div>
            <h1 style={{ margin: 0, fontSize: 28, fontWeight: 600, letterSpacing: "-0.02em", lineHeight: 1.1 }}>
              Regime<span style={{ color: "#555" }}>.</span>ai
            </h1>
            <p style={{ margin: "6px 0 0", fontSize: 12, color: "#555" }}>
              Real-time macro regime detection via live economic data
            </p>
          </div>
          <button
            onClick={fetchRegime}
            disabled={loading}
            style={{
              padding: "12px 24px", background: loading ? "rgba(255,255,255,0.05)" : "rgba(255,255,255,0.08)",
              border: "1px solid rgba(255,255,255,0.12)", borderRadius: 8, color: loading ? "#555" : "#E8E8E8",
              cursor: loading ? "not-allowed" : "pointer", fontSize: 12, fontWeight: 500, letterSpacing: "0.06em",
              textTransform: "uppercase", fontFamily: "'DM Mono', monospace", display: "flex", alignItems: "center", gap: 8,
              transition: "all 0.2s",
            }}
          >
            {loading ? (
              <>
                <div style={{ width: 12, height: 12, border: "2px solid #444", borderTopColor: "#00D4AA", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
                Analyzing...
              </>
            ) : (
              <>⟳ Run Analysis</>
            )}
          </button>
        </div>

        {/* Empty State */}
        {!data && !loading && !error && (
          <div style={{ textAlign: "center", padding: "80px 20px", border: "1px dashed rgba(255,255,255,0.08)", borderRadius: 16 }}>
            <div style={{ fontSize: 40, marginBottom: 16 }}>◎</div>
            <p style={{ margin: 0, color: "#555", fontSize: 14 }}>Click <strong style={{ color: "#888" }}>Run Analysis</strong> to fetch live economic data and calculate the current macro regime</p>
            <p style={{ margin: "8px 0 0", color: "#444", fontSize: 11, fontFamily: "'DM Mono', monospace" }}>Sources: Fed, CME, BLS, ISM, Conference Board, Atlanta Fed + more</p>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div style={{ textAlign: "center", padding: "80px 20px", border: "1px dashed rgba(0,212,170,0.15)", borderRadius: 16, animation: "fadeIn 0.4s ease" }}>
            <div style={{ width: 40, height: 40, border: "2px solid rgba(0,212,170,0.2)", borderTopColor: "#00D4AA", borderRadius: "50%", animation: "spin 1s linear infinite", margin: "0 auto 20px" }} />
            <p style={{ margin: 0, color: "#666", fontSize: 13 }}>Searching live economic databases...</p>
            <p style={{ margin: "6px 0 0", color: "#444", fontSize: 11 }}>Fetching 20+ indicators · Calculating weighted scores · Determining regime</p>
          </div>
        )}

        {/* Error */}
        {error && (
          <div style={{ padding: 20, background: "rgba(255,71,87,0.08)", border: "1px solid rgba(255,71,87,0.2)", borderRadius: 12 }}>
            <p style={{ margin: 0, color: "#FF4757", fontSize: 13 }}><strong>Error:</strong> {error}</p>
          </div>
        )}

        {/* Results */}
        {data && (
          <div style={{ animation: "fadeIn 0.6s ease" }}>
            {/* Regime Banner */}
            <div style={{
              padding: "20px 24px", background: cfg.bg, border: `1px solid ${cfg.border}`,
              borderRadius: 16, marginBottom: 20, display: "flex", alignItems: "center", gap: 20, flexWrap: "wrap"
            }}>
              <div style={{ fontSize: 36, lineHeight: 1 }}>{cfg.icon}</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 10, letterSpacing: "0.15em", textTransform: "uppercase", color: `${cfg.color}99`, fontFamily: "'DM Mono', monospace", marginBottom: 2 }}>Current Regime</div>
                <div style={{ fontSize: 22, fontWeight: 600, color: cfg.color, letterSpacing: "-0.01em" }}>{regime}</div>
                <div style={{ fontSize: 12, color: "#777", marginTop: 2 }}>{cfg.desc}</div>
              </div>
              <div style={{ borderLeft: `1px solid ${cfg.border}`, paddingLeft: 20 }}>
                <div style={{ fontSize: 10, letterSpacing: "0.1em", color: "#555", textTransform: "uppercase", marginBottom: 6, fontFamily: "'DM Mono', monospace" }}>Favored Assets</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {cfg.favor.map(a => (
                    <span key={a} style={{ fontSize: 10, padding: "3px 8px", background: `${cfg.color}15`, border: `1px solid ${cfg.color}30`, borderRadius: 4, color: cfg.color, fontFamily: "'DM Mono', monospace" }}>{a}</span>
                  ))}
                </div>
              </div>
            </div>

            {/* Scores + Chart */}
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 180px", gap: 16, marginBottom: 20, alignItems: "stretch" }}>
              <div style={{ padding: 20, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 12 }}>
                <ScoreGauge score={data.growthScore} label="Growth Score" color={data.growthScore >= 0 ? "#00D4AA" : "#FF4757"} />
              </div>
              <div style={{ padding: 20, background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 12 }}>
                <ScoreGauge score={data.inflationScore} label="Inflation Score" color={data.inflationScore >= 0 ? "#FF6B35" : "#5B8DEF"} />
              </div>
              <QuadrantChart growthScore={data.growthScore} inflationScore={data.inflationScore} regime={regime} />
            </div>

            {/* Summary */}
            {data.summary && (
              <div style={{ padding: "14px 18px", background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 10, marginBottom: 20 }}>
                <p style={{ margin: 0, fontSize: 12, color: "#888", lineHeight: 1.7 }}>{data.summary}</p>
              </div>
            )}

            {/* Component Breakdown */}
            <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 12, overflow: "hidden", marginBottom: 20 }}>
              <div style={{ display: "flex", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
                {["growth", "inflation"].map(t => (
                  <button key={t} onClick={() => setTab(t)} style={{
                    flex: 1, padding: "14px 20px", background: tab === t ? "rgba(255,255,255,0.04)" : "transparent",
                    border: "none", cursor: "pointer", fontSize: 11, fontWeight: tab === t ? 600 : 400,
                    color: tab === t ? "#E8E8E8" : "#555", letterSpacing: "0.1em", textTransform: "uppercase",
                    fontFamily: "'DM Mono', monospace", borderBottom: tab === t ? `2px solid ${t === "growth" ? "#00D4AA" : "#FF6B35"}` : "2px solid transparent",
                    transition: "all 0.2s",
                  }}>
                    {t === "growth" ? `Growth Score: ${data.growthScore >= 0 ? "+" : ""}${data.growthScore}` : `Inflation Score: ${data.inflationScore >= 0 ? "+" : ""}${data.inflationScore}`}
                  </button>
                ))}
              </div>
              <div style={{ padding: "20px 24px" }}>
                {(tab === "growth" ? growthComponents : inflationComponents).map(c => (
                  <ComponentBar key={c.label} label={c.label} score={c.score} maxAbs={c.max} color={tab === "growth" ? "#00D4AA" : "#FF6B35"} details={c.details} />
                ))}
              </div>
            </div>

            {/* Key Data Points */}
            {data.keyDataPoints?.length > 0 && (
              <div style={{ background: "rgba(255,255,255,0.02)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: 12, padding: "16px 20px" }}>
                <div style={{ fontSize: 10, letterSpacing: "0.15em", color: "#555", textTransform: "uppercase", marginBottom: 14, fontFamily: "'DM Mono', monospace" }}>Live Data Snapshot</div>
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(180px, 1fr))", gap: 10 }}>
                  {data.keyDataPoints.map((dp, i) => (
                    <div key={i} style={{ padding: "10px 12px", background: "rgba(255,255,255,0.02)", borderRadius: 8, border: "1px solid rgba(255,255,255,0.05)" }}>
                      <div style={{ fontSize: 9, color: "#555", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 4 }}>{dp.label}</div>
                      <div style={{ fontSize: 14, fontWeight: 600, color: "#E8E8E8", fontFamily: "'DM Mono', monospace" }}>{dp.value}</div>
                      <div style={{ fontSize: 9, color: "#444", marginTop: 2 }}>{dp.source}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Timestamp */}
            <div style={{ textAlign: "right", marginTop: 16, fontSize: 10, color: "#444", fontFamily: "'DM Mono', monospace" }}>
              Last updated: {data.timestamp ? new Date(data.timestamp).toLocaleString() : new Date().toLocaleString()}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
