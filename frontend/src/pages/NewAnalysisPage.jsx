import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import UploadZone from "../components/UploadZone";
import ReadingReview from "../components/alpha/ReadingReview";
import { deleteFile, listFiles, readFiles, startAnalysis, uploadFiles } from "../services/alphaApi";
import { buildConfirmations, fileSize } from "../utils/alphaFormat";

const EMPTY = { roles: {}, links: {}, timeCols: {}, rowOrder: {} };

export default function NewAnalysisPage({ token }) {
  const navigate = useNavigate();
  const [files, setFiles] = useState([]);
  const [selected, setSelected] = useState(new Set());
  const [dragging, setDragging] = useState(false);
  const [progress, setProgress] = useState(null);
  const [reading, setReading] = useState(null);
  const [choices, setChoices] = useState(EMPTY);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");

  const refresh = useCallback(() => listFiles(token).then(setFiles).catch((e) => setError(e.message)), [token]);
  useEffect(() => { refresh(); }, [refresh]);

  async function onFiles(picked) {
    setError(""); setProgress(0);
    try {
      const added = await uploadFiles(picked.slice(0, 10), token, setProgress);
      await refresh();
      setSelected((s) => new Set([...s, ...added.map((a) => a.id)]));
      setReading(null);
    } catch (e) { setError(e.message); } finally { setProgress(null); }
  }

  function toggle(id) {
    setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
    setReading(null); setChoices(EMPTY);
  }

  async function remove(id) {
    try { await deleteFile(id, token); setSelected((s) => { const n = new Set(s); n.delete(id); return n; }); setReading(null); await refresh(); }
    catch (e) { setError(e.message); }
  }

  async function review() {
    setError(""); setBusy("reading");
    try { setReading(await readFiles([...selected], buildConfirmations(choices), token)); }
    catch (e) { setError(e.message); } finally { setBusy(""); }
  }

  async function run() {
    setError(""); setBusy("starting");
    try { const id = await startAnalysis([...selected], buildConfirmations(choices), token); navigate(`/analysis/${id}`); }
    catch (e) { setError(e.message); setBusy(""); }
  }

  return <div className="page-content">
    <section className="page-header">
      <span className="eyebrow">New analysis</span>
      <h1>Upload your business files</h1>
      <p>Any CSV or Excel files: sales, costs, tickets, bookings, anything with rows. Files can be linked or completely separate. Alpha works out what each column means and shows you before it starts.</p>
    </section>

    <section className="upload-panel">
      <UploadZone onFilesSelect={onFiles} isDragging={dragging} setIsDragging={setDragging} disabled={progress !== null}/>
      {progress !== null && <div className="al-progress" role="progressbar" aria-valuenow={progress}><i style={{ width: `${progress}%` }}/><span>Uploading {progress}%</span></div>}
    </section>

    {error && <div className="error-banner" role="alert"><span>!</span><div><strong>Something went wrong</strong><p>{error}</p></div></div>}

    {files.length > 0 && <section className="al-panel">
      <h3 className="al-h3">Your files</h3>
      <p className="al-muted">Tick the files for this analysis.</p>
      <ul className="al-files">{files.map((f) => <li key={f.id}>
        <label><input type="checkbox" checked={selected.has(f.id)} onChange={() => toggle(f.id)}/><span><strong>{f.name}</strong><small>{fileSize(f.sizeBytes)} · uploaded {new Date(f.createdAt).toLocaleDateString()}</small></span></label>
        <button type="button" className="al-link-button" onClick={() => remove(f.id)} aria-label={`Delete ${f.name}`}>Delete</button>
      </li>)}</ul>
      <div className="al-actions">
        <button type="button" className="primary-button" disabled={!selected.size || busy !== ""} onClick={review}>{busy === "reading" ? "Reading…" : reading ? "Read again" : "Next: check how Alpha reads them"}</button>
      </div>
    </section>}

    {reading && <>
      <ReadingReview reading={reading} choices={choices} setChoices={setChoices}/>
      <div className="al-actions al-sticky">
        <button type="button" className="secondary-button" onClick={review} disabled={busy !== ""}>Apply my changes and re-read</button>
        <button type="button" className="primary-button" onClick={run} disabled={busy !== ""}>{busy === "starting" ? "Starting…" : "Run the analysis"}</button>
      </div>
    </>}
  </div>;
}
