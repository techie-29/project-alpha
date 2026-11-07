import { useEffect, useMemo, useRef, useState } from "react";
import Chart, { RowsTable } from "../viz/Chart";
import Tile from "../viz/Tile";
import { OverviewTab, ReadingTab, CoverageTab } from "../Tabs";
import { askAlpha, listQuestions } from "../../../services/alphaApi";
import { cellText, fmtValue } from "../../../utils/alphaFormat";

/* One report view for both versions of Alpha. The metric + AI version and the full-AI version write the same finding
   cards; only the parts around them (dashboard tiles, data checks, column reading) come from different places. */

export function viewOf(report) {
  const f = report.findings || {};
  const full = report.brain === "full AI" || f.brain === "full AI";
  const ov = report.overview || {};
  const currency = ov.currency || "";
  const figures = full
    ? (f.key_figures || []).map((k, i) => ({ metric: `k${i}`, label: k.label, value: k.value, fmt: k.format === "money" ? "money" : k.format, unit: k.format === "money" ? currency : "", note: k.note }))
    : (ov.tiles || []).slice(0, 8);
  const dc = report.data_check;
  const health = full
    ? { text: `${(f.data_quality || []).length} data-quality note${(f.data_quality || []).length === 1 ? "" : "s"} from the AI's own checks`, rows: null }
    : dc ? { text: dc.headline, rows: dc.rows, total: dc.rows_in } : null;
  return { full, f, currency, figures, health, cards: f.cards || [], headline: f.headline || report.briefing?.headline, brain: full ? "full AI" : (f.brain || "older engine") };
}

const TONE = { risk: ["Risk", "ar-risk"], strength: ["Strength", "ar-strength"], data: ["Data issue", "ar-data"], neutral: ["Worth knowing", "ar-neutral"] };
const STRENGTH = { Calculated: "Calculated", "Supported by evidence": "Supported by evidence", Possible: "Possible (early sign)" };

function chartSpec(c) {
  const d = c.chart_data;
  if (!d || !d.rows?.length) return null;
  if (d.type === "line") return { type: "line", title: d.title || "", x: d.rows.map((r) => String(r.group)), values: d.rows.map((r) => r.value), fmt: d.fmt };
  if (d.type === "table") return { type: "table", title: d.title || "", columns: ["Value"], fmts: { Value: d.fmt }, rows: d.rows.map((r) => ({ key: String(r.group), Value: r.value })) };
  return { type: "bar", title: d.title || "", rows: d.rows.map((r) => ({ group: String(r.group), value: r.value, rows: r.rows })), fmt: d.fmt };
}

function Money({ m, currency }) {
  if (!m || m.amount === null || m.amount === undefined) return null;
  return <span className="ar-money"><b>{fmtValue(Math.abs(m.amount), "money", currency)}</b>{m.what ? ` ${m.what}` : ""}</span>;
}

function How({ card }) {
  const how = card.how || [];
  if (!how.length && !card.rows_sample) return null;
  return <details className="ar-how"><summary>How it was worked out</summary>
    {how.map((h, i) => <div key={i} className="ar-how-item">
      {h.question && <p className="ar-how-q">{h.question}</p>}
      {h.formula && <p className="al-muted">Formula: {h.formula}{h.rows_used != null ? ` · ${h.rows_used.toLocaleString()} rows used` : ""}{h.file ? ` · ${h.file}` : ""}</p>}
      {h.code && <pre className="al-pre">{h.code}</pre>}
      {h.result !== undefined && h.code && <pre className="al-pre ar-result">{JSON.stringify(h.result, null, 1).slice(0, 1500)}</pre>}
      {h.evidence?.rows?.length > 0 && <RowsTable evidence={{ ...h.evidence, file: h.file || "your file" }}/>}
    </div>)}
    {card.rows_sample && <RowsTable evidence={card.rows_sample}/>}
  </details>;
}

