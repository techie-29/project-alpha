import { Fragment, useMemo, useState } from "react";
import { Link } from "react-router-dom";

const TYPE = { measure: "Number", category: "Category", time: "Date", key: "ID", id: "ID", text: "Text", flag: "Yes / no", constant: "Same in every row", empty: "Empty", group: "Category" };
const num = (v) => (Math.abs(v) >= 1000 ? Math.round(v).toLocaleString() : Number(v.toFixed(2)).toLocaleString());
const pct = (v) => `${Math.round(v * 1000) / 10}%`;

function rowsOf(reading) {
  const out = [];
  for (const f of reading?.files || []) for (const c of f.columns || []) {
    out.push({ file: f.name, rows: f.rows, column: c.original || c.name, means: c.label || "Not read", type: TYPE[c.type] || c.type, confidence: c.confidence,
      reasons: c.reasons || [], profile: c.profile, issues: c.issues || [], source: c.source });
  }
  return out;
}

function csvOf(rows) {
  const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const head = ["File", "Column", "Means", "Type", "Filled", "Blank", "Different values", "Examples", "Min", "Max", "Average", "Issues"];
  const body = rows.map((r) => { const p = r.profile || {}; const s = p.stats || {};
    return [r.file, r.column, r.means, r.type, p.filled != null ? pct(p.filled) : "", p.blank ?? "", p.unique ?? "", p.hidden ? "(hidden: personal)" : (p.examples || []).join(" | "),
      s.min ?? "", s.max ?? "", s.mean != null ? Number(s.mean.toFixed(2)) : "", r.issues.join("; ")].map(esc).join(","); });
  return [head.map(esc).join(","), ...body].join("\r\n");
}

function Detail({ r, id }) {
  const p = r.profile || {};
  const s = p.stats, top = p.top || [];
  const max = top.length ? top[0].count : 1;
  return <div className="dd-detail">
    <div>
      <h4>How Alpha read it</h4>
      <p>{r.means}{r.confidence != null ? `, ${Math.round(r.confidence * 100)}% sure` : ""}{r.source === "memory" ? " (your earlier choice)" : ""}.</p>
      {r.reasons.length > 0 && <ul className="al-plain">{r.reasons.map((x, i) => <li key={i}>{x}</li>)}</ul>}
      <Link to={`/analysis/${id}/mapping`}>Change what this column means</Link>
    </div>
    <div>
      <h4>{s ? "Spread" : top.length ? "Most common values" : p.first ? "Date range" : "Values"}</h4>
      {p.hidden && <p className="al-muted">Personal details are not shown here.</p>}
      {s && <><dl className="dd-stats"><div><dt>Lowest</dt><dd>{num(s.min)}</dd></div><div><dt>Average</dt><dd>{num(s.mean)}</dd></div><div><dt>Middle</dt><dd>{num(s.median)}</dd></div><div><dt>Highest</dt><dd>{num(s.max)}</dd></div></dl>
        <div className="dd-range" aria-hidden="true"><i style={{ left: `${s.max > s.min ? ((s.median - s.min) / (s.max - s.min)) * 100 : 50}%` }}/></div></>}
      {!s && top.length > 0 && <ul className="dd-top">{top.map((t) => <li key={t.value}><span>{t.value}</span><b>{t.count.toLocaleString()}</b><i style={{ width: `${(t.count / max) * 100}%` }}/></li>)}</ul>}
      {p.first && <p>{p.first} to {p.last}</p>}
      {!s && !top.length && !p.first && !p.hidden && <p className="al-muted">Every value is different (like an ID). Examples: {(p.examples || []).join(", ") || "none"}.</p>}
    </div>
    <div>
      <h4>Quality</h4>
      {r.issues.length ? <ul className="al-plain">{r.issues.map((x, i) => <li key={i}>{x}</li>)}</ul> : <p>No problems found by the checks.</p>}
      {p.blank > 0 && <p className="al-muted">{p.blank.toLocaleString()} blank cell{p.blank === 1 ? "" : "s"}.</p>}
      <Link to={`/analysis/${id}/quality`}>Open Data Quality</Link>
    </div>
  </div>;
}

/** Every column in every file: what it means, what is in it, and how clean it is. */
export default function DictionaryPage({ id, report }) {
  const all = useMemo(() => rowsOf(report.reading), [report]);
  const files = useMemo(() => [...new Set(all.map((r) => r.file))], [all]);
  const [q, setQ] = useState("");
  const [file, setFile] = useState("all");
  const [open, setOpen] = useState(null);
  const words = q.trim().toLowerCase().split(/\s+/).filter(Boolean);
  const list = all.filter((r) => (file === "all" || r.file === file) && words.every((w) => `${r.column} ${r.means} ${r.type} ${r.file}`.toLowerCase().includes(w)));
  const profiled = all.some((r) => r.profile);
  const download = () => {
    const url = URL.createObjectURL(new Blob(["﻿" + csvOf(list)], { type: "text/csv;charset=utf-8" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "data-dictionary.csv" });
    document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  if (!all.length) return <div className="al-panel"><p>This analysis has no column details.</p></div>;
  return <div className="al-stack">
    {!profiled && <p className="al-note-warn">This analysis was made before column profiles existed. Run it again to see fill rates, examples and spreads.</p>}
    <div className="ex-bar">
      <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search columns (e.g. price, date, city)" aria-label="Search columns"/>
      {files.length > 1 && <select value={file} onChange={(e) => setFile(e.target.value)} aria-label="File"><option value="all">All {files.length} files</option>{files.map((f) => <option key={f} value={f}>{f}</option>)}</select>}
      <button type="button" className="secondary-button" onClick={download}>Download CSV</button>
    </div>
    <p className="al-muted">{list.length} of {all.length} columns. Click a row for details.</p>
    <div className="al-table-wrap"><table className="al-table dd">
      <thead><tr><th>Column</th>{files.length > 1 && <th>File</th>}<th>Means</th><th>Type</th><th>Filled</th><th>Different values</th><th>Examples</th><th aria-label="Quality"/></tr></thead>
      <tbody>{list.map((r) => { const k = `${r.file}::${r.column}`; const p = r.profile || {}; const on = open === k;
        return <Fragment key={k}>
          <tr className={`dd-row${on ? " on" : ""}`} onClick={() => setOpen(on ? null : k)} tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setOpen(on ? null : k); } }} aria-expanded={on}>
            <td><code>{r.column}</code></td>
            {files.length > 1 && <td className="dd-file" title={r.file}>{r.file.replace(/\.(csv|xlsx?|xls)$/i, "")}</td>}
            <td>{r.means}</td><td>{r.type}</td>
            <td>{p.filled != null ? <span className="dd-fill"><i style={{ width: `${p.filled * 100}%` }} className={p.filled < 0.9 ? "low" : ""}/><b>{pct(p.filled)}</b></span> : "—"}</td>
            <td>{p.unique != null ? p.unique.toLocaleString() : "—"}</td>
            <td className="dd-ex">{p.hidden ? <span className="al-muted">hidden</span> : (p.examples || []).join(", ")}</td>
            <td>{r.issues.length ? <span className="al-chip al-chip-warn">{r.issues.length} issue{r.issues.length === 1 ? "" : "s"}</span> : null}</td>
          </tr>
          {on && <tr className="dd-open"><td colSpan={files.length > 1 ? 8 : 7}><Detail r={r} id={id}/></td></tr>}
        </Fragment>; })}</tbody>
    </table></div>
  </div>;
}
