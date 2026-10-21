import { useEffect, useMemo, useRef, useState } from "react";
import Tile from "./viz/Tile";
import Chart from "./viz/Chart";
import InsightCard, { Claim } from "./InsightCard";
import { askAlpha, listQuestions } from "../../services/alphaApi";
import { fmtValue, ROLE_TEXT } from "../../utils/alphaFormat";

const AREA = { sales: "Sales", products: "Products", customers: "Customers", operations: "Operations", service: "Service", stock: "Stock", costs: "Costs", data: "Data checks", other: "Other", general: "General", people: "People" };

/* ------------------------------ Briefing ------------------------------ */
export function BriefingTab({ report, open, answers, onAnswer }) {
  const b = report.briefing;
  return <div className="al-stack">
    <section className="al-hero">
      <span className="eyebrow">Briefing</span>
      <h2>{b.headline}</h2>
      {b.ai_summary && <p className="al-lead">{b.ai_summary}</p>}
      <ul className="al-keynums">{b.key_numbers.map((k) => <li key={k}>{k}</li>)}</ul>
      <p className="al-muted">{b.coverage}</p>
    </section>
    {b.top.length > 0 && <section><h3 className="al-h3">What matters most</h3>
      <div className="al-cards">{b.top.map((t) => <button type="button" key={t.insight_id} className={`al-story pol-${t.polarity}`} onClick={() => open(t.insight_id)}>
        <Claim claim={t.claim}/><strong>{t.title}</strong><span>{t.detail}</span>{t.suggestion && <em>{t.suggestion}</em>}</button>)}</div></section>}
    {b.first_actions?.length > 0 && <section className="al-panel"><h3 className="al-h3">Do these first</h3>
      <ol className="al-plain">{b.first_actions.map((a) => <li key={a.insight_id}><button type="button" className="al-link-button al-plainlink" onClick={() => open(a.insight_id)}>{a.action}</button> <span className="al-muted">({a.title})</span></li>)}</ol></section>}
    {report.questions?.length > 0 && <QuestionsBox report={report} answers={answers} onAnswer={onAnswer}/>}
    {b.caveats.length > 0 && <section className="al-panel al-caveat"><h3 className="al-h3">Keep in mind</h3><ul className="al-plain">{b.caveats.map((c) => <li key={c}>{c}</li>)}</ul></section>}
    <section className="al-panel"><h3 className="al-h3">How to read this</h3><p className="al-muted">{b.how_to_read}</p><ul className="al-plain al-muted">{report.limits.map((l) => <li key={l}>{l}</li>)}</ul></section>
  </div>;
}

function QuestionsBox({ report, answers, onAnswer }) {
  const saved = new Map((answers || []).map((a) => [a.questionId, a.answer]));
  return <section className="al-panel"><h3 className="al-h3">Questions only you can answer</h3>
    <p className="al-muted">The files show what changed, not always why. Your answers are saved with this analysis.</p>
    {report.questions.map((q) => <QuestionRow key={q.id} q={q} saved={saved.get(q.id)} onAnswer={onAnswer}/>)}</section>;
}

function QuestionRow({ q, saved, onAnswer }) {
  const [v, setV] = useState(saved || "");
  return <form className="al-question" onSubmit={(e) => { e.preventDefault(); if (v.trim()) onAnswer(q.id, v.trim()); }}>
    <label>{q.text}<textarea rows={2} value={v} maxLength={1000} onChange={(e) => setV(e.target.value)} placeholder="Type what you know"/></label>
    <button type="submit" className="secondary-button" disabled={!v.trim() || v.trim() === saved}>{saved && v.trim() === saved ? "Saved" : "Save answer"}</button>
  </form>;
}

