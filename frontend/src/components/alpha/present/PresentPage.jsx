import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { useAnalysis } from "../../../context/AnalysisContext";
import { THEMES, buildDeck } from "../../../utils/deck";
import Slide from "./Slide";
import { DEFAULTS, loadSettings, saveSettings, themeOf, themeVars } from "./store";
import { exportPptx } from "./exportPptx";
import "./present.css";

const W = 1280, H = 720;

/** The deck for this analysis, with the owner's settings applied. */
function useDeck(id) {
  const { select, report, view, status, error } = useAnalysis();
  useEffect(() => { if (id) select(id); }, [id]);          // eslint-disable-line react-hooks/exhaustive-deps
  const [settings, setSettings] = useState(() => loadSettings(id));
  useEffect(() => { setSettings(loadSettings(id)); }, [id]);
  const update = (patch) => setSettings((s) => { const n = { ...s, ...patch }; saveSettings(id, n); return n; });
  const business = settings.business || "Your business";
  const all = useMemo(() => (report && view ? buildDeck(report, view, { business, presenter: settings.presenter, title: settings.title }).map((s) => ({ ...s, biz: business })) : []), [report, view, business, settings.presenter, settings.title]);
  const slides = useMemo(() => all.filter((s) => !settings.off.includes(s.id)), [all, settings.off]);
  return { all, slides, settings, update, theme: themeOf(settings), ready: !!(report && view), failed: status?.status === "failed" || !!error, business };
}

function Loading({ failed }) { return <div className="dk-wait">{failed ? "This analysis could not be opened." : <><span className="spinner"/>Getting your slides ready…</>}</div>; }

/** Before presenting: names, theme, and which slides to include. */
export function Setup() {
  const { id } = useParams();
  const nav = useNavigate();
  const d = useDeck(id);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  if (!d.ready) return <Loading failed={d.failed}/>;
  const { settings, update, all, slides } = d;
  const toggle = (sid) => update({ off: settings.off.includes(sid) ? settings.off.filter((x) => x !== sid) : [...settings.off, sid] });
  async function ppt() { setBusy(true); setErr(""); try { await exportPptx(slides, d.theme, `${d.business} review`.replace(/[^\w ]+/g, "")); } catch (e) { setErr("Could not make the PowerPoint file. " + (e.message || "")); } finally { setBusy(false); } }
  return <div className="dk-setup" style={themeVars(d.theme)}>
    <header><Link to={`/analysis/${id}/overview`} className="dk-back">← Back to the analysis</Link><h1>Present this analysis</h1><p>Alpha builds the slides from your numbers. Change anything here, then press Start. Nothing leaves your computer.</p></header>
    <div className="dk-setup-grid">
      <section>
        <h2>Details</h2>
        <label>Slide title<input value={settings.title} placeholder={`${d.business}: business review`} onChange={(e) => update({ title: e.target.value })}/></label>
        <label>Business name<input value={settings.business} placeholder={d.business} onChange={(e) => update({ business: e.target.value })}/></label>
        <label>Presenter<input value={settings.presenter} placeholder="Your name" onChange={(e) => update({ presenter: e.target.value })}/></label>
        <h2>Look</h2>
        <div className="dk-themes">{Object.entries(THEMES).map(([k, t]) => <button key={k} type="button" className={settings.theme === k ? "on" : ""} onClick={() => update({ theme: k })} style={{ background: `#${t.bg}`, color: `#${t.text}`, borderColor: settings.theme === k ? `#${t.accent}` : "transparent" }}><i style={{ background: `#${t.accent}` }}/>{t.name}</button>)}</div>
      </section>
      <section>
        <h2>Slides <small>{slides.length} of {all.length} included</small></h2>
        <ul className="dk-list">{all.map((s, i) => <li key={s.id}><label><input type="checkbox" checked={!settings.off.includes(s.id)} onChange={() => toggle(s.id)}/><span>{i + 1}. {s.label}</span><em>{String(s.title).slice(0, 70)}</em></label></li>)}</ul>
      </section>
    </div>
    <div className="dk-actions-row">
      <button type="button" className="dk-go" disabled={!slides.length} onClick={() => nav(`/present/${id}/play`)}>Start presenting</button>
      <button type="button" className="dk-alt" disabled={!slides.length} onClick={() => window.open(`/present/${id}/play`, "_blank")}>Start with presenter view</button>
      <button type="button" className="dk-alt" disabled={busy || !slides.length} onClick={ppt}>{busy ? "Making…" : "Download PowerPoint"}</button>
      <button type="button" className="dk-alt" disabled={!slides.length} onClick={() => window.open(`/present/${id}/print`, "_blank")}>Download PDF</button>
      <button type="button" className="dk-alt" disabled={!slides.length} onClick={() => window.open(`/present/${id}/handout`, "_blank")}>One-page handout</button>
    </div>
    {err && <p className="dk-err">{err}</p>}
    <p className="dk-hint">While presenting: ← → to move, F full screen, B blank screen, A auto-play, P presenter view, Esc to leave. In the PDF dialogs choose “Save as PDF”.</p>
  </div>;
}

