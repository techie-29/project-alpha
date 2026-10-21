import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AskTab, BriefingTab, CoverageTab, InsightsTab, OverviewTab, ReadingTab, SuggestionsTab } from "../components/alpha/Tabs";
import { downloadExport, getAnalysis, getReport, sendAnswer, sendFeedback } from "../services/alphaApi";

const TABS = [["briefing", "Briefing"], ["overview", "Overview"], ["insights", "Insights"], ["suggestions", "Suggestions"], ["ask", "Ask Alpha"], ["coverage", "Coverage"], ["reading", "How I read your files"]];

export default function AnalysisPage({ token }) {
  const { id } = useParams();
  const [status, setStatus] = useState(null);
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [tab, setTab] = useState("briefing");
  const [focusId, setFocusId] = useState(null);
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

  const open = useCallback((insightId) => { setFocusId(insightId); setTab("insights"); }, []);
  async function onFeedback(findingId, verdict) {
    setReport((r) => ({ ...r, owner: { ...r.owner, feedback: [...r.owner.feedback.filter((x) => x.findingId !== findingId), { findingId, verdict }] } }));
    try { await sendFeedback(id, findingId, verdict, token); } catch (e) { setError(e.message); }
  }
  async function onAnswer(questionId, answer) {
    setReport((r) => ({ ...r, owner: { ...r.owner, answers: [...r.owner.answers.filter((x) => x.questionId !== questionId), { questionId, answer }] } }));
    try { await sendAnswer(id, questionId, answer, token); } catch (e) { setError(e.message); }
  }
  async function onExport(format) {
    setExporting(format); setError("");
    try { await downloadExport(id, format, token); } catch (e) { setError(e.message); } finally { setExporting(""); }
  }

  if (error && !status) return <div className="page-content"><div className="error-banner" role="alert"><span>!</span><div><strong>Could not load this analysis</strong><p>{error}</p></div></div><Link to="/analyses">Back to analyses</Link></div>;
  if (!status) return <div className="page-content"><div className="analytics-loading"><span className="spinner"/>Loading…</div></div>;
  if (status.status === "failed") return <div className="page-content"><div className="error-banner" role="alert"><span>!</span><div><strong>The analysis stopped</strong><p>{status.error || "Something went wrong."}</p></div></div><Link className="secondary-button" to="/upload">Try again</Link></div>;
  if (!report) return <div className="page-content">
    <section className="page-header"><span className="eyebrow">Working on it</span><h1>{status.stage || "Starting"}…</h1><p>Alpha is reading every file, building the overview and running each analysis. Large files take a few minutes; you can leave this page.</p></section>
    <div className="al-progress" role="progressbar" aria-valuenow={status.progress}><i style={{ width: `${status.progress}%` }}/><span>{status.progress}%</span></div>
    {status.engineMessage && <p className="al-note-warn">{status.engineMessage}</p>}
  </div>;
  if (report.version !== 2) return <div className="page-content"><div className="al-panel">This analysis was made by an older version of Alpha. Please run it again to see the new report.</div><Link className="secondary-button" to="/upload">Run again</Link></div>;

  const aiOn = report.ai?.provider && report.ai.provider !== "none";
  return <div className="page-content al-report">
    <section className="page-header al-report-head">
      <div><span className="eyebrow">Analysis · {new Date(report.generated_at).toLocaleString()}</span>
        <h1>{report.files.length} file{report.files.length === 1 ? "" : "s"}: {report.files.map((f) => f.name).join(", ")}</h1>
        <p className="al-muted">Took {Math.round(report.seconds)}s · AI helper {aiOn ? `on (${report.ai.provider})` : "off"}{report.ai?.investigation?.questions ? ` · asked ${report.ai.investigation.questions} questions of its own` : ""}</p></div>
      <div className="al-actions"><button type="button" className="secondary-button" disabled={!!exporting} onClick={() => onExport("pdf")}>{exporting === "pdf" ? "Preparing…" : "Download PDF"}</button>
        <button type="button" className="secondary-button" disabled={!!exporting} onClick={() => onExport("xlsx")}>{exporting === "xlsx" ? "Preparing…" : "Download Excel"}</button></div>
    </section>
    {error && <div className="error-banner" role="alert"><span>!</span><div><p>{error}</p></div></div>}
    <div className="al-tabs" role="tablist">{TABS.map(([k, t]) => <button key={k} type="button" role="tab" aria-selected={tab === k} className={tab === k ? "is-on" : ""} onClick={() => setTab(k)}>{t}</button>)}</div>
    {tab === "briefing" && <BriefingTab report={report} open={open} answers={report.owner.answers} onAnswer={onAnswer}/>}
    {tab === "overview" && <OverviewTab report={report}/>}
    {tab === "insights" && <InsightsTab report={report} focusId={focusId} feedback={report.owner.feedback} onFeedback={onFeedback}/>}
    {tab === "suggestions" && <SuggestionsTab report={report} open={open}/>}
    {tab === "ask" && <AskTab analysisId={id} token={token} aiOn={aiOn}/>}
    {tab === "coverage" && <CoverageTab report={report} open={open}/>}
    {tab === "reading" && <ReadingTab report={report}/>}
  </div>;
}
