import { useEffect, useState } from "react";
import { listSamples } from "../../services/samples";

const ICON = { grocery: "🛒", boutique: "👗", cafe: "☕" };

/** "No file handy?" Three ready-made businesses that run through the same steps as real data. */
export default function SamplePicker({ onPick, busy }) {
  const [samples, setSamples] = useState([]);
  useEffect(() => { listSamples().then(setSamples).catch(() => setSamples([])); }, []);
  if (!samples.length) return null;
  return <section className="al-panel sp">
    <div className="sp-head"><h3 className="al-h3">No file handy? Try a sample business</h3>
      <p className="al-muted">Real-looking data with a few problems hidden in it. It goes through the same steps as your own files, and a short tour shows what Alpha found.</p></div>
    <div className="sp-list">{samples.map((s) => <button key={s.key} type="button" className="sp-card" disabled={!!busy} onClick={() => onPick(s)}>
      <span className="sp-icon" aria-hidden="true">{ICON[s.key] || "📊"}</span>
      <strong>{busy === s.key ? "Loading…" : s.name}</strong>
      <small>{s.about}</small>
      <em>{s.files.length} files</em>
    </button>)}</div>
  </section>;
}