function useChannel(id, onMessage) {
  const ch = useRef(null);
  const cb = useRef(onMessage); cb.current = onMessage;
  useEffect(() => { try { ch.current = new BroadcastChannel(`alphaDeck:${id}`); ch.current.onmessage = (e) => cb.current(e.data); } catch { ch.current = null; } return () => ch.current?.close(); }, [id]);
  return useCallback((m) => { try { ch.current?.postMessage(m); } catch { /* channel closed */ } }, []);
}

/** A slide scaled to whatever box it is in. */
function Fit({ children }) {
  const box = useRef(null);
  const [k, setK] = useState(1);
  useEffect(() => { const f = () => { const r = box.current?.getBoundingClientRect(); if (r) setK(Math.min(r.width / W, r.height / H)); }; f(); const ro = new ResizeObserver(f); ro.observe(box.current); return () => ro.disconnect(); }, []);
  return <div ref={box} className="dk-fit"><div className="dk-canvas" style={{ width: W, height: H, transform: `translate(-50%,-50%) scale(${k})` }}>{children}</div></div>;
}

export function Play() {
  const { id } = useParams();
  const [q] = useSearchParams();
  const nav = useNavigate();
  const d = useDeck(id);
  const [i, setI] = useState(Math.max(0, (Number(q.get("at")) || 1) - 1));
  const [blank, setBlank] = useState(false);
  const [auto, setAuto] = useState(false);
  const n = d.slides.length;
  const send = useChannel(id, (m) => { if (m.type === "go") setI(Math.min(Math.max(0, m.i), Math.max(0, n - 1))); if (m.type === "hello") send({ type: "at", i, n }); });
  const go = useCallback((to) => setI((c) => { const v = Math.min(Math.max(0, typeof to === "function" ? to(c) : to), Math.max(0, n - 1)); return v; }), [n]);
  useEffect(() => { send({ type: "at", i, n }); }, [i, n, send]);
  useEffect(() => { if (!auto) return; const t = setInterval(() => setI((c) => (c + 1 >= n ? (setAuto(false), c) : c + 1)), 8000); return () => clearInterval(t); }, [auto, n]);
  useEffect(() => {
    const onKey = (e) => {
      if (e.target.closest?.("input,textarea")) return;
      const k = e.key;
      if (["ArrowRight", "ArrowDown", "PageDown", " ", "Enter"].includes(k)) { e.preventDefault(); go((c) => c + 1); }
      else if (["ArrowLeft", "ArrowUp", "PageUp", "Backspace"].includes(k)) { e.preventDefault(); go((c) => c - 1); }
      else if (k === "Home") go(0); else if (k === "End") go(n - 1);
      else if (k === "f" || k === "F") { document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen?.(); }
      else if (k === "b" || k === "B" || k === ".") setBlank((b) => !b);
      else if (k === "a" || k === "A") setAuto((a) => !a);
      else if (k === "p" || k === "P") window.open(`/present/${id}/presenter?at=${i + 1}`, "alphaPresenter", "width=1100,height=700");
      else if (k === "Escape" && !document.fullscreenElement) nav(`/present/${id}`);
    };
    window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey);
  }, [go, n, id, i, nav]);
  if (!d.ready) return <Loading failed={d.failed}/>;
  const s = d.slides[i];
  if (!s) return <Loading failed/>;
  return <div className="dk-stage" style={themeVars(d.theme)} onClick={(e) => { if (!e.target.closest(".dk-bar-ui")) go((c) => c + 1); }}>
    <Fit><div key={s.id} className="dk-fade"><Slide s={s} index={i} total={n}/></div></Fit>
    {blank && <div className="dk-blank"/>}
    <div className="dk-progress"><i style={{ width: `${((i + 1) / n) * 100}%` }}/></div>
    <div className="dk-bar-ui">
      <button type="button" onClick={() => go(i - 1)} disabled={i === 0} aria-label="Previous slide">‹</button>
      <button type="button" onClick={() => go(i + 1)} disabled={i === n - 1} aria-label="Next slide">›</button>
      <button type="button" className={auto ? "on" : ""} onClick={() => setAuto(!auto)}>{auto ? "Pause" : "Auto-play"}</button>
      <button type="button" onClick={() => window.open(`/present/${id}/presenter?at=${i + 1}`, "alphaPresenter", "width=1100,height=700")}>Presenter view</button>
      <button type="button" onClick={() => (document.fullscreenElement ? document.exitFullscreen() : document.documentElement.requestFullscreen?.())}>Full screen</button>
      <Link to={`/present/${id}`}>Exit</Link>
    </div>
  </div>;
}

