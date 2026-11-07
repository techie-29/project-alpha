import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { alertsOf } from "../../context/AnalysisContext";

const LEVEL = { fail: ["Fix first", "al-lv-high"], warn: ["Look at", "al-lv-mid"] };
const FILTERS = [["all", "All"], ["finding", "Business risks"], ["data", "Data problems"]];

/** Everything that needs the owner's attention, most serious first: data checks that failed or warned, and findings that are risks. */
export default function AlertsPage({ id, report, view }) {
  const [filter, setFilter] = useState("all");
  const all = useMemo(() => alertsOf(report, view), [report, view]);
  const actions = useMemo(() => {
    const m = {};
    for (const list of Object.values(report.suggestions || {})) for (const s of list || []) m[s.insight_id] = s.action;
    return m;
  }, [report]);
  const items = all
    .map((a, n) => ({ ...a, n, rank: a.level === "fail" ? 0 : a.kind === "finding" ? 1 : 2 }))
    .filter((a) => filter === "all" || a.kind === filter)
    .sort((a, b) => a.rank - b.rank || a.n - b.n);
  const count = (k) => all.filter((a) => k === "all" || a.kind === k).length;

  if (!all.length) return <div className="al-panel al-allclear"><h3 className="al-h3">All clear</h3><p>No data problems and no business risks were found in this analysis. Run a new one when you have fresh data.</p></div>;
  return <div className="al-stack">
    <div className="al-filters" role="tablist" aria-label="Filter alerts">
      {FILTERS.map(([k, t]) => <button key={k} type="button" role="tab" aria-selected={filter === k} className={filter === k ? "on" : ""} onClick={() => setFilter(k)}>{t} <b>{count(k)}</b></button>)}
    </div>
    {items.length === 0 && <p className="al-muted">Nothing in this group.</p>}
    <ul className="al-alerts">{items.map((a) => {
      const [label, cls] = a.kind === "finding" ? ["Risk", "al-lv-risk"] : LEVEL[a.level];
      const action = a.kind === "finding" ? actions[a.insight] || a.fix : null;
      return <li key={`${a.kind}-${a.n}`} className={cls}>
        <span className="al-lv">{label}</span>
        <div>
          <strong>{a.title}</strong>
          {a.detail && <p>{a.detail}</p>}
          {action && <p className="al-do"><b>What to do:</b> {action}</p>}
          <small>{a.kind === "data" ? <>In <code>{a.file}</code> · <Link to={`/analysis/${id}/quality`}>See the data checks</Link></> : <><Link to={`/analysis/${id}/suggestions#${a.id}`}>Open the finding</Link>{a.area ? ` · ${a.area}` : ""}</>}</small>
        </div>
      </li>;
    })}</ul>
  </div>;
}