export function FindingCard({ card, currency, big }) {
  const [label, cls] = TONE[card.tone] || TONE.neutral;
  const spec = chartSpec(card);
  return <article className={`ar-card ${cls} ${big ? "ar-card-big" : ""}`}>
    <header className="ar-card-head">
      <div className="ar-chips"><span className={`ar-tone ${cls}`}>{label}</span><span className="ar-sure">{STRENGTH[card.strength] || card.strength}</span>
        {card.area && card.area !== "general" && <span className="ar-area">{card.area}</span>}{card.source === "engine" && <span className="ar-area" title="Found by the engine's own scan, checked the same way">engine</span>}</div>
      <Money m={card.money} currency={currency}/>
    </header>
    <h3>{card.headline}</h3>
    {card.points?.length > 0 && <ul className="ar-points">{card.points.map((p, i) => <li key={i}>{p}</li>)}</ul>}
    {card.why_it_matters && <p className="ar-why">{card.why_it_matters}</p>}
    {spec && <div className="ar-chart"><Chart spec={spec} compactView/></div>}
    {card.look_into && <div className="ar-look"><strong>Worth looking into</strong><span>{card.look_into}</span></div>}
    <How card={card}/>
  </article>;
}

function Dropped({ list }) {
  if (!list?.length) return null;
  return <details className="al-panel ar-dropped"><summary>{list.length} possible finding{list.length === 1 ? " was" : "s were"} held back because their numbers did not match the calculations, or they said nothing specific</summary>
    <ul className="al-plain">{list.slice(0, 40).map((d, i) => <li key={i}><strong>{d.headline || "(no headline)"}</strong> <span className="al-muted">{(d.why || []).join("; ")}</span></li>)}</ul></details>;
}

function HealthBar({ h, onOpen }) {
  if (!h) return null;
  if (!h.rows) return <button type="button" className="ar-health" onClick={onOpen}><span>{h.text}</span><em>Open data check →</em></button>;
  const tot = Math.max(1, (h.rows.ok || 0) + (h.rows.fixed || 0) + (h.rows.flagged || 0) + (h.rows.left_out || 0));
  const seg = [["ok", "Fine", "ar-ok"], ["fixed", "Cleaned", "ar-fixed"], ["flagged", "Flagged", "ar-flag"], ["left_out", "Left out", "ar-out"]];
  return <button type="button" className="ar-health" onClick={onOpen} aria-label={h.text}>
    <span className="ar-health-bar">{seg.map(([k, , c]) => h.rows[k] ? <i key={k} className={c} style={{ width: `${(100 * h.rows[k]) / tot}%` }}/> : null)}</span>
    <span className="ar-health-legend">{seg.map(([k, t, c]) => <span key={k}><i className={c}/>{t} {(h.rows[k] || 0).toLocaleString()}</span>)}</span>
    <em>Open data check →</em>
  </button>;
}

export function SummaryTab({ report, view, go }) {
  const { figures, cards, headline, health, currency } = view;
  return <div className="al-stack">
    <section className="ar-hero">
      <span className="eyebrow">Summary</span>
      <h2>{headline || "Here is what your files show."}</h2>
      {view.f.business && <p className="al-lead">{view.f.business}</p>}
      {view.f.understanding && <p className="al-lead">{view.f.understanding}</p>}
      {view.f.error && <p className="al-note-warn">{view.f.error}</p>}
    </section>
    {figures.length > 0 && <section><h3 className="al-h3">Key figures</h3>{(() => { const notes = [...new Set(figures.map((t) => t.note).filter(Boolean))]; return notes.length > 0 && <p className="al-muted">{notes.join(" ")}</p>; })()}<div className="al-tiles">{figures.map((t) => <div key={t.metric}><Tile t={t}/></div>)}</div></section>}
    <HealthBar h={health} onOpen={() => go("data")}/>
    {cards.length > 0 && <section><div className="ar-sec-head"><h3 className="al-h3">What matters most</h3><button type="button" className="al-mini" onClick={() => go("findings")}>All {cards.length} findings →</button></div>
      <div className="ar-top">{cards.slice(0, 3).map((c) => <FindingCard key={c.id} card={c} currency={currency} big/>)}</div></section>}
    {cards.length === 0 && !view.f.error && <div className="al-panel">No finding passed the checks for this upload. The key figures and the data check still describe your business.</div>}
    {(view.f.cannot_tell || []).length > 0 && <section className="al-panel al-caveat"><h3 className="al-h3">What the data cannot tell you</h3><ul className="al-plain">{view.f.cannot_tell.map((c, i) => <li key={i}>{c}</li>)}</ul></section>}
    {report.limits && <section className="al-panel"><h3 className="al-h3">How to read this</h3><ul className="al-plain al-muted">{report.limits.map((l) => <li key={l}>{l}</li>)}
      <li>Each finding says how sure it is: Calculated (plain arithmetic on your rows), Supported by evidence (holds up against chance), or Possible (an early sign). None claims a cause.</li></ul></section>}
  </div>;
}

