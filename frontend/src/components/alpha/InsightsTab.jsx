import { useEffect, useMemo, useRef, useState } from "react";
import FindingCard from "./FindingCard";

export default function InsightsTab({ report, feedback, onFeedback, focusId }) {
  const [filter, setFilter] = useState("all");
  const refs = useRef({});
  const all = report.insights.findings.filter((f) => !f.muted);
  const muted = report.insights.findings.filter((f) => f.muted);
  const shown = useMemo(() => all.filter((f) => filter === "all" || (filter === "confirmed" ? f.level === "confirmed" : f.level !== "confirmed")), [all, filter]);
  useEffect(() => { if (focusId && refs.current[focusId]) refs.current[focusId].scrollIntoView({ behavior: "smooth", block: "center" }); }, [focusId]);
  const fb = new Map((feedback || []).map((x) => [x.findingId, x.verdict]));
  const ins = report.insights;
  return <div className="al-stack">
    <div className="al-filter" role="group" aria-label="Filter findings">
      {[["all", `All (${all.length})`], ["confirmed", `Supported by evidence (${all.filter((f) => f.level === "confirmed").length})`], ["early", `Early signs (${all.filter((f) => f.level !== "confirmed").length})`]].map(([k, t]) =>
        <button key={k} type="button" className={filter === k ? "is-on" : ""} onClick={() => setFilter(k)}>{t}</button>)}
    </div>
    {ins.quiet && <div className="al-panel"><h3 className="al-h3">Nothing unusual changed</h3>
      <p>Alpha checked {ins.checked.series.toLocaleString()} combinations of measures, groups and time windows. Everything stayed within its own normal range once chance was allowed for. A quiet result is a real result: it means the business was steady, not that nothing was looked at.</p></div>}
    {shown.map((f) => <div key={f.id} ref={(el) => { refs.current[f.id] = el; }}><FindingCard finding={f} feedback={fb.get(f.id)} onFeedback={onFeedback} defaultOpen={f.id === focusId}/></div>)}
    {muted.length > 0 && <details className="al-panel"><summary>{muted.length} hidden because you marked similar findings "not useful"</summary>
      <div className="al-stack">{muted.map((f) => <FindingCard key={f.id} finding={f} feedback={fb.get(f.id)} onFeedback={onFeedback}/>)}</div></details>}
    {ins.seasonal.length > 0 && <section className="al-panel"><h3 className="al-h3">Repeats every year</h3>
      <p className="al-muted">These happen at the same time each year, so they are patterns, not surprises.</p>
      <ul className="al-plain">{ins.seasonal.map((s, i) => <li key={i}>{s.measure}{s.scope ? ` for ${s.scope}` : ""} around {s.when}. {s.note}</li>)}</ul></section>}
    {ins.snapshots.some((s) => s.findings?.length) && <section className="al-panel"><h3 className="al-h3">Snapshot (not a trend)</h3>
      {ins.snapshots.filter((s) => s.findings?.length).map((s) => <div key={s.view}><h4>{s.view}</h4><p className="al-muted">{s.note}</p>
        <ul className="al-plain">{s.findings.map((f, i) => <li key={i}>{f.title}{f.detail ? ` — ${f.detail}` : ""}</li>)}</ul></div>)}
    </section>}
  </div>;
}
