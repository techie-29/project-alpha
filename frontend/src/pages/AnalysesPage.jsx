import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listAnalyses } from "../services/alphaApi";

const STATUS = { queued: "Queued", running: "Running", done: "Ready", failed: "Stopped" };

export default function AnalysesPage({ token }) {
  const [items, setItems] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { listAnalyses(token).then(setItems).catch((e) => setError(e.message)); }, [token]);
  return <div className="page-content">
    <section className="page-header"><span className="eyebrow">Home</span><h1>Your analyses</h1><p>Each analysis is a snapshot of what Alpha found in a set of files. Run a new one whenever you have fresh data.</p></section>
    {error && <div className="error-banner" role="alert"><span>!</span><div><p>{error}</p></div></div>}
    {!items && !error && <div className="analytics-loading"><span className="spinner"/>Loading…</div>}
    {items && items.length === 0 && <div className="al-panel"><h3 className="al-h3">Nothing here yet</h3><p>Upload your first files and Alpha will tell you what changed in your business and where to look.</p><Link className="primary-button" to="/upload">Start an analysis</Link></div>}
    {items && items.length > 0 && <>
      <div className="al-actions"><Link className="primary-button" to="/upload">New analysis</Link></div>
      <ul className="al-analyses">{items.map((a) => <li key={a.id}><Link to={`/analysis/${a.id}`}>
        <strong>{new Date(a.createdAt).toLocaleString()}</strong>
        <span>{(a.file_ids || []).length} file{(a.file_ids || []).length === 1 ? "" : "s"}</span>
        <span className={`al-badge al-status-${a.status}`}>{STATUS[a.status]}{a.status === "running" ? ` ${a.progress}%` : ""}</span>
        {a.error && <small>{a.error}</small>}
      </Link></li>)}</ul>
    </>}
  </div>;
}
