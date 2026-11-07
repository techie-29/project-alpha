import { useState } from "react";

const MARK = { issue: "al-dq-issue", fixed: "al-dq-fixed" };

function Health({ value, issues, total }) {
  const tone = value >= 90 ? "good" : value >= 70 ? "ok" : "bad";
  return <div className={`al-dq-health al-dq-${tone}`} role="img" aria-label={`Data health ${value} out of 100`}>
    <b>{value}</b><span>/ 100<small>data health</small></span>
    <p>{issues === 0 ? "No problems found in " + total.toLocaleString() + " cells." : `${issues.toLocaleString()} of ${total.toLocaleString()} cells need attention.`}</p>
  </div>;
}

function Group({ g, onChoose, busy }) {
  const [open, setOpen] = useState(false);
  return <div className="al-panel al-dq-group">
    <div className="al-panel-head"><h4>{g.title}</h4><span className="al-chip al-chip-warn">{g.count.toLocaleString()} {g.count === 1 ? "cell" : "cells"}</span></div>
    <p className="al-muted">{g.why}</p>
    <div className="al-dq-choices" role="radiogroup" aria-label={g.title}>
      {g.choices.map((c) => <button key={c.id} type="button" role="radio" aria-checked={g.choice === c.id} disabled={busy}
        className={`al-dq-choice ${g.choice === c.id ? "on" : ""}`} onClick={() => onChoose(g.type, c.id)}>{c.label}{g.default === c.id ? " (suggested)" : ""}</button>)}
    </div>
    {g.cells.length > 0 && <button type="button" className="al-link-button" onClick={() => setOpen(!open)}>{open ? "Hide" : "Show"} the {Math.min(g.cells.length, g.count)} affected {g.cells.length === 1 ? "cell" : "cells"}</button>}
    {open && <div className="al-table-wrap"><table className="al-table al-compact"><thead><tr><th>Row</th><th>Column</th><th>Value</th>{g.cells.some((c) => c.suggest != null) && <th>Suggested</th>}</tr></thead>
      <tbody>{g.cells.slice(0, 30).map((c, i) => <tr key={i}><td>{c.row}</td><td>{c.column || "all columns"}</td><td><code>{c.value == null || c.value === "" ? "(empty)" : String(c.value)}</code></td>{g.cells.some((x) => x.suggest != null) && <td>{c.suggest ?? ""}</td>}</tr>)}</tbody></table></div>}
  </div>;
}

function FileReport({ rep, onChoose, busy }) {
  const [all, setAll] = useState(false);
  if (rep.error) return <div className="al-panel"><h4>{rep.file}</h4><p className="al-note-warn">{rep.error}</p></div>;
  const s = rep.summary, pv = rep.preview;
  const rows = all ? pv.rows : pv.rows.slice(0, 12);
  return <section className="al-stack">
    <div className="al-panel">
      <div className="al-panel-head"><h3 className="al-h3">{rep.file}</h3>
        <span className="al-chip">{s.rows_before.toLocaleString()} rows{s.removed ? ` → ${s.rows_after.toLocaleString()} after removing ${s.removed}` : ""}</span></div>
      <Health value={s.health} issues={s.issues} total={rep.cells}/>
      {rep.auto.length > 0 && <div className="al-dq-auto"><h4>Fixed automatically ({rep.auto.length})</h4>
        <ul>{rep.auto.map((a) => <li key={a.id}><strong>{a.what}</strong>{a.examples?.length > 0 && <small>{a.examples.slice(0, 2).map((e) => e.to == null ? `row ${e.row}` : `row ${e.row}: ${e.from ?? ""} → ${e.to}`).join(" · ")}</small>}</li>)}</ul></div>}
      {rep.groups.length === 0 && rep.auto.length === 0 && <p>This table is clean. Nothing to decide.</p>}
    </div>
    {rep.groups.map((g) => <Group key={g.type} g={g} busy={busy} onChoose={(t, c) => onChoose(rep.file, t, c)}/>)}
    {pv.rows.length > 0 && <div className="al-panel"><h4>Your data, problems highlighted</h4>
      <p className="al-muted">Showing {rows.length} of {pv.total.toLocaleString()} rows{pv.total > pv.shown ? " (rows with problems first)" : ""}. <span className="al-dq-issue">Red</span> needs a decision, <span className="al-dq-fixed">green</span> was fixed for you.</p>
      <div className="al-table-wrap"><table className="al-table al-compact"><thead><tr><th>Row</th>{pv.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead>
        <tbody>{rows.map((r) => <tr key={r.row} className={r.removed || r.repeat ? "al-dq-gone" : ""}><td>{r.row}</td>
          {r.cells.map((c, i) => <td key={i} className={MARK[c.s] || ""} title={c.s === "fixed" ? `Fixed to ${c.to}` : c.s === "issue" ? "Needs a decision" : undefined}>{c.v == null ? <em>empty</em> : c.v}{c.s === "fixed" && <small> → {c.to}</small>}</td>)}</tr>)}</tbody></table></div>
      {pv.rows.length > 12 && <button type="button" className="al-link-button" onClick={() => setAll(!all)}>{all ? "Show fewer rows" : `Show all ${pv.rows.length} rows`}</button>}
    </div>}
  </section>;
}

/** The data-quality step: health, what was fixed for the owner, and one decision per kind of problem. */
export default function DataQuality({ quality, onChoose, busy }) {
  const t = quality.totals;
  return <div className="al-stack">
    <div className={`al-panel ${t.decisions ? "al-caveat" : ""}`}>
      <h3 className="al-h3">Checking your data</h3>
      <p>{t.decisions ? `${t.auto} problem${t.auto === 1 ? " was" : "s were"} fixed for you and ${t.decisions} cell${t.decisions === 1 ? " needs" : "s need"} your decision. Pick what to do with each kind of problem. The health score updates as you choose.` : t.auto ? `${t.auto} small problem${t.auto === 1 ? " was" : "s were"} fixed for you. Nothing needs your decision.` : "No problems found."}</p>
      {quality.files.length > 1 && <p className="al-muted">Overall health: <strong>{t.health}/100</strong> across {quality.files.length} tables.</p>}
    </div>
    {quality.files.map((r) => <FileReport key={r.file} rep={r} onChoose={onChoose} busy={busy}/>)}
  </div>;
}