const clock = (s) => `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

/** The speaker's window: current slide, next slide, notes and a timer. Controls the audience window. */
export function Presenter() {
  const { id } = useParams();
  const [q] = useSearchParams();
  const d = useDeck(id);
  const [i, setI] = useState(Math.max(0, (Number(q.get("at")) || 1) - 1));
  const [secs, setSecs] = useState(0);
  const [run, setRun] = useState(true);
  const n = d.slides.length;
  const send = useChannel(id, (m) => { if (m.type === "at") setI(m.i); });
  useEffect(() => { send({ type: "hello" }); }, [send]);
  useEffect(() => { if (!run) return; const t = setInterval(() => setSecs((x) => x + 1), 1000); return () => clearInterval(t); }, [run]);
  const go = useCallback((to) => { const v = Math.min(Math.max(0, to), Math.max(0, n - 1)); setI(v); send({ type: "go", i: v }); }, [n, send]);
  useEffect(() => {
    const onKey = (e) => { if (["ArrowRight", "PageDown", " "].includes(e.key)) { e.preventDefault(); go(i + 1); } else if (["ArrowLeft", "PageUp"].includes(e.key)) { e.preventDefault(); go(i - 1); } };
    window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey);
  }, [go, i]);
  if (!d.ready) return <Loading failed={d.failed}/>;
  const s = d.slides[i], next = d.slides[i + 1];
  if (!s) return <Loading failed/>;
  return <div className="dk-presenter" style={themeVars(d.theme)}>
    <div className="dk-pv-main"><div className="dk-pv-cur"><Fit><Slide s={s} index={i} total={n}/></Fit></div>
      <div className="dk-pv-ctl"><button type="button" onClick={() => go(i - 1)} disabled={i === 0}>‹ Back</button><b>{i + 1} / {n}</b><button type="button" onClick={() => go(i + 1)} disabled={i === n - 1}>Next ›</button></div></div>
    <aside>
      <div className="dk-pv-timer"><b>{clock(secs)}</b><button type="button" onClick={() => setRun(!run)}>{run ? "Pause" : "Resume"}</button><button type="button" onClick={() => setSecs(0)}>Reset</button></div>
      <h3>Next</h3><div className="dk-pv-next">{next ? <Fit><Slide s={next} index={i + 1} total={n}/></Fit> : <p>End of the talk.</p>}</div>
      <h3>Speaker notes</h3><p className="dk-pv-notes">{s.notes || "No notes for this slide."}</p>
    </aside>
  </div>;
}

/** Every slide stacked, one per page, sized for “Save as PDF”. */
export function Print() {
  const { id } = useParams();
  const d = useDeck(id);
  useEffect(() => { if (d.ready) { const t = setTimeout(() => window.print(), 700); return () => clearTimeout(t); } }, [d.ready]);
  if (!d.ready) return <Loading failed={d.failed}/>;
  return <div className="dk-print" style={themeVars(d.theme)}>
    <div className="dk-print-note">Choose “Save as PDF” in the print window. Turn on “Background graphics” so the colours show.</div>
    {d.slides.map((s, i) => <div key={s.id} className="dk-print-page"><div className="dk-canvas dk-static" style={{ width: W, height: H }}><Slide s={s} index={i} total={d.slides.length}/></div></div>)}
  </div>;
}

/** One A4 page to hand out or email. */
export function Handout() {
  const { id } = useParams();
  const d = useDeck(id);
  useEffect(() => { if (d.ready) { const t = setTimeout(() => window.print(), 700); return () => clearTimeout(t); } }, [d.ready]);
  if (!d.ready) return <Loading failed={d.failed}/>;
  const by = (k) => d.all.filter((s) => s.kind === k);
  const snap = by("snapshot")[0], risks = by("risk"), acts = by("actions")[0], fc = by("forecast")[0], title = by("title")[0], good = by("good")[0];
  return <div className="dk-hand">
    <div className="dk-print-note">Choose “Save as PDF” in the print window.</div>
    <header><h1>{title?.title}</h1><p>{[title?.subtitle, title?.presenter && `Presented by ${title.presenter}`].filter(Boolean).join(" · ")}</p></header>
    {snap && <section><h2>{snap.title}</h2><div className="dk-h-figs">{snap.figures.map((f) => <div key={f.label}><span>{f.label}</span><b>{f.value}</b>{f.change && <small className={`t-${f.tone}`}>{f.change}</small>}</div>)}</div>
      <p className="dk-h-sm">{snap.business ? `Business health ${snap.business.score}/100 (${snap.business.label.toLowerCase()}). ` : ""}{snap.data != null ? `Data health ${snap.data}/100.` : ""}</p></section>}
    {risks.length > 0 && <section><h2>Biggest problems</h2><ol>{risks.map((r) => <li key={r.id}><b>{r.title}</b>{r.money && <em> ({r.money})</em>}{r.action && <p>Do this: {r.action}</p>}</li>)}</ol></section>}
    {good && <section><h2>Going well</h2><ul>{good.items.map((g, k) => <li key={k}>{g.headline}</li>)}</ul></section>}
    {fc && <section><h2>Next three months</h2><p>About <b>{fc.total.mid}</b> expected (likely {fc.total.low} to {fc.total.high}). {fc.trust ? `Past test: off by about ${fc.trust.error}% a month.` : fc.untested}</p></section>}
    {acts && <section><h2>Action plan</h2><ol>{acts.items.map((a, k) => <li key={k}><b>{a.title}</b>{a.impact && <em> ({a.impact})</em>}<p>{a.action}</p></li>)}</ol></section>}
    <footer>Made with Alpha from the uploaded files. Every number comes from your data.</footer>
  </div>;
}
