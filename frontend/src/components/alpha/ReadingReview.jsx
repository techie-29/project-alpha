import { useMemo } from "react";
import { ROLE_TEXT, dateExample } from "../../utils/alphaFormat";

const KIND_FOR_TYPE = { measure: ["number"], category: ["group", "key", "text"], flag: ["group"], id: ["key", "text", "group"], time: ["date"], text: ["text", "key", "group"] };
const AREA_ORDER = ["sales", "costs", "products", "stock", "customers", "operations", "service", "people", "general"];

function ConceptSelect({ col, concepts, value, onChange }) {
  const kinds = KIND_FOR_TYPE[col.type] || ["number", "group", "key", "text", "date"];
  const opts = concepts.filter((c) => kinds.includes(c.kind)).sort((a, b) => AREA_ORDER.indexOf(a.area) - AREA_ORDER.indexOf(b.area) || a.label.localeCompare(b.label));
  const current = value || col.concept;
  return <select value={current || ""} onChange={(e) => onChange(e.target.value === col.concept ? null : e.target.value)} aria-label={`What ${col.name} means`}>
    {!current && <option value="">(not read)</option>}
    {opts.map((c) => <option key={c.id} value={c.id}>{c.label}</option>)}
  </select>;
}

function DateLine({ c, value, onChange }) {
  const d = c.date;
  const flippable = d.order === "day-first" || d.order === "month-first";
  return <span className="al-date">
    {d.example && <span>Read as: <code>{dateExample(d.order, d.example)}</code>{d.from && d.to ? ` · ${d.from} to ${d.to}` : ""}</span>}
    {flippable && <label className="al-inline">Day/month order
      <select value={value || d.order} onChange={(e) => onChange(e.target.value)} aria-label={`Day and month order in ${c.name}`}>
        <option value="day-first">Day first (31/12/2024)</option>
        <option value="month-first">Month first (12/31/2024)</option>
      </select>{!d.certain && !value && <span className="al-chip al-chip-warn">please check</span>}</label>}
  </span>;
}

export default function ReadingReview({ reading, choices, setChoices }) {
  const setConcept = (key, cid) => setChoices((c) => { const concepts = { ...c.concepts }; if (cid) concepts[key] = cid; else delete concepts[key]; return { ...c, concepts }; });
  const setLink = (key, use) => setChoices((c) => ({ ...c, links: { ...c.links, [key]: use } }));
  const setOrder = (name, on) => setChoices((c) => ({ ...c, rowOrder: { ...c.rowOrder, [name]: on } }));
  const setDateOrder = (file, col, order) => setChoices((c) => ({ ...c, dateOrder: { ...(c.dateOrder || {}), [file]: { ...((c.dateOrder || {})[file] || {}), [col]: order } } }));
  const setTimeCol = (file, col) => setChoices((c) => ({ ...c, timeCol: { ...(c.timeCol || {}), [file]: col } }));
  const unsure = useMemo(() => reading.files.reduce((n, f) => n + f.columns.filter((c) => c.needs_confirmation && !choices.concepts[`${f.name}::${c.name}`]).length, 0), [reading, choices]);
  const pending = reading.links.filter((l) => l.needs_confirmation && choices.links[l.key] === undefined);
  return <div className="al-stack">
    <div className={`al-panel ${unsure || pending.length ? "al-caveat" : ""}`}>
      <h3 className="al-h3">How I read your business</h3>
      <p>{unsure || pending.length ? `${unsure} column${unsure === 1 ? "" : "s"} and ${pending.length} link${pending.length === 1 ? "" : "s"} need a quick look (marked "please check"). You can run now, but findings that use them are less certain.` : "Everything was clear. Change anything that is wrong, then run the analysis. Alpha remembers your choices for next time."}</p>
      {reading.ai_review?.status === "ok" && <p className="al-muted">The AI helper reviewed {reading.ai_review.reviewed} unsure column(s); {reading.ai_review.accepted} suggestion(s) passed Alpha's value checks.</p>}
    </div>
    {reading.links.length > 0 && <div className="al-panel"><h4>How the files connect</h4>
      <p className="al-muted">A link lets Alpha treat the files as one business (for example, sales by customer segment, or stock against sales). Rows are never duplicated.</p>
      {reading.links.map((l) => { const on = choices.links[l.key] !== undefined ? choices.links[l.key] : l.use; return <label key={l.key} className="al-link">
        <input type="checkbox" checked={on} onChange={(e) => setLink(l.key, e.target.checked)}/>
        <span><strong>{l.child}</strong> · {l.child_col} → <strong>{l.parent}</strong> · {l.parent_col}<small>{Math.round(l.coverage * 100)}% of keys match.{l.needs_confirmation && choices.links[l.key] === undefined ? " Please confirm." : ""}</small></span></label>; })}
    </div>}
    {reading.files.map((f) => <div className="al-panel" key={f.name}>
      <div className="al-panel-head"><h4>{f.name}</h4><span className="al-chip">{ROLE_TEXT[f.role] || f.role}{f.entity ? ` · ${f.entity}` : ""} · {f.rows.toLocaleString()} rows</span></div>
      <p className="al-muted">{f.role_reason}</p>
      {f.identities?.length > 0 && <p className="al-muted">Found exact arithmetic between columns: {f.identities.slice(0, 4).join("; ")}.</p>}
      {f.warnings.map((w, i) => <p key={i} className="al-note-warn">{w}</p>)}
      {f.notes.slice(0, 3).map((n, i) => <p key={i} className="al-muted">{n}</p>)}
      {(f.date_columns || []).length > 1 && <label className="al-field al-inline">Timeline (when things happened)
        <select value={(choices.timeCol || {})[f.name] || f.time_col || ""} onChange={(e) => setTimeCol(f.name, e.target.value)}>
          {!f.time_col && <option value="">(none: these dates describe each row)</option>}
          {f.date_columns.map((d) => <option key={d} value={d}>{d}</option>)}
        </select></label>}
      {f.kind === "periodic" && !f.time_col && <label className="al-link"><input type="checkbox" checked={!!choices.rowOrder[f.name]} onChange={(e) => setOrder(f.name, e.target.checked)}/><span>No dates, but rows are in time order<small>Tick only if you are sure.</small></span></label>}
      {f.role !== "summary" && <div className="al-table-wrap"><table className="al-table al-compact"><thead><tr><th>Column</th><th>Means</th><th>Confidence</th><th>Why</th></tr></thead>
        <tbody>{f.columns.filter((c) => c.type !== "empty").map((c) => { const key = `${f.name}::${c.name}`; const mine = choices.concepts[key];
          return <tr key={c.name} className={c.needs_confirmation && !mine ? "al-unsure" : ""}>
            <td><code>{c.name}</code></td>
            <td><ConceptSelect col={c} concepts={reading.concepts} value={mine} onChange={(v) => setConcept(key, v)}/>{mine && <span className="al-chip al-chip-mine">your choice</span>}</td>
            <td>{c.confidence != null ? `${Math.round(c.confidence * 100)}%` : "—"}{c.needs_confirmation && !mine && <span className="al-chip al-chip-warn">please check</span>}</td>
            <td className="al-why">{c.source === "memory" ? "You chose this before. " : c.source === "ai" ? "AI helper. " : ""}{(c.reasons || []).slice(0, 2).join("; ")}
              {c.date && <DateLine f={f} c={c} value={((choices.dateOrder || {})[f.name] || {})[c.name]} onChange={(o) => setDateOrder(f.name, c.name, o)}/>}</td></tr>; })}</tbody></table></div>}
    </div>)}
  </div>;
}
