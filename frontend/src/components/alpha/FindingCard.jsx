import { useState } from "react";
import { TrendChart } from "./Charts";
import { amount, cellText, num, percent, signedPercent, LEVEL_TEXT, POLARITY_TEXT } from "../../utils/alphaFormat";

export function LevelBadge({ level, claim }) {
  return <span className={`al-badge al-badge-${level}`}>{claim || LEVEL_TEXT[level]}</span>;
}

function Drivers({ drivers }) {
  if (!drivers || !drivers.by_column?.length) return null;
  return <div className="al-block">
    <h4>What it lines up with</h4>
    {drivers.by_column.slice(0, 3).map((col) => <div key={col.col} className="al-driver">
      <span className="al-driver-col">{col.col.replaceAll("_", " ")}</span>
      <ul>{col.top.slice(0, 3).map((t) => <li key={t.value}>
        <strong>{t.value}</strong> accounts for {percent(t.share_of_change)} of the change
        {t.surprise && t.surprise >= 2 ? <em> (about {t.surprise.toFixed(1)}x its usual weight)</em> : null}
      </li>)}</ul>
    </div>)}
    {drivers.not_explained > 0.3 && <p className="al-muted">About {percent(drivers.not_explained)} of the change is not explained by the columns in your files.</p>}
  </div>;
}

function Rows({ rows }) {
  if (!rows || !rows.rows?.length) return null;
  return <div className="al-block">
    <h4>The rows behind this <span className="al-muted">({rows.total.toLocaleString()} in total, showing the {rows.rows.length} largest)</span></h4>
    <div className="al-table-wrap"><table className="al-table">
      <thead><tr>{rows.columns.map((c) => <th key={c}>{c.replaceAll("_", " ")}</th>)}</tr></thead>
      <tbody>{rows.rows.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j}>{cellText(v)}</td>)}</tr>)}</tbody>
    </table></div>
    <p className="al-muted">From {rows.file}. "Source row" is the row number in that file, so you can find it yourself.</p>
  </div>;
}

export default function FindingCard({ finding: f, feedback, onFeedback, defaultOpen = false }) {
  const [open, setOpen] = useState(defaultOpen);
  const n = f.numbers || {};
  return <article className={`al-finding al-pol-${f.polarity}`}>
    <button type="button" className="al-finding-head" aria-expanded={open} onClick={() => setOpen(!open)}>
      <div>
        <div className="al-finding-meta"><LevelBadge level={f.level} claim={f.claim}/><span className="al-chip">{POLARITY_TEXT[f.polarity]}</span>{f.view && <span className="al-chip">{f.view}</span>}</div>
        <h3>{f.title}</h3>
        <p>{f.detail}</p>
      </div>
      <span className="al-chevron" aria-hidden="true">{open ? "−" : "+"}</span>
    </button>
    {open && <div className="al-finding-body">
      {f.chart?.values?.length > 2 && <TrendChart labels={f.chart.labels} values={f.chart.values} focus={f.chart.focus} unit={n.unit}/>}
      <div className="al-numbers">
        <div><span>Before</span><strong>{amount(n.before, n.unit)}</strong></div>
        <div><span>During</span><strong>{amount(n.after, n.unit)}</strong></div>
        <div><span>Change</span><strong>{signedPercent(n.relative)}</strong></div>
        {n.impact !== null && n.impact !== undefined && <div><span>Amount involved</span><strong>{amount(n.impact, n.unit)}</strong></div>}
        {n.impact_share ? <div><span>Share of total</span><strong>{percent(n.impact_share, 1)}</strong></div> : null}
      </div>
      {f.investigation?.summary && <div className="al-block al-ai"><h4>What Alpha's AI helper checked</h4>
        <p>{f.investigation.summary}</p>
        {f.investigation.checks?.length > 0 && <ul className="al-plain">{f.investigation.checks.map((c, i) => <li key={i}>{typeof c === "string" ? c : c.why}</li>)}</ul>}
        <p className="al-muted">Every number in this note was produced by a calculation on your data, not by the AI. It describes what lines up, not a cause.</p></div>}
      <Drivers drivers={f.drivers}/>
      {f.folded?.length > 0 && <div className="al-block"><h4>Also part of this</h4><ul className="al-plain">{f.folded.slice(0, 6).map((x, i) => <li key={i}>{typeof x === "string" ? x : x.title}</li>)}</ul></div>}
      {f.caveats?.length > 0 && <div className="al-block al-caveat"><h4>Keep in mind</h4><ul className="al-plain">{f.caveats.map((c, i) => <li key={i}>{c}</li>)}</ul></div>}
      <Rows rows={f.rows}/>
      <p className="al-muted">How sure: {f.evidence_strength}. This shows what changed and what it lines up with. It does not prove a cause.</p>
      {onFeedback && <div className="al-feedback">
        <span>Was this useful?</span>
        <button type="button" className={feedback === "useful" ? "is-on" : ""} onClick={() => onFeedback(f.id, "useful")}>Useful</button>
        <button type="button" className={feedback === "not_useful" ? "is-on" : ""} onClick={() => onFeedback(f.id, "not_useful")}>Not useful</button>
      </div>}
    </div>}
  </article>;
}
