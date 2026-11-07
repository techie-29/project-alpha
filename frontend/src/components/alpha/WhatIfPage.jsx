import { useMemo, useState } from "react";
import { fmtValue } from "../../utils/alphaFormat";
import { baseline, simulate } from "../../utils/whatIf";

const SLIDERS = [
  ["price", "Change your prices", -20, 20, "Raise or lower every selling price."],
  ["discount", "Give a discount on everything", 0, 30, "Extra money taken off every sale."],
  ["units", "Sell more or fewer units", -30, 30, "Your own sales push, before any price reaction."],
  ["cost", "Cost of what you sell changes", -20, 30, "Suppliers, materials, delivery."],
];
const START = { price: 0, discount: 0, units: 0, cost: 0, reaction: "little" };

function Row({ label, now, next, fmt, currency }) {
  const d = next - now, up = d > 0.0005 * Math.abs(now || 1);
  return <div className="wi-row"><span>{label}</span><b>{fmtValue(next, fmt, currency)}</b>
    <small className={Math.abs(d) < 1e-9 ? "" : up ? "wi-up" : "wi-down"}>{Math.abs(d) < 1e-9 ? "no change" : `${d > 0 ? "+" : "−"}${fmt === "pct" ? fmtValue(Math.abs(d), fmt).replace("%", " points") : fmtValue(Math.abs(d), fmt, currency)} vs now`}</small></div>;
}

export default function WhatIfPage({ report }) {
  const [s, setS] = useState(START);
  const currency = report.overview?.currency || "";
  const b = useMemo(() => baseline(report.overview?.tiles), [report]);
  if (!b) return <div className="al-panel"><h3 className="al-h3">Not enough to simulate</h3><p>The simulator needs a revenue figure, and this analysis has none. Upload sales data with an amount or price column and run again.</p></div>;
  const r = simulate(b, s);
  const moved = SLIDERS.some(([k]) => s[k] !== 0);
  return <div className="wi">
    <div className="al-panel wi-controls">
      <h3 className="al-h3">Change something</h3>
      <p className="al-muted">Move a slider to see what would happen to your business if the last period repeated with that change.</p>
      {SLIDERS.map(([k, label, min, max, hint]) => <label key={k} className="wi-slider"><span>{label}<b>{s[k] > 0 && k !== "discount" ? "+" : ""}{s[k]}%</b></span>
        <input type="range" min={min} max={max} step="1" value={s[k]} onChange={(e) => setS({ ...s, [k]: Number(e.target.value) })} aria-label={label}/><small>{hint}</small></label>)}
      {s.price !== 0 && <label className="al-field"><span>If prices change, customers…</span>
        <select value={s.reaction} onChange={(e) => setS({ ...s, reaction: e.target.value })}>
          <option value="same">buy the same amount</option><option value="little">buy a little less (or more)</option><option value="lot">react strongly</option></select></label>}
      <button type="button" className="secondary-button" disabled={!moved && s.reaction === START.reaction} onClick={() => setS(START)}>Reset</button>
    </div>
    <div className="al-panel wi-result">
      <h3 className="al-h3">What you would get</h3>
      <Row label="Revenue" now={b.revenue} next={r.revenue} fmt="money" currency={currency}/>
      {r.profit != null && <Row label="Profit" now={b.profit} next={r.profit} fmt="money" currency={currency}/>}
      {r.margin != null && <Row label="Profit margin" now={b.profit / b.revenue} next={r.margin} fmt="pct"/>}
      {r.orders != null && <Row label="Orders" now={b.orders} next={r.orders} fmt="number"/>}
      <p className="al-muted wi-note">This is simple arithmetic on your own totals for the whole period, not a forecast. Real customers may react differently, so use it to compare ideas, not to promise results.</p>
    </div>
  </div>;
}
