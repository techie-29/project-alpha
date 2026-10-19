import { useState } from "react";
import { askAlpha } from "../../services/alphaApi";

function show(r) {
  if (r === null || r === undefined) return "";
  if (typeof r !== "object") return String(r);
  if (r.columns) return [r.columns.join(" | "), ...r.rows.map((x) => x.join(" | "))].join("\n");
  return Object.entries(r).map(([k, v]) => `${k}: ${typeof v === "object" ? JSON.stringify(v) : v}`).join("\n");
}

export default function AskAlpha({ analysisId, token }) {
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  async function submit(e) {
    e.preventDefault();
    if (q.trim().length < 3) return;
    setBusy(true); setErr(""); setRes(null);
    try { setRes(await askAlpha(analysisId, q, token)); } catch (x) { setErr(x.message); } finally { setBusy(false); }
  }
  return <section className="al-panel">
    <h3 className="al-h3">Ask Alpha</h3>
    <p className="al-muted">Ask about your data in plain words, for example "Which region sold the most last year?". Alpha runs the calculation and shows its working.</p>
    <form className="al-ask" onSubmit={submit}>
      <input value={q} maxLength={500} onChange={(e) => setQ(e.target.value)} placeholder="Type your question" aria-label="Your question"/>
      <button className="primary-button" type="submit" disabled={busy || q.trim().length < 3}>{busy ? "Working…" : "Ask"}</button>
    </form>
    {err && <p className="al-note-warn">{err}</p>}
    {res && <div className="al-answer">
      {res.answer ? <p><strong>{res.answer}</strong></p> : <p className="al-muted">{res.note}</p>}
      {res.calculations?.length > 0 && <details><summary>How Alpha worked this out</summary>
        {res.calculations.map((c, i) => <div key={i}><p className="al-muted">{c.why}{c.ok ? "" : ` (${c.error})`}</p>{c.ok && <pre>{show(c.result)}</pre>}</div>)}</details>}
    </div>}
  </section>;
}
