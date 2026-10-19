import { CHOOSABLE_ROLES, ROLE_LABELS } from "../../utils/alphaFormat";

function ColumnRow({ file, c, value, onChange }) {
  const current = value || c.role;
  const shown = CHOOSABLE_ROLES.includes(current) ? CHOOSABLE_ROLES : [current, ...CHOOSABLE_ROLES];
  return <tr className={c.needs_confirmation && !value ? "al-unsure" : ""}>
    <td><code>{c.name}</code></td>
    <td>
      <select value={current} onChange={(e) => onChange(`${file.name}::${c.name}`, e.target.value === c.role ? null : e.target.value)} aria-label={`How to read ${c.name}`}>
        {shown.map((r) => <option key={r} value={r}>{ROLE_LABELS[r] || r}</option>)}
      </select>
      {value && <span className="al-chip al-chip-mine">your choice</span>}
    </td>
    <td className="al-why">
      {c.reasons[0]}
      {c.ai && c.ai.accepted && <span className="al-chip">AI agrees: {c.ai.reason}</span>}
      {c.needs_confirmation && !value && <span className="al-chip al-chip-warn">please check</span>}
    </td>
  </tr>;
}

export default function ReadingReview({ reading, choices, setChoices }) {
  const setRole = (key, role) => setChoices((c) => { const roles = { ...c.roles }; if (role) roles[key] = role; else delete roles[key]; return { ...c, roles }; });
  const setLink = (key, use) => setChoices((c) => ({ ...c, links: { ...c.links, [key]: use } }));
  const setOrder = (name, on) => setChoices((c) => ({ ...c, rowOrder: { ...c.rowOrder, [name]: on } }));
  const unsure = reading.files.reduce((n, f) => n + f.columns.filter((c) => c.needs_confirmation && !choices.roles[`${f.name}::${c.name}`]).length, 0);
  const pending = reading.links.filter((l) => l.needs_confirmation && choices.links[l.key] === undefined);

  return <div className="al-stack">
    <div className={`al-panel ${unsure || pending.length ? "al-caveat" : ""}`}>
      <h3 className="al-h3">How I read your files</h3>
      <p>{unsure || pending.length ? `${unsure} column${unsure === 1 ? "" : "s"} and ${pending.length} link${pending.length === 1 ? "" : "s"} need a quick look. Everything else is clear. You can still run the analysis, but findings that rely on an unclear column are less certain.` : "Everything was clear. Check the table if you like, or run the analysis."}</p>
    </div>

    {reading.links.length > 0 && <div className="al-panel">
      <h4>Links between files</h4>
      <p className="al-muted">A link lets Alpha look at one file by the groups in another (for example, sales by customer region). Rows are never duplicated.</p>
      {reading.links.map((l) => {
        const on = choices.links[l.key] !== undefined ? choices.links[l.key] : l.use;
        return <label key={l.key} className="al-link">
          <input type="checkbox" checked={on} onChange={(e) => setLink(l.key, e.target.checked)}/>
          <span><strong>{l.child}</strong> · {l.child_col} → <strong>{l.parent}</strong> · {l.parent_col}
            <small>{Math.round(l.coverage * 100)}% of keys match. {l.reasons.slice(1, 3).join(". ")}{l.needs_confirmation && choices.links[l.key] === undefined ? " — please confirm." : ""}</small></span>
        </label>;
      })}
    </div>}

    {reading.files.map((f) => <div className="al-panel" key={f.name}>
      <div className="al-panel-head"><h4>{f.name}</h4><span className="al-chip">{f.rows.toLocaleString()} rows · {({ events: "one row per event", periodic: "one row per period", reference: "reference table", dimension: "lookup table", summary: "summary (skipped)", no_time: "no dates" })[f.kind] || f.kind}</span></div>
      {f.warnings.map((w, i) => <p key={i} className="al-note-warn">{w}</p>)}
      {f.notes.slice(0, 4).map((n, i) => <p key={i} className="al-muted">{n}</p>)}
      {f.ai && f.ai.status && <p className="al-muted">AI column review: {f.ai.status === "ok" ? "done" : f.ai.status === "skipped" ? "not needed" : "not available this time (rule-based reading used)"}.</p>}
      {f.kind === "periodic" && !f.time_col && <label className="al-link"><input type="checkbox" checked={!!choices.rowOrder[f.name]} onChange={(e) => setOrder(f.name, e.target.checked)}/><span>This file has no dates, but its rows are in time order<small>Tick only if you are sure; Alpha will treat row order as time.</small></span></label>}
      <div className="al-table-wrap"><table className="al-table al-compact"><thead><tr><th>Column</th><th>Read as</th><th>Why</th></tr></thead>
        <tbody>{f.columns.filter((c) => c.role !== "empty").map((c) => <ColumnRow key={c.name} file={f} c={c} value={choices.roles[`${f.name}::${c.name}`]} onChange={setRole}/>)}</tbody></table></div>
    </div>)}
  </div>;
}