export function FindingsTab({ view }) {
  const [area, setArea] = useState("all");
  const [tone, setTone] = useState("all");
  const areas = [...new Set(view.cards.map((c) => c.area).filter(Boolean))];
  const shown = view.cards.filter((c) => (area === "all" || c.area === area) && (tone === "all" || c.tone === tone));
  return <div className="al-stack">
    <div className="al-filters">
      <label>Area <select value={area} onChange={(e) => setArea(e.target.value)}><option value="all">All ({view.cards.length})</option>{areas.map((a) => <option key={a} value={a}>{a}</option>)}</select></label>
      <label>Kind <select value={tone} onChange={(e) => setTone(e.target.value)}><option value="all">All</option><option value="risk">Risks</option><option value="strength">Strengths</option><option value="data">Data issues</option><option value="neutral">Worth knowing</option></select></label>
      <span className="al-muted">Ranked by importance and money involved. Every number was checked against the calculation behind it.</span>
    </div>
    <div className="ar-list">{shown.map((c) => <FindingCard key={c.id} card={c} currency={view.currency}/>)}</div>
    {shown.length === 0 && <p className="al-muted">Nothing here.</p>}
    <Dropped list={view.f.dropped}/>
  </div>;
}

export function ExploreTab({ report, view }) {
  const byArea = useMemo(() => {
    const m = {};
    for (const c of view.cards) (m[c.area || "general"] ||= []).push(c);
    return m;
  }, [view.cards]);
  return <div className="al-stack">
    {!view.full && report.overview && <OverviewTab report={report}/>}
    {Object.keys(byArea).length > 0 && <section><h3 className="al-h3">Findings by area</h3>
      {Object.entries(byArea).map(([a, list]) => <details key={a} className="al-panel ar-area-block" open={view.full}><summary><strong className="ar-cap">{a}</strong> <span className="al-muted">{list.length} finding{list.length === 1 ? "" : "s"}</span></summary>
        <div className="ar-list">{list.map((c) => <FindingCard key={c.id} card={c} currency={view.currency}/>)}</div></details>)}</section>}
  </div>;
}

/* ------------------------------ Data check ------------------------------ */
const ST = { pass: ["✓", "Passed", "ar-st-pass"], fixed: ["✱", "Cleaned", "ar-st-fixed"], info: ["i", "Note", "ar-st-info"], warn: ["!", "Check", "ar-st-warn"], fail: ["✕", "Problem", "ar-st-fail"], "n/a": ["–", "Not applicable", "ar-st-na"] };

function downloadRows(file) {
  const lines = [["check", "status", "row_in_file"].join(",")];
  for (const c of file.checks) for (const r of c.examples?.all_rows || []) if (["warn", "fail", "fixed"].includes(c.status)) lines.push([`"${c.title}"`, c.status, r].join(","));
  const blob = new Blob([lines.join("\n")], { type: "text/csv" });
  const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `${file.file}-problem-rows.csv`; a.click(); URL.revokeObjectURL(a.href);
}

function Check({ c }) {
  const [icon, word, cls] = ST[c.status] || ST.info;
  return <details className={`ar-check ${cls}`} open={c.status === "fail"}>
    <summary><span className="ar-st-icon" aria-label={word}>{icon}</span><span className="ar-check-title">{c.title}</span>
      {c.rows ? <span className="ar-check-n">{c.rows.toLocaleString()} rows</span> : null}{c.money ? <span className="ar-check-n">{fmtValue(Math.abs(c.money), "money")} of sales</span> : null}</summary>
    <p>{c.detail}</p>
    {c.examples?.rows?.length > 0 && <div className="al-table-wrap"><table className="al-table al-compact"><thead><tr>{c.examples.columns.map((h) => <th key={h}>{h}</th>)}</tr></thead>
      <tbody>{c.examples.rows.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j}>{cellText(v)}</td>)}</tr>)}</tbody></table></div>}
    {(c.parts || []).length > 0 && <ul className="al-plain al-muted">{c.parts.map((p, i) => <li key={i}>{p.detail}</li>)}</ul>}
  </details>;
}

