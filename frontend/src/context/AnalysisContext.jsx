import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { getAnalysis, getReport, listAnalyses } from "../services/alphaApi";
import { viewOf } from "../components/alpha/report/Report";

const Ctx = createContext(null);
const LAST = "alphaLastAnalysis";

function readLast() { try { return localStorage.getItem(LAST); } catch { return null; } }
function writeLast(id) { try { localStorage.setItem(LAST, id); } catch { /* storage blocked: fine */ } }

/** The analysis the owner is looking at, shared by the sidebar, the top bar and every page. */
export function AnalysisProvider({ token, children }) {
  const [analyses, setAnalyses] = useState(null);
  const [currentId, setCurrentId] = useState(readLast);
  const [status, setStatus] = useState(null);
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");

  const refreshList = useCallback(() => listAnalyses(token).then((list) => { setAnalyses(list); return list; }).catch(() => setAnalyses([])), [token]);
  useEffect(() => { refreshList(); }, [refreshList]);

  // no analysis chosen yet (or the remembered one is gone): use the newest finished one
  const chosen = useRef(new Set());                 // ids opened by URL or the switcher: never replaced, even before the list knows them
  useEffect(() => {
    if (!analyses) return;
    if (currentId && (analyses.some((a) => a.id === currentId) || chosen.current.has(currentId))) return;
    const done = analyses.find((a) => a.status === "done") || analyses[0];
    setCurrentId(done ? done.id : null);
  }, [analyses, currentId]);

  const select = useCallback((id) => {
    if (!id) return;
    chosen.current.add(id);
    if (id !== currentId) { setCurrentId(id); writeLast(id); }
    if (analyses && !analyses.some((a) => a.id === id)) refreshList();          // a run just started: put it in the switcher
  }, [currentId, analyses, refreshList]);

  useEffect(() => {
    setStatus(null); setReport(null); setError("");
    if (!currentId) return;
    writeLast(currentId);
    let active = true, timer;
    async function poll() {
      try {
        const s = await getAnalysis(currentId, token);
        if (!active) return;
        setStatus(s);
        if (s.status === "done") { const r = await getReport(currentId, token); if (active) setReport(r); refreshList(); return; }
        if (s.status === "failed") return;
        timer = setTimeout(poll, 2000);
      } catch (e) { if (active) setError(e.message); }
    }
    poll();
    return () => { active = false; clearTimeout(timer); };
  }, [currentId, token, refreshList]);

  const view = useMemo(() => (report && (report.version === 2 || report.brain === "full AI") ? viewOf(report) : null), [report]);
  /** An analysis was deleted: stop pointing at it and let the newest remaining one take over. */
  const forget = useCallback((id) => {
    chosen.current.delete(id);
    try { if (localStorage.getItem(LAST) === id) localStorage.removeItem(LAST); } catch { /* storage unavailable */ }
    setCurrentId((c) => (c === id ? null : c));
    return refreshList();
  }, [refreshList]);

  const value = useMemo(() => ({ token, forget, analyses, currentId, select, status, report, view, error, refreshList }), [token, forget, analyses, currentId, select, status, report, view, error, refreshList]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export const useAnalysis = () => useContext(Ctx);

/** Share of rows that are fine or were cleaned, 0-100, from the data check. */
export function healthOf(report) {
  const r = report?.data_check?.rows;
  if (!r) return null;
  const tot = (r.ok || 0) + (r.fixed || 0) + (r.flagged || 0) + (r.left_out || 0);
  if (!tot) return null;
  const good = (r.ok || 0) + (r.fixed || 0);
  return good === tot ? 100 : Math.min(99, Math.floor((100 * good) / tot));
}

/** Things that need the owner's attention: data checks that warn or fail, and findings that are risks. */
export function alertsOf(report, view) {
  const out = [];
  for (const f of report?.data_check?.files || []) for (const c of f.checks || []) if (c.status === "fail" || c.status === "warn") out.push({ kind: "data", level: c.status, title: c.title, detail: c.detail, file: f.file });
  for (const c of view?.cards || []) if (c.tone === "risk") out.push({ kind: "finding", level: "warn", title: c.headline, detail: c.why_it_matters || "", area: c.area, id: c.id, insight: c.insight_id, fix: c.look_into || "" });
  return out;
}
