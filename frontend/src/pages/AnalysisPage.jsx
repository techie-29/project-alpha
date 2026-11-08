import ForecastPage from "../components/alpha/ForecastPage";
import SuggestionsPage from "../components/alpha/SuggestionsPage";
import { useEffect, useMemo } from "react";
import { Link, Navigate, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { AskTab, DataTab, FindingsTab, ReadTab } from "../components/alpha/report/Report";
import { AREA_PAGES, AreaPage, Head, TrendsPage } from "../components/alpha/AreaPage";
import { useAnalysis } from "../context/AnalysisContext";
import RunProgress from "../components/alpha/RunProgress";
import OverviewPage from "../components/alpha/OverviewPage";
import WhatIfPage from "../components/alpha/WhatIfPage";
import ExplorerPage from "../components/alpha/ExplorerPage";
import { PickContext } from "../components/alpha/viz/PickContext";
import SampleTour from "../components/alpha/SampleTour";
import { sampleOf } from "../services/samples";
import DictionaryPage from "../components/alpha/DictionaryPage";
import HoodPage from "../components/alpha/HoodPage";
import AlertsPage from "../components/alpha/AlertsPage";

const SECTIONS = new Set(["overview", "mapping", "quality", "dictionary", "explorer", "sales", "customers", "products", "trends", "suggestions", "forecast", "alerts", "whatif", "ask", "hood"]);
const OLD_TAB = { summary: "overview", findings: "suggestions", explore: "explorer", data: "quality", ask: "ask", reading: "mapping" };

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
  const pick = useMemo(() => {
    const words = (view?.cards || []).map((c) => [c.headline, ...(c.points || []), c.look_into].filter(Boolean).join(" ").toLowerCase());
    return (name) => {
      const n = String(name ?? "").trim();
      if (n.length < 2 || /^\(.*\)$|^other/i.test(n) || !words.some((w) => w.includes(n.toLowerCase()))) return null;
      return () => navigate(`/analysis/${id}/explorer?q=${encodeURIComponent(n)}`);
    };
  }, [view, id, navigate]);
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
  else if (section === "dictionary") body = <><Head title="Data Dictionary" intro="Every column in your files: what it means, what is in it, and how clean it is."/><DictionaryPage id={id} report={report}/></>;
  else if (section === "explorer") body = <><Head title="Data Explorer" intro="Search, filter and sort every finding Alpha made."/><ExplorerPage view={view}/></>;
  else if (section === "suggestions") body = <><Head title="Suggestions" intro="What to do, in order. Each one says what to do first, why, and how much money is behind it."/><SuggestionsPage id={id} report={report} view={view}/></>;
  else if (section === "forecast") body = <><Head title="Forecast" intro="Where revenue and orders are heading over the next three months, and how far to trust it."/><ForecastPage report={report}/></>;
  else if (section === "alerts") body = <><Head title="Alerts" intro="Everything that needs your attention, most serious first."/><AlertsPage id={id} report={report} view={view}/></>;
  else if (section === "whatif") body = <><Head title="What-If" intro="Try a change and see what it would do to revenue and profit."/><WhatIfPage report={report}/></>;
  else if (section === "hood") body = <><Head title="Under the Hood" intro="Everything Alpha did with your files, step by step."/><HoodPage id={id} report={report}/></>;
  else if (section === "ask") body = <><Head title="Ask Your Data" intro="Ask a question in plain words. Alpha answers from your rows only."/><AskTab analysisId={id} token={token} aiOn={report.ai?.provider && report.ai.provider !== "none"} initial={params.get("q") || undefined}/></>;
  return <PickContext.Provider value={pick}><div className="page-content al-report pg-anim" key={section}>{body}</div>{sampleOf(report) && <SampleTour id={id} sample={sampleOf(report)} section={section}/>}</PickContext.Provider>;
}