export function DataTab({ report, view }) {
  const [problemsOnly, setProblemsOnly] = useState(true);
  if (view.full) {
    const checks = (view.f.code || []).filter((x) => String(x.id).startsWith("c"));
    return <div className="al-stack">
      <p className="al-muted">In this version the AI decided which checks to run on your data, wrote them as code, and the engine ran them.</p>
      <div className="ar-list">{(view.f.data_quality || []).map((c) => <FindingCard key={c.id} card={c} currency={view.currency}/>)}</div>
      {!(view.f.data_quality || []).length && <div className="al-panel">The AI did not report any data-quality problem that its checks could back with numbers.</div>}
      {checks.length > 0 && <details className="al-panel"><summary>The {checks.length} checks the AI ran</summary>
        {checks.map((x) => <div key={x.id} className="ar-how-item"><p className="ar-how-q">{x.question} {x.ok ? "" : <span className="al-note-warn">({x.error})</span>}</p><pre className="al-pre">{x.code}</pre></div>)}</details>}
      {view.f.setup && <details className="al-panel"><summary>How the AI prepared your data</summary><pre className="al-pre">{view.f.setup}</pre></details>}
    </div>;
  }
  const dc = report.data_check;
  if (!dc || !dc.files?.length) return <div className="al-panel">No data check for this analysis. Run it again to see one.</div>;
  return <div className="al-stack">
    <section className="ar-hero"><span className="eyebrow">Data check</span><h2>{dc.headline}</h2>
      <p className="al-muted">{dc.checks_total} checks on every file. Nothing is deleted without being reported; flagged rows stay in the totals until you decide.</p></section>
    <HealthBar h={view.health}/>
    <label className="al-inline"><input type="checkbox" checked={problemsOnly} onChange={(e) => setProblemsOnly(e.target.checked)}/> Show only what needs a look</label>
    {dc.files.map((f) => {
      const groups = [...new Set(f.checks.map((c) => c.group))];
      return <section key={f.file} className="al-panel">
        <div className="al-panel-head"><h4>{f.file}</h4><span className="al-muted">{f.rows_in_file.toLocaleString()} rows in the file · {f.problems} to look at{f.serious ? ` · ${f.serious} serious` : ""}</span>
          <button type="button" className="al-mini" onClick={() => downloadRows(f)}>Download problem rows (CSV)</button></div>
        {f.reconciliation && <div className="al-numbers">
          <div><span>Sales in the file</span><strong>{fmtValue(f.reconciliation.sales_in_file, "money", view.currency)}</strong></div>
          <div><span>Sales counted</span><strong>{fmtValue(f.reconciliation.sales_counted, "money", view.currency)}</strong></div>
          <div><span>Left out</span><strong>{fmtValue(f.reconciliation.sales_left_out, "money", view.currency)}</strong></div>
          <div><span>On flagged rows</span><strong>{fmtValue(f.reconciliation.sales_on_flagged_rows, "money", view.currency)}</strong></div></div>}
        {f.left_out_because?.length > 0 && <p className="al-muted">Left out: {f.left_out_because.join("; ")}.</p>}
        {groups.map((g) => {
          const list = f.checks.filter((c) => c.group === g && (!problemsOnly || ["warn", "fail", "fixed"].includes(c.status)));
          if (!list.length) return null;
          return <div key={g} className="ar-group"><h5>{g}</h5>{list.map((c) => <Check key={c.id} c={c}/>)}</div>;
        })}
      </section>;
    })}
  </div>;
}