/* ------------------------------ Overview ------------------------------ */
export function OverviewTab({ report }) {
  const ov = report.overview;
  const [area, setArea] = useState(ov.sections[0]?.area);
  const sec = ov.sections.find((s) => s.area === area);
  return <div className="al-stack">
    <section><h3 className="al-h3">What your files contain</h3>
      <div className="al-files-grid">{ov.files.map((f) => <div key={f.name} className="al-filecard">
        <span className="al-chip">{f.role_text}{f.entity ? ` · ${f.entity}` : ""}</span><strong>{f.name}</strong><span>{f.what}</span>
        {f.from && <small className="al-muted">{f.from} to {f.to}</small>}{f.currencies?.length > 1 && <small className="al-muted">Currencies: {f.currencies.join(", ")}</small>}</div>)}</div>
      {ov.currencies?.length > 1 && <p className="al-note-warn">Money is shown in {ov.currency}, the largest currency. Other currencies are never added in; their totals are listed under Sales.</p>}
    </section>
    <section><h3 className="al-h3">Key numbers</h3><div className="al-tiles">{ov.tiles.map((t) => <Tile key={t.metric} t={t}/>)}</div></section>
    {ov.sections.length > 0 && <section>
      <div className="al-sectabs" role="tablist" aria-label="Business areas">{ov.sections.map((s) => <button key={s.area} type="button" role="tab" aria-selected={s.area === area} className={s.area === area ? "is-on" : ""} onClick={() => setArea(s.area)}>{s.title} <span className="al-muted">{s.charts.length}</span></button>)}</div>
      {sec && <div className="al-chartgrid">{sec.charts.map((c) => <div key={c.id} className={c.type === "line" || c.type === "stacked" || c.type === "stacked_count" || c.type === "table" ? "al-wide" : ""}><Chart spec={c}/></div>)}</div>}
    </section>}
  </div>;
}

/* ------------------------------ Insights ------------------------------ */
export function InsightsTab({ report, focusId, feedback, onFeedback }) {
  const items = report.insights.items.filter((i) => !i.muted);
  const muted = report.insights.items.filter((i) => i.muted);
  const [area, setArea] = useState("all");
  const [strength, setStrength] = useState("all");
  const areas = [...new Set(items.map((i) => i.area))];
  const shown = items.filter((i) => (area === "all" || i.area === area) && (strength === "all" || i.claim === strength));
  const fb = new Map((feedback || []).map((x) => [x.findingId, x.verdict]));
  useEffect(() => { if (focusId) setTimeout(() => document.getElementById(`ins-${focusId}`)?.scrollIntoView({ behavior: "smooth", block: "start" }), 60); }, [focusId]);
  const stories = new Map(report.insights.stories.map((s) => [s.id, s]));
  return <div className="al-stack">
    <div className="al-filters">
      <label>Area <select value={area} onChange={(e) => setArea(e.target.value)}><option value="all">All ({items.length})</option>{areas.map((a) => <option key={a} value={a}>{AREA[a] || a} ({items.filter((i) => i.area === a).length})</option>)}</select></label>
      <label>Strength <select value={strength} onChange={(e) => setStrength(e.target.value)}><option value="all">All</option><option>Supported by evidence</option><option>Calculated</option><option>Possible (early sign)</option></select></label>
      <span className="al-muted">Checked: {Object.entries(report.insights.checked?.timing || {}).length} kinds of analysis across every column that could be used. See Coverage for the full list.</span>
    </div>
    {report.insights.quiet && <div className="al-panel"><h3 className="al-h3">Nothing unusual changed</h3><p>Everything Alpha tested stayed within its normal range once chance was allowed for. The calculated facts below still describe your business.</p></div>}
    {shown.map((i) => <div key={i.id}>
      <InsightCard item={i} feedback={fb.get(i.id)} onFeedback={onFeedback} open={i.id === focusId}/>
      {stories.get(i.id)?.size > 1 && <p className="al-muted al-related">Related: {stories.get(i.id).members.filter((m) => m !== i.id).map((m) => items.find((x) => x.id === m)?.title).filter(Boolean).join(" · ")}</p>}
    </div>)}
    {muted.length > 0 && <details className="al-panel"><summary>{muted.length} hidden because you marked similar findings "not useful"</summary>
      <div className="al-stack">{muted.map((i) => <InsightCard key={i.id} item={i} feedback={fb.get(i.id)} onFeedback={onFeedback}/>)}</div></details>}
  </div>;
}

