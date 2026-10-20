import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import BriefingTab from "../components/alpha/BriefingTab";
import YourDataTab from "../components/alpha/YourDataTab";
import InsightsTab from "../components/alpha/InsightsTab";
import IntelligenceTab from "../components/alpha/IntelligenceTab";
import { downloadExport, getAnalysis, getReport, sendAnswer, sendFeedback } from "../services/alphaApi";

const TABS = [["briefing", "Briefing"], ["data", "Your data"], ["insights", "Insights"], ["intelligence", "Intelligence"]];

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

  const openFinding = useCallback((findingId) => { setFocusId(findingId); setTab("insights"); }, []);

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
  if (status.status === "failed") return <div className="page-content"><div className="error-banner" role="alert"><span>!</span><div><strong>The analysis stopped</strong><p>{status.error || "Something went wrong."}</p></div></div><Link className="secondary-button" to="/upload">Try again with your files</Link></div>;
  if (!report) return <div className="page-content">
    <section className="page-header"><span className="eyebrow">Working on it</span><h1>{status.stage || "Starting"}…</h1><p>Large files can take a few minutes. You can leave this page; the result will be here when you come back.</p></section>
    <div className="al-progress" role="progressbar" aria-valuenow={status.progress}><i style={{ width: `${status.progress}%` }}/><span>{status.progress}%</span></div>
    {status.engineMessage && <p className="al-note-warn">{status.engineMessage}</p>}
  </div>;

  return <div className="page-content al-report">
    <section className="page-header">
      <span className="eyebrow">Analysis · {new Date(report.generated_at).toLocaleString()}</span>
      <h1>{report.files.map((f) => f.name).join(", ")}</h1>
      <div className="al-actions"><button type="button" className="secondary-button" disabled={!!exporting} onClick={() => onExport("pdf")}>{exporting === "pdf" ? "Preparing…" : "Download PDF"}</button><button type="button" className="secondary-button" disabled={!!exporting} onClick={() => onExport("xlsx")}>{exporting === "xlsx" ? "Preparing…" : "Download Excel"}</button></div>
      <p className="al-muted">Took {report.seconds}s. AI helper: {report.ai.provider === "none" ? "off (rule-based reading only)" : report.ai.provider}.</p>
    </section>
    {error && <div className="error-banner" role="alert"><span>!</span><div><p>{error}</p></div></div>}
    <div className="al-tabs" role="tablist">{TABS.map(([k, t]) => <button key={k} type="button" role="tab" aria-selected={tab === k} className={tab === k ? "is-on" : ""} onClick={() => setTab(k)}>{t}</button>)}</div>
    {tab === "briefing" && <BriefingTab report={report} onOpenFinding={openFinding} onAnswer={onAnswer} answers={report.owner.answers} analysisId={id} token={token}/>}
    {tab === "data" && <YourDataTab report={report}/>}
    {tab === "insights" && <InsightsTab report={report} feedback={report.owner.feedback} onFeedback={onFeedback} focusId={focusId}/>}
    {tab === "intelligence" && <IntelligenceTab report={report} onOpenFinding={openFinding}/>}
  </div>;
}