/* ------------------------------ Ask Alpha ------------------------------ */
function Answer({ r }) {
  return <div className="al-a ar-answer">
    {r.short_answer ? <p className="ar-short"><strong>{r.short_answer}</strong></p> : <p className="al-muted">{r.note || r.answer}</p>}
    {r.key_points?.length > 0 && <ul className="ar-points">{r.key_points.map((p, i) => <li key={i}>{p}</li>)}</ul>}
    {r.what_it_means && <p><b>What it means:</b> {r.what_it_means}</p>}
    {r.cannot_tell && <p className="al-muted"><b>What the data cannot show:</b> {r.cannot_tell}</p>}
    {r.short_answer && r.note && <p className="al-note-warn">{r.note}</p>}
    {(r.how_worked_out?.length > 0 || r.calculations?.length > 0) && <details><summary>How Alpha worked this out ({(r.calculations || []).length} calculation{(r.calculations || []).length === 1 ? "" : "s"})</summary>
      {r.how_worked_out?.length > 0 && <ul className="al-plain">{r.how_worked_out.map((x, i) => <li key={i}>{x}</li>)}</ul>}
      {(r.calculations || []).map((c, i) => <div key={i} className="ar-how-item"><p className="ar-how-q">{c.question}{c.ok ? "" : <span className="al-note-warn"> — {c.error}</span>}</p>
        {c.formula && <p className="al-muted">Formula: {c.formula}{c.rows_used != null ? ` · ${c.rows_used.toLocaleString()} rows` : ""}</p>}
        {c.code && <pre className="al-pre">{c.code}</pre>}
        {c.ok && c.result && <pre className="al-pre ar-result">{JSON.stringify(c.result, null, 1).slice(0, 1200)}</pre>}
        {c.evidence?.rows?.length > 0 && <RowsTable evidence={{ ...c.evidence, file: "your file" }}/>}</div>)}
      {r.removed?.length > 0 && <p className="al-muted">Left out because the numbers did not check out: {r.removed.join("; ")}</p>}</details>}
  </div>;
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
  const examples = ["How is the business doing on profit?", "Which products or groups lose money?", "What changed most compared with last year?", "Where is money tied up or leaking?"];
  return <div className="al-stack al-ask-page">
    {!aiOn && <div className="al-panel al-caveat">The AI helper is off (no AI key in engine/.env), so Ask Alpha cannot answer yet.</div>}
    <div className="al-chat">
      {items.length === 0 && <div className="al-panel"><h3 className="al-h3">Ask anything about your business</h3><p className="al-muted">Alpha turns your question into calculations on all your rows, answers in short points, shows its working, and says what the data cannot tell.</p>
        <div className="al-examples">{examples.map((x) => <button key={x} type="button" className="al-mini" onClick={() => submit(null, x)}>{x}</button>)}</div></div>}
      {items.map((it, i) => <div key={i} className="al-qa"><p className="al-q">{it.question}</p><Answer r={it.result || {}}/></div>)}
      {busy && <p className="al-muted">Alpha is working on it… (this can take up to a minute)</p>}
      <div ref={end}/>
    </div>
    {err && <p className="al-note-warn">{err}</p>}
    <form className="al-ask" onSubmit={submit}><input value={q} maxLength={500} onChange={(e) => setQ(e.target.value)} placeholder="Ask about your business…" aria-label="Your question"/>
      <button className="primary-button" type="submit" disabled={busy || q.trim().length < 3}>{busy ? "Working…" : "Ask"}</button></form>
  </div>;
}

/* ------------------------------ How we read your files ------------------------------ */
export function ReadTab({ report, view, open }) {
  if (!view.full) return <div className="al-stack"><ReadingTab report={report}/><h3 className="al-h3">What Alpha did with each column</h3><CoverageTab report={report} open={open}/></div>;
  const cols = report.reading?.columns || [];
  return <div className="al-stack">
    {report.reading?.business && <p className="al-lead">{report.reading.business}</p>}
    {(report.files || []).map((f) => <section key={f.name} className="al-panel"><div className="al-panel-head"><h4>{f.name}</h4><span className="al-muted">{f.rows.toLocaleString()} rows · {f.columns} columns</span></div>
      {f.withheld_personal_columns?.length > 0 && <p className="al-muted">Kept private, never shown to the AI: {f.withheld_personal_columns.join(", ")}</p>}
      <div className="al-table-wrap"><table className="al-table al-compact"><thead><tr><th>Column</th><th>What the AI understood</th><th>How it is used</th></tr></thead>
        <tbody>{cols.filter((c) => !c.file || c.file === f.name).map((c, i) => <tr key={i}><td><code>{c.column}</code></td><td className="al-why">{c.meaning}</td><td className="al-why">{c.use}</td></tr>)}</tbody></table></div></section>)}
  </div>;
}
