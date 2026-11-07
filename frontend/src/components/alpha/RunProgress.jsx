import { useEffect, useRef, useState } from "react";

// The engine reports a stage name and a percentage. These are the milestones those percentages fall into.
const STEPS = [
  { at: 0, title: "Reading your files", text: "Opening every file and sheet, finding the header, fixing separators and blanks." },
  { at: 20, title: "Understanding columns", text: "Working out what each column means and linking the files into one business." },
  { at: 26, title: "Checking your data", text: "27 checks: duplicates, missing values, impossible numbers, dates in the wrong order." },
  { at: 28, title: "Building the overview", text: "Key numbers and charts for sales, customers, products and stock." },
  { at: 30, title: "Looking for patterns", text: "Trends, changes, groups that differ, customers, stock, outliers." },
  { at: 88, title: "Ranking what matters", text: "Every finding is checked against chance and ranked by the money involved." },
];

function clean(stage) {
  return String(stage || "").replace(/^.*?: (?=Looking for)/, "").trim();
}

function fmtTime(s) {
  if (s < 60) return `${Math.round(s)}s`;
  return `${Math.floor(s / 60)}m ${String(Math.round(s % 60)).padStart(2, "0")}s`;
}

/** The screen shown while an analysis runs: milestones, a live feed of what the engine is doing, time taken and time left. */
export default function RunProgress({ status, files }) {
  const pct = Math.max(1, Math.min(100, status.progress || 0));
  const start = useRef(status.createdAt ? new Date(status.createdAt).getTime() : Date.now());
  const [now, setNow] = useState(Date.now());
  const [feed, setFeed] = useState([]);
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 1000); return () => clearInterval(t); }, []);
  useEffect(() => {
    const s = clean(status.stage);
    if (!s || s === "Starting") return;
    setFeed((f) => (f[0]?.text === s ? f : [{ text: s, at: Date.now() }, ...f].slice(0, 12)));
  }, [status.stage]);
  const elapsed = Math.max(0, (now - start.current) / 1000);
  const left = pct >= 8 && pct < 100 ? (elapsed * (100 - pct)) / pct : null;
  const cur = STEPS.reduce((k, s, i) => (pct >= s.at ? i : k), 0);
  return <div className="rp">
    <section className="rp-head">
      <div className="rp-ring" style={{ "--p": pct }} role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100} aria-label="Analysis progress">
        <b>{pct}<small>%</small></b></div>
      <div>
        <span className="eyebrow">Analysing{files ? ` ${files}` : ""}</span>
        <h1>{STEPS[cur].title}…</h1>
        <p>{STEPS[cur].text}</p>
        <p className="rp-time">{fmtTime(elapsed)} so far{left != null ? ` · about ${fmtTime(left)} left` : ""} · you can leave this page, it keeps running</p>
      </div>
    </section>
    <div className="rp-body">
      <ol className="rp-steps">{STEPS.map((s, i) => <li key={s.title} className={i < cur ? "done" : i === cur ? "now" : ""}>
        <i aria-hidden="true">{i < cur ? "✓" : i + 1}</i><div><strong>{s.title}</strong>{i === cur && <span>{s.text}</span>}</div></li>)}</ol>
      <section className="rp-feed" aria-live="polite"><h3>Live</h3>
        {feed.length === 0 ? <p className="al-muted">Starting the engine…</p> : <ul>{feed.map((f, i) => <li key={f.at} className={i === 0 ? "now" : ""}>
          <span>{i === 0 ? <span className="rp-dot"/> : "✓"}</span>{f.text}<time>{new Date(f.at).toLocaleTimeString([], { minute: "2-digit", second: "2-digit" })}</time></li>)}</ul>}
      </section>
    </div>
    {status.engineMessage && <p className="al-note-warn">{status.engineMessage}</p>}
  </div>;
}
