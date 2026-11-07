import { useEffect } from "react";
import { Link, Navigate, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { AskTab, DataTab, ExploreTab, FindingsTab, ReadTab } from "../components/alpha/report/Report";
import { AREA_PAGES, AreaPage, Head, TrendsPage } from "../components/alpha/AreaPage";
import { useAnalysis } from "../context/AnalysisContext";
import RunProgress from "../components/alpha/RunProgress";
import OverviewPage from "../components/alpha/OverviewPage";

const SECTIONS = new Set(["overview", "mapping", "quality", "explorer", "sales", "customers", "products", "trends", "suggestions", "alerts", "whatif", "ask", "hood"]);
const OLD_TAB = { summary: "overview", findings: "suggestions", explore: "explorer", data: "quality", ask: "ask", reading: "mapping" };
const SOON = {
  alerts: ["Alerts", "Warnings that need your attention: sudden drops, rising refunds, data problems. Coming in this build."],
  whatif: ["What-If", "Move a slider (price, discount, costs) and see revenue and profit change. Coming in this build."],
  hood: ["Under the Hood", "Everything Alpha did with your files, step by step. Coming in this build."],
};

export default function AnalysisPage() {
  const { id, section = "overview" } = useParams();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const { hash } = useLocation();
  const { currentId, select, status, report, view, error, token } = useAnalysis();
  useEffect(() => { select(id); }, [id, select]);
  useEffect(() => {
    if (!hash) { window.scrollTo({ top: 0 }); return; }
    const t = setTimeout(() => { const el = document.getElementById(hash.slice(1)); if (el) { el.scrollIntoView({ behavior: "smooth", block: "center" }); el.classList.add("ar-flash"); setTimeout(() => el.classList.remove("ar-flash"), 2000); } }, 250);
    return () => clearTimeout(t);
  }, [section, hash, report]);
  if (!SECTIONS.has(section)) return <Navigate to={`/analysis/${id}/overview`} replace/>;
  const go = (t) => navigate(`/analysis/${id}/${OLD_TAB[t] || t}`);

  if (currentId !== id || (!status && !error)) return <div className="page-content"><div className="analytics-loading"><span className="spinner"/>Loading…</div></div>;
  if (error && !status) return <div className="page-content"><div className="error-banner" role="alert"><span>!</span><div><strong>Could not load this analysis</strong><p>{error}</p></div></div><Link to="/analyses">Back to analyses</Link></div>;
  if (status.status === "failed") return <div className="page-content"><div className="error-banner" role="alert"><span>!</span><div><strong>The analysis stopped</strong><p>{status.error || "Something went wrong."}</p></div></div><Link className="secondary-button" to="/upload">Try again</Link></div>;
  if (!report) return <div className="page-content pg-anim"><RunProgress status={status}/></div>;
  if (!view) return <div className="page-content"><div className="al-panel">This analysis was made by an older version of Alpha. Please run it again to see the new report.</div><Link className="secondary-button" to="/upload">Run again</Link></div>;

  const files = `${report.files.length} file${report.files.length === 1 ? "" : "s"}: ${report.files.map((f) => f.name).join(", ")}`;
  let body;
  if (section === "overview") body = <><Head title="Overview" intro={files}/><OverviewPage id={id} report={report} view={view}/></>;
  else if (AREA_PAGES[section]) body = <AreaPage page={section} report={report} view={view}/>;
  else if (section === "trends") body = <TrendsPage report={report}/>;
  else if (section === "mapping") body = <><Head title="Header Mapping" intro="What Alpha understood each column to mean, and how it used it."><Link className="secondary-button" to="/upload">Change the mapping</Link></Head><ReadTab report={report} view={view} open={() => go("suggestions")}/></>;
  else if (section === "quality") body = <><Head title="Data Quality" intro="Every check Alpha ran on your rows, and what it found."/><DataTab report={report} view={view}/></>;
  else if (section === "explorer") body = <><Head title="Data Explorer" intro="Every chart and finding, grouped by area."/><ExploreTab report={report} view={view}/></>;
  else if (section === "suggestions") body = <><Head title="Suggestions" intro="What Alpha found, ranked by importance and the money involved."/><FindingsTab view={view}/></>;
  else if (section === "ask") body = <><Head title="Ask Your Data" intro="Ask a question in plain words. Alpha answers from your rows only."/><AskTab analysisId={id} token={token} aiOn={report.ai?.provider && report.ai.provider !== "none"} initial={params.get("q") || undefined}/></>;
  else body = <><Head title={SOON[section][0]}/><div className="al-panel al-empty-page"><p>{SOON[section][1]}</p></div></>;
  return <div className="page-content al-report pg-anim" key={section}>{body}</div>;
}
