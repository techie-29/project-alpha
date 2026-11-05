import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AskTab, DataTab, ExploreTab, FindingsTab, ReadTab, SummaryTab, viewOf } from "../components/alpha/report/Report";
import { downloadExport, getAnalysis, getReport } from "../services/alphaApi";

const TABS = [["summary", "Summary"], ["findings", "Findings"], ["explore", "Explore"], ["data", "Data check"], ["ask", "Ask Alpha"], ["reading", "How we read your files"]];

export default function AnalysisPage({ token }) {
  const { id } = useParams();
  const [status, setStatus] = useState(null);
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("summary");
  const [exporting, setExporting] = useState("");

  useEffect(() => {
    let active = true, timer;
    async function poll() {
      try {
        const s = await getAnalysis(id, token);
        if (!active) return;
        setStatus(s);
        if (s.status === "done") { setReport(await getReport(id, token)); return; }
        if (s.status === "failed") return;
        timer = setTimeout(poll, 3000);
      } catch (e) { if (active) setError(e.message); }
    }
    poll();
    return () => { active = false; clearTimeout(timer); };
  }, [id, token]);

  const view = useMemo(() => (report ? viewOf(report) : null), [report]);
  const go = useCallback((t) => { setTab(t); window.scrollTo({ top: 0, behavior: "smooth" }); }, []);
  async function onExport(format) {
    setExporting(format); setError("");
    try { await downloadExport(id, format, token); } catch (e) { setError(e.message); } finally { setExporting(""); }
  }

  if (error && !status) return <div className="page-content"><div className="error-banner" role="alert"><span>!</span><div><strong>Could not load this analysis</strong><p>{error}</p></div></div><Link to="/analyses">Back to analyses</Link></div>;
  if (!status) return <div className="page-content"><div className="analytics-loading"><span className="spinner"/>Loading…</div></div>;
  if (status.status === "failed") return <div className="page-content"><div className="error-banner" role="alert"><span>!</span><div><strong>The analysis stopped</strong><p>{status.error || "Something went wrong."}</p></div></div><Link className="secondary-button" to="/upload">Try again</Link></div>;
  if (!report) return <div className="page-content">
    <section className="page-header"><span className="eyebrow">Working on it</span><h1>{status.stage || "Starting"}…</h1><p>Alpha is reading every file, checking the data and working out what matters. Large files take a few minutes; you can leave this page.</p></section>
    <div className="al-progress" role="progressbar" aria-valuenow={status.progress}><i style={{ width: `${status.progress}%` }}/><span>{status.progress}%</span></div>
    {status.engineMessage && <p className="al-note-warn">{status.engineMessage}</p>}
  </div>;
  if ((report.version !== 2 || !report.data_check) && report.brain !== "full AI") return <div className="page-content"><div className="al-panel">This analysis was made by an older version of Alpha. Please run it again to see the new report.</div><Link className="secondary-button" to="/upload">Run again</Link></div>;

  const usage = report.ai?.usage;
  const aiOn = report.ai?.provider && report.ai.provider !== "none";
  const exportable = !view.full;
  return <div className="page-content al-report">
    <section className="page-header al-report-head">
      <div><span className="eyebrow">Analysis · {new Date(report.generated_at).toLocaleString()} · {view.brain}</span>
        <h1>{report.files.length} file{report.files.length === 1 ? "" : "s"}: {report.files.map((f) => f.name).join(", ")}</h1>
        <p className="al-muted">Took {Math.round(report.seconds)}s · AI {aiOn ? `on${report.ai.model ? ` (${report.ai.model})` : ""}` : "off"}
          {usage?.calls ? ` · ${usage.calls} AI call${usage.calls === 1 ? "" : "s"}${usage.cost_usd ? `, $${usage.cost_usd.toFixed(3)}` : ""}` : ""}{view.f.replayed ? " · replayed from the saved run (no AI cost)" : ""}
          {report.ai?.stopped ? <span className="al-note-warn"> · {report.ai.stopped}</span> : null}</p></div>
      {exportable && <div className="al-actions"><button type="button" className="secondary-button" disabled={!!exporting} onClick={() => onExport("pdf")}>{exporting === "pdf" ? "Preparing…" : "Download PDF"}</button>
        <button type="button" className="secondary-button" disabled={!!exporting} onClick={() => onExport("xlsx")}>{exporting === "xlsx" ? "Preparing…" : "Download Excel"}</button></div>}
    </section>
    {error && <div className="error-banner" role="alert"><span>!</span><div><p>{error}</p></div></div>}
    <div className="al-tabs" role="tablist">{TABS.map(([k, t]) => <button key={k} type="button" role="tab" aria-selected={tab === k} className={tab === k ? "is-on" : ""} onClick={() => setTab(k)}>{t}{k === "findings" && view.cards.length ? <span className="ar-count">{view.cards.length}</span> : null}</button>)}</div>
    {tab === "summary" && <SummaryTab report={report} view={view} go={go}/>}
    {tab === "findings" && <FindingsTab view={view}/>}
    {tab === "explore" && <ExploreTab report={report} view={view}/>}
    {tab === "data" && <DataTab report={report} view={view}/>}
    {tab === "ask" && <AskTab analysisId={id} token={token} aiOn={aiOn}/>}
    {tab === "reading" && <ReadTab report={report} view={view} open={() => go("findings")}/>}
  </div>;
}
