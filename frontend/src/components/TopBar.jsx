import { useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { alertsOf, healthOf, useAnalysis } from "../context/AnalysisContext";
import { sampleOf } from "../services/samples";
import { downloadExport } from "../services/alphaApi";
import { NAV } from "./Sidebar";

function label(a) {
  const n = (a.file_ids || []).length;
  return `${new Date(a.createdAt).toLocaleDateString(undefined, { day: "numeric", month: "short" })} · ${a.fileNames?.length ? a.fileNames.join(", ") : `${n} file${n === 1 ? "" : "s"}`}${a.status === "done" ? "" : ` (${a.status})`}`;
}

function Search({ currentId, report, view }) {
  const [q, setQ] = useState("");
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const items = useMemo(() => {
    const pages = NAV.flatMap((g) => g.items).map((it) => ({ kind: "Page", text: it.label, to: it.to || (currentId ? `/analysis/${currentId}/${it.section}` : null) }));
    const findings = (view?.cards || []).map((c) => ({ kind: "Finding", text: c.headline, to: `/analysis/${currentId}/suggestions#${c.id}` }));
    const figures = (report?.overview?.tiles || []).map((t) => ({ kind: "Number", text: t.label, to: `/analysis/${currentId}/${t.area === "customers" || t.area === "service" ? "customers" : t.area === "stock" || t.area === "products" || t.area === "operations" ? "products" : "sales"}` }));
    const cols = (report?.reading?.files || []).flatMap((f) => (f.columns || []).map((c) => ({ kind: "Column", text: `${c.name} (${f.name})`, to: `/analysis/${currentId}/mapping` })));
    return [...pages, ...figures, ...findings, ...cols].filter((x) => x.to);
  }, [currentId, report, view]);
  const shown = q.trim() ? items.filter((x) => x.text.toLowerCase().includes(q.trim().toLowerCase())).slice(0, 8) : [];
  const go = (x) => { navigate(x.to); setQ(""); setOpen(false); };
  return <div className="tb-search" onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setOpen(false); }}>
    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
    <input type="search" placeholder="Search pages, numbers, findings, columns" value={q} aria-label="Search"
      onChange={(e) => { setQ(e.target.value); setOpen(true); }} onFocus={() => setOpen(true)}
      onKeyDown={(e) => { if (e.key === "Enter" && shown[0]) go(shown[0]); if (e.key === "Escape") setOpen(false); }}/>
    {open && shown.length > 0 && <ul className="tb-results" role="listbox">{shown.map((x, i) => <li key={i}><button type="button" onClick={() => go(x)}><small>{x.kind}</small>{x.text}</button></li>)}</ul>}
    {open && q.trim() && shown.length === 0 && <ul className="tb-results"><li className="tb-none">Nothing matches “{q}”.</li></ul>}
  </div>;
}

export default function TopBar({ accountLabel, onLogout, onMenu }) {
  const { analyses, currentId, select, report, view, token, status } = useAnalysis();
  const navigate = useNavigate();
  const [menu, setMenu] = useState("");
  const [busy, setBusy] = useState("");
  const health = healthOf(report);
  const alerts = useMemo(() => alertsOf(report, view), [report, view]);
  const exportable = report && view && !view.full;
  const timer = useRef(null);
  const toggle = (m) => setMenu((x) => (x === m ? "" : m));
  async function exp(format) {
    setBusy(format); setMenu("");
    try { await downloadExport(currentId, format, token); } catch { /* the page shows errors */ } finally { setBusy(""); }
  }
  const initials = (accountLabel || "A").slice(0, 2).toUpperCase();
  return <header className="topbar" onBlur={(e) => { if (!e.currentTarget.contains(e.relatedTarget)) { clearTimeout(timer.current); timer.current = setTimeout(() => setMenu(""), 120); } }}>
    <button type="button" className="tb-menu" aria-label="Open menu" onClick={onMenu}><svg viewBox="0 0 24 24"><path d="M4 6h16M4 12h16M4 18h16"/></svg></button>
    <div className="mobile-brand"><span>A</span>Alpha</div>
    {analyses?.length > 0 && <label className="tb-switch"><span className="al-sr">Analysis</span>
      <select value={currentId || ""} onChange={(e) => { select(e.target.value); navigate(`/analysis/${e.target.value}/overview`); }}>
        {analyses.map((a) => <option key={a.id} value={a.id}>{label(a)}</option>)}
      </select></label>}
    {sampleOf(report) && <span className="tb-sample" title="This analysis uses a sample business, not your data">Sample data</span>}
    {health !== null && <button type="button" className={`tb-health ${health >= 90 ? "good" : health >= 70 ? "ok" : "bad"}`} title="Share of rows that are fine or were cleaned" onClick={() => navigate(`/analysis/${currentId}/quality`)}>
      <i/>Health {health}</button>}
    {status && status.status !== "done" && status.status !== "failed" && <span className="tb-running"><span className="spinner"/>{status.progress || 0}%</span>}
    <Search currentId={currentId} report={report} view={view}/>
    <div className="tb-actions">
      {exportable && <div className="tb-pop"><button type="button" className="tb-btn" onClick={() => toggle("export")} aria-expanded={menu === "export"} disabled={!!busy}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v12"/><path d="m7 11 5 5 5-5"/><path d="M5 20h14"/></svg>{busy ? "Preparing…" : "Export"}</button>
        {menu === "export" && <div className="tb-menu-list"><button type="button" onClick={() => exp("pdf")}>PDF report</button><button type="button" onClick={() => exp("xlsx")}>Excel workbook</button></div>}</div>}
      {currentId && <div className="tb-pop"><button type="button" className="tb-icon" aria-label={`${alerts.length} alerts`} onClick={() => toggle("alerts")} aria-expanded={menu === "alerts"}>
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8"/><path d="M10.3 21a2 2 0 0 0 3.4 0"/></svg>{alerts.length > 0 && <b>{alerts.length > 99 ? "99+" : alerts.length}</b>}</button>
        {menu === "alerts" && <div className="tb-menu-list tb-alerts">
          {alerts.length === 0 ? <p className="al-muted">Nothing needs your attention.</p> : alerts.slice(0, 6).map((a, i) => <button type="button" key={i} onClick={() => { setMenu(""); navigate(`/analysis/${currentId}/alerts`); }}>
            <small className={`tb-lvl ${a.level}`}>{a.kind === "data" ? "Data" : "Risk"}</small>{a.title}</button>)}
          <button type="button" className="tb-all" onClick={() => { setMenu(""); navigate(`/analysis/${currentId}/alerts`); }}>See all alerts →</button></div>}</div>}
      <div className="tb-pop"><button type="button" className="account-avatar" aria-label="Account" onClick={() => toggle("account")}>{initials}</button>
        {menu === "account" && <div className="tb-menu-list"><p className="tb-who">{accountLabel}</p><button type="button" onClick={() => { setMenu(""); navigate("/settings"); }}>Settings</button><button type="button" onClick={onLogout}>Sign out</button></div>}</div>
    </div>
  </header>;
}