/* ------------------------------ Suggestions ------------------------------ */
const BUCKETS = [["fix", "Fix", "Problems worth solving, biggest first."], ["keep", "Keep", "Things going well; protect them."], ["plan", "Plan", "Patterns to plan around."], ["watch", "Watch", "Early signs; check again next time."]];
export function SuggestionsTab({ report, open }) {
  return <div className="al-columns">{BUCKETS.map(([k, t, sub]) => <section key={k} className={`al-bucket al-${k}`}>
    <header><h3>{t}</h3><span>{report.suggestions[k].length}</span></header><p className="al-muted">{sub}</p>
    {report.suggestions[k].length === 0 && <p className="al-empty">Nothing here.</p>}
    {report.suggestions[k].map((s) => <button type="button" key={s.insight_id} className="al-intel" onClick={() => open(s.insight_id)}>
      <em>{s.action}</em><span>{s.title}</span>{s.impact ? <small>{fmtValue(Math.abs(s.impact), "money", s.impact_unit)} involved · {s.claim}</small> : <small>{s.claim}</small>}</button>)}
  </section>)}</div>;
}

/* ------------------------------ Ask Alpha ------------------------------ */
function show(r) {
  if (r === null || r === undefined) return "";
  if (typeof r !== "object") return String(r);
  if (r.columns) return [r.columns.join(" | "), ...r.rows.map((x) => x.join(" | "))].join("\n");
  return Object.entries(r).slice(0, 40).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`).join("\n");
}

export function AskTab({ analysisId, token, aiOn }) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [items, setItems] = useState([]);
  const [err, setErr] = useState("");
  const end = useRef(null);
  useEffect(() => { listQuestions(analysisId, token).then(setItems).catch(() => {}); }, [analysisId, token]);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [items.length, busy]);
  async function submit(e, text) {
    e?.preventDefault();
    const question = (text ?? q).trim();
    if (question.length < 3) return;
    setBusy(true); setErr("");
    try { const result = await askAlpha(analysisId, question, token); setItems((x) => [...x, { question, result }]); setQ(""); }
    catch (x) { setErr(x.message); } finally { setBusy(false); }
  }
  const examples = ["Why did sales drop in the last month?", "Which products make the least profit?", "Which region has the most returns, and why might that be?", "Who are my best customers and what do they buy?"];
  return <div className="al-stack al-ask-page">
    {!aiOn && <div className="al-panel al-caveat">The AI helper is off (no Gemini key set in engine/.env), so Ask Alpha cannot answer yet. Everything else in the report works without it.</div>}
    <div className="al-chat">
      {items.length === 0 && <div className="al-panel"><h3 className="al-h3">Ask anything about your business</h3><p className="al-muted">Alpha answers by running calculations on all your files, shows its working, and says what the data cannot tell.</p>
        <div className="al-examples">{examples.map((x) => <button key={x} type="button" className="al-mini" onClick={() => submit(null, x)}>{x}</button>)}</div></div>}
      {items.map((it, i) => <div key={i} className="al-qa">
        <p className="al-q">{it.question}</p>
        <div className="al-a">
          {it.result.answer ? <p><strong>{it.result.answer}</strong></p> : <p className="al-muted">{it.result.note}</p>}
          {it.result.reasoning && <p className="al-muted"><b>Why:</b> {it.result.reasoning}</p>}
          {it.result.cannot_tell && <p className="al-muted"><b>What the data cannot show:</b> {it.result.cannot_tell}</p>}
          {it.result.calculations?.length > 0 && <details><summary>How Alpha worked this out ({it.result.calculations.length} calculation{it.result.calculations.length === 1 ? "" : "s"})</summary>
            {it.result.calculations.map((c, j) => <div key={j}><p className="al-muted">{c.why} <span>({c.table})</span>{c.ok ? "" : ` — ${c.error}`}</p>{c.ok && <pre className="al-pre">{show(c.result)}</pre>}</div>)}</details>}
        </div>
      </div>)}
      {busy && <p className="al-muted">Alpha is working on it… (this can take up to a minute)</p>}
      <div ref={end}/>
    </div>
    {err && <p className="al-note-warn">{err}</p>}
    <form className="al-ask" onSubmit={submit}><input value={q} maxLength={500} onChange={(e) => setQ(e.target.value)} placeholder="Ask about your business…" aria-label="Your question"/>
      <button className="primary-button" type="submit" disabled={busy || q.trim().length < 3}>{busy ? "Working…" : "Ask"}</button></form>
  </div>;
}

/* ------------------------------ Coverage ------------------------------ */
export function CoverageTab({ report, open }) {
  const [file, setFile] = useState("all");
  const files = [...new Set(report.coverage.map((c) => c.file))];
  const rows = report.coverage.filter((c) => file === "all" || c.file === file);
  const counts = useMemo(() => { const m = {}; for (const c of report.coverage) { const k = c.status.split(":")[0].replace(/ \d+ finding.*/, " findings"); m[k] = (m[k] || 0) + 1; } return m; }, [report.coverage]);
  return <div className="al-stack">
    <p className="al-muted">Every column Alpha read, what it understood it to mean, and what it did with it. Nothing is silently skipped.</p>
    <div className="al-filters"><label>File <select value={file} onChange={(e) => setFile(e.target.value)}><option value="all">All files</option>{files.map((f) => <option key={f}>{f}</option>)}</select></label>
      <span className="al-muted">{Object.entries(counts).map(([k, v]) => `${v} ${k.toLowerCase()}`).join(" · ")}</span></div>
    <div className="al-table-wrap al-tall"><table className="al-table al-compact"><thead><tr><th>File</th><th>Column</th><th>Read as</th><th>Confidence</th><th>What Alpha did</th></tr></thead>
      <tbody>{rows.map((c) => <tr key={c.file + c.column}><td>{c.file}</td><td><code>{c.column}</code></td><td>{c.label}</td><td>{Math.round(c.confidence * 100)}%</td>
        <td>{c.status}{c.findings?.length > 0 && <> · <button type="button" className="al-link-button al-plainlink" onClick={() => open(c.findings[0])}>open</button></>}</td></tr>)}</tbody></table></div>
  </div>;
}

/* ------------------------------ Reading (report copy) ------------------------------ */
export function ReadingTab({ report }) {
  return <div className="al-stack">{report.reading.files.map((f) => <section key={f.name} className="al-panel">
    <div className="al-panel-head"><h4>{f.name}</h4><span className="al-chip">{ROLE_TEXT[f.role] || f.role}{f.entity ? ` · ${f.entity}` : ""}</span></div>
    <p className="al-muted">{f.role_reason}</p>
    {f.identities?.length > 0 && <p className="al-muted">Columns that add up exactly: {f.identities.join("; ")}</p>}
    <div className="al-table-wrap"><table className="al-table al-compact"><thead><tr><th>Column</th><th>Means</th><th>Confidence</th><th>Why</th></tr></thead>
      <tbody>{f.columns.filter((c) => c.concept).map((c) => <tr key={c.name}><td><code>{c.name}</code></td><td>{c.label}</td><td>{Math.round((c.confidence || 0) * 100)}%</td><td className="al-why">{(c.reasons || []).join("; ")}</td></tr>)}</tbody></table></div>
  </section>)}</div>;
}
