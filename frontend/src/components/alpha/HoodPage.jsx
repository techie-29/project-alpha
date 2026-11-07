import { useState } from "react";
import { Link } from "react-router-dom";
import { fmtValue } from "../../utils/alphaFormat";
import { ROLE_TEXT } from "../../utils/alphaFormat";

const PURPOSE = { column_review: "Checked unsure column meanings", ask: "Answered a question", investigate: "Wrote the summary", phrase: "Wrote the findings in plain words" };
const money = (v) => (v < 0.01 && v > 0 ? "under $0.01" : `$${(v || 0).toFixed(2)}`);

function Step({ n, title, sub, children, open }) {
  return <details className="hd-step" open={open}><summary><i>{n}</i><span><strong>{title}</strong>{sub && <small>{sub}</small>}</span></summary><div className="hd-body">{children}</div></details>;
}

/** Everything Alpha did with the files, in the order it did it, so the owner can see and trust the work. */
export default function HoodPage({ id, report }) {
  const [allCols, setAllCols] = useState(false);
  const files = report.files || [];
  const links = (report.reading?.links || []).filter((l) => l.use);
  const dc = report.data_check || {};
  const rows = dc.rows || {};
  const timing = Object.entries(report.insights?.checked?.timing || {}).filter(([, s]) => s !== undefined);
  const cover = report.coverage || [];
  const used = cover.filter((c) => /^Used/.test(c.status)).length;
  const ai = report.ai || {}, u = ai.usage || {};
  const aiOn = ai.provider && ai.provider !== "none";
  const shown = allCols ? cover : cover.slice(0, 12);
  const when = report.generated_at ? new Date(report.generated_at).toLocaleString() : "";
  const items = (report.insights?.items || []).length;

  return <div className="hd">
    <div className="al-panel hd-sum">
      <div><b>{files.length}</b><span>file{files.length === 1 ? "" : "s"}</span></div>
      <div><b>{(dc.rows_in || files.reduce((n, f) => n + (f.rows || 0), 0)).toLocaleString()}</b><span>rows read</span></div>
      <div><b>{cover.length}</b><span>columns understood</span></div>
      <div><b>{items}</b><span>findings made</span></div>
      <div><b>{report.seconds != null ? `${report.seconds}s` : "—"}</b><span>to analyse</span></div>
    </div>
    <p className="al-muted">Nothing here is hidden. Every step is listed in order. {when && <>This analysis ran on {when}.</>}</p>

    <Step n="1" title="Read your files" sub={files.map((f) => f.name).join(", ")} open>
      <ul className="hd-list">{files.map((f) => <li key={f.name}><strong>{f.name}</strong><span>{ROLE_TEXT[f.role] || f.role} · {(f.rows || 0).toLocaleString()} rows</span></li>)}</ul>
    </Step>

    <Step n="2" title="Worked out what each column means" sub={`${used} of ${cover.length} columns were used in the analysis`}>
      <p className="al-muted">Alpha looked at the header and the values together. You can change any reading on <Link to={`/analysis/${id}/mapping`}>Header Mapping</Link>.</p>
      <div className="al-table-wrap"><table className="al-table al-compact"><thead><tr><th>File</th><th>Column</th><th>Means</th><th>Sure</th><th>Used for</th></tr></thead>
        <tbody>{shown.map((c, i) => <tr key={i}><td>{c.file}</td><td><code>{c.column}</code></td><td>{c.label}</td><td>{c.confidence != null ? `${Math.round(c.confidence * 100)}%` : "—"}</td><td>{c.status}</td></tr>)}</tbody></table></div>
      {cover.length > 12 && <button type="button" className="al-link-button" onClick={() => setAllCols(!allCols)}>{allCols ? "Show fewer" : `Show all ${cover.length} columns`}</button>}
    </Step>

    <Step n="3" title="Connected the files" sub={links.length ? `${links.length} link${links.length === 1 ? "" : "s"} used` : "No links between files"}>
      {links.length > 0 && <ul className="hd-list">{links.map((l) => <li key={l.key}><strong>{l.child}</strong> · {l.child_col} → <strong>{l.parent}</strong> · {l.parent_col}<span>{Math.round(l.coverage * 100)}% of keys match</span></li>)}</ul>}
      {(report.link_notes || []).map((n, i) => <p key={i} className="al-muted">{n}</p>)}
      {(report.link_warnings || []).map((n, i) => <p key={i} className="al-note-warn">{n}</p>)}
      {!links.length && !(report.link_notes || []).length && <p className="al-muted">Each file was analysed on its own.</p>}
    </Step>

    <Step n="4" title="Checked and cleaned the data" sub={dc.headline}>
      <div className="hd-chips"><span className="al-chip">{(rows.ok || 0).toLocaleString()} fine</span><span className="al-chip">{(rows.fixed || 0).toLocaleString()} cleaned</span><span className="al-chip al-chip-warn">{(rows.flagged || 0).toLocaleString()} flagged</span><span className="al-chip">{(rows.left_out || 0).toLocaleString()} left out</span></div>
      <p className="al-muted">{dc.checks_total || 0} checks ran across: {(dc.groups || []).join(", ")}. Rows that are flagged are kept but marked; rows left out would have made the totals wrong. <Link to={`/analysis/${id}/quality`}>See every check</Link>.</p>
    </Step>

    <Step n="5" title="Looked for patterns" sub={`${items} findings from ${timing.length} kinds of analysis`}>
      <ul className="hd-list">{timing.map(([k, s]) => <li key={k}><strong>{k[0].toUpperCase() + k.slice(1)}</strong><span>{s < 0.05 ? "instant" : `${s}s`}</span></li>)}</ul>
      <p className="al-muted">Findings are ranked by the money involved and how strong the evidence is. Each one is labelled: calculated, supported by evidence, or an early sign.</p>
    </Step>

    <Step n="6" title="AI helper" sub={aiOn ? `${u.calls || 0} call${u.calls === 1 ? "" : "s"} · ${money(u.cost_usd)}` : "Not used"}>
      {aiOn ? <>
        <p className="al-muted">The AI never sees your rows. It only gets summaries of the columns and the findings, and every answer is checked against your data before it is used.</p>
        <div className="hd-chips"><span className="al-chip">{u.calls || 0} of {u.limits?.calls ?? "—"} calls</span><span className="al-chip">{money(u.cost_usd)} of {money(u.limits?.cost_usd)}</span><span className="al-chip">{((u.tokens_in || 0) + (u.tokens_out || 0)).toLocaleString()} tokens</span>{u.failed ? <span className="al-chip al-chip-warn">{u.failed} failed</span> : null}</div>
        {(u.log || []).length > 0 && <ul className="hd-list">{u.log.map((l, i) => <li key={i}><strong>{PURPOSE[l.purpose] || l.purpose}</strong><span>{l.error ? "failed" : `${l.seconds}s · ${money(l.cost)}`}</span></li>)}</ul>}
      </> : <p className="al-muted">No AI key is set, so everything above was done by Alpha's own checks. Add a key to get plain-language summaries and Ask Your Data.</p>}
    </Step>

    <Step n="7" title="What Alpha cannot tell you">
      <ul className="al-plain">{(report.limits || []).map((l, i) => <li key={i}>{l}</li>)}</ul>
    </Step>
  </div>;
}
