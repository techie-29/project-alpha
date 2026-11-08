import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listSamples } from "../../services/samples";

const KEY = "alphaTourDone";
const done = (id) => { try { return (JSON.parse(localStorage.getItem(KEY) || "[]")).includes(id); } catch { return false; } };
const markDone = (id) => { try { const l = JSON.parse(localStorage.getItem(KEY) || "[]"); localStorage.setItem(KEY, JSON.stringify([...l, id].slice(-30))); } catch { /* storage blocked */ } };

/** A short, skippable walk through what Alpha found in a sample business. */
export default function SampleTour({ id, sample, section }) {
  const navigate = useNavigate();
  const [steps, setSteps] = useState(null);
  const [at, setAt] = useState(0);
  const [open, setOpen] = useState(() => !done(id));
  useEffect(() => { listSamples().then((l) => setSteps((l.find((s) => s.key === sample) || {}).tour || [])).catch(() => setSteps([])); }, [sample]);
  if (!open || !steps?.length) return null;
  const step = steps[at];
  const go = (n) => { setAt(n); navigate(`/analysis/${id}/${steps[n].section}`); };
  const close = () => { markDone(id); setOpen(false); };
  return <aside className="tour" role="dialog" aria-label="Sample tour">
    <div className="tour-top"><span>Tour · {at + 1} of {steps.length}</span><button type="button" className="tour-x" onClick={close} aria-label="Close the tour">×</button></div>
    <strong>{step.title}</strong>
    <p>{step.text}</p>
    {section !== step.section && <button type="button" className="al-link-button" onClick={() => go(at)}>Show me</button>}
    <div className="tour-bar" aria-hidden="true">{steps.map((s, n) => <i key={n} className={n <= at ? "on" : ""}/>)}</div>
    <div className="tour-actions">
      <button type="button" className="secondary-button" onClick={() => go(at - 1)} disabled={at === 0}>Back</button>
      {at < steps.length - 1 ? <button type="button" className="primary-button" onClick={() => go(at + 1)}>Next</button>
        : <button type="button" className="primary-button" onClick={close}>Finish</button>}
    </div>
  </aside>;
}
