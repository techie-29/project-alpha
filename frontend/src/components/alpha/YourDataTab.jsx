import { useState } from "react";
import { Spark, TrendChart, BarList } from "./Charts";
import { amount, num, percent, signedPercent } from "../../utils/alphaFormat";

function Kpi({ k }) {
  const change = k.change_is_points ? (k.change_recent == null ? null : `${k.change_recent > 0 ? "+" : ""}${(k.change_recent * 100).toFixed(1)} points`) : (k.change_recent == null ? null : signedPercent(k.change_recent));
  const value = k.kind === "rate" ? percent(k.value, 1) : k.kind === "money" ? amount(k.value, k.unit) : num(k.value);
  return <div className="al-kpi">
    <span>{k.label}</span>
    <strong>{value}</strong>
    {change && <small>{change} <i>{k.recent_label}</i></small>}
    {k.change_year != null && <small>{signedPercent(k.change_year)} <i>vs the year before</i></small>}
    {k.note && <small><i>{k.note}</i></small>}
    {k.spark && <Spark values={k.spark}/>}
  </div>;
}

function View({ v }) {
  const [serie, setSerie] = useState(0);
  const s = v.series[serie];
  return <section className="al-stack">
    <div className="al-view-head">
      <h3 className="al-h3">{v.view}</h3>
      <p className="al-muted">{v.rows_total.toLocaleString()} rows, {v.from.slice(0, 10)} to {v.to.slice(0, 10)}, looked at {v.step} by {v.step}. {v.rows_counted.toLocaleString()} rows count toward amounts.</p>
    </div>
    <div className="al-kpis">{v.kpis.map((k) => <Kpi key={k.label} k={k}/>)}</div>
    {s && <div className="al-panel">
      <div className="al-panel-head"><h4>{s.name} over time</h4>{v.series.length > 1 && <select value={serie} onChange={(e) => setSerie(Number(e.target.value))} aria-label="Choose currency">{v.series.map((x, i) => <option key={x.name} value={i}>{x.name}</option>)}</select>}</div>
      <TrendChart labels={s.labels} values={s.values} unit={s.unit}/>
    </div>}
    {v.weekday && <div className="al-panel"><h4>Average {v.weekday.measure} by day of the week</h4><BarList labels={v.weekday.labels} values={v.weekday.values} unit={v.weekday.unit}/></div>}
    {v.breakdowns.length > 0 && <div className="al-grid2">{v.breakdowns.map((b) => <div className="al-panel" key={b.column}>
      <h4>{b.measure} by {b.column.replaceAll("_", " ")}</h4>
      <table className="al-table al-compact"><thead><tr><th>Group</th><th>{b.unit || "Amount"}</th><th>Share</th><th>vs last year</th></tr></thead>
        <tbody>{b.rows.map((r) => <tr key={r.value}><td>{r.value}</td><td>{num(r.amount)}</td><td><span className="al-bar"><i style={{ width: `${Math.min(100, r.share * 100)}%` }}/></span>{percent(r.share)}</td><td>{signedPercent(r.change_year)}</td></tr>)}</tbody></table>
    </div>)}</div>}
    {v.outcomes && <div className="al-panel"><h4>Order outcomes ({v.outcomes.column.replaceAll("_", " ")})</h4>
      <div className="al-outcomes">{v.outcomes.rows.map((r) => <div key={r.value}><strong>{percent(r.share, 1)}</strong><span>{r.value}</span><small>{r.count.toLocaleString()} rows</small></div>)}</div></div>}
    {[...v.notes, ...v.warnings].length > 0 && <div className="al-panel al-caveat"><h4>How this file was read</h4>
      <ul className="al-plain">{v.warnings.map((w, i) => <li key={`w${i}`}><strong>Note:</strong> {w}</li>)}{v.notes.map((n, i) => <li key={`n${i}`}>{n}</li>)}</ul></div>}
  </section>;
}

export default function YourDataTab({ report }) {
  if (!report.your_data.length) return <div className="al-panel">None of the files had enough dates to show a business overview over time. See the Insights tab for what stood out in the other files.</div>;
  return <div className="al-stack">{report.your_data.map((v) => <View key={v.view} v={v}/>)}</div>;
}
