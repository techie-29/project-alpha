import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Chart from "./viz/Chart";
import Tile from "./viz/Tile";
import { allSections, allTiles } from "./AreaPage";
import { change, fmtValue } from "../../utils/alphaFormat";
import { healthOf } from "../../context/AnalysisContext";

const KEY = ["revenue", "profit", "orders", "customers", "margin"];

function tileBy(tiles, metric) { return tiles.find((t) => t.metric === metric); }

function Spark({ values, color = "#12976a", h = 34 }) {
  const v = (values || []).filter((x) => Number.isFinite(x));
  if (v.length < 3) return null;
  const lo = Math.min(...v), hi = Math.max(...v), r = hi - lo || 1, w = 120;
  const pts = v.map((x, i) => `${(i * w) / (v.length - 1)},${h - 3 - ((x - lo) / r) * (h - 6)}`);
  const d = "M" + pts.join(" L");
  return <svg className="ov-spark" viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" aria-hidden="true"><path d={`${d} L${w},${h} L0,${h} Z`} fill={color} opacity=".12"/><path d={d} fill="none" stroke={color} strokeWidth="1.8"/></svg>;
}

/** One sentence about how the business is doing, built only from numbers the engine produced. */
function snapshot(tiles, risks, strengths, view, health) {
  const rev = tileBy(tiles, "revenue");
  const c = rev?.last_period?.change;
  const parts = [];
  if (Number.isFinite(c)) parts.push(`Revenue is ${c >= 0 ? "up" : "down"} ${Math.abs(c * 100).toFixed(1)}% (${rev.last_period.label} vs ${rev.last_period.previous_label})`);
  const m = tileBy(tiles, "margin");
  if (m && Number.isFinite(m.value)) parts.push(`profit margin is ${(m.value * 100).toFixed(1)}%`);
  const lead = parts.length ? parts.join(" and ") + "." : (view.headline || "Here is what your files show.");
  const title = risks.length ? `${risks.length} thing${risks.length === 1 ? "" : "s"} need${risks.length === 1 ? "s" : ""} your attention.` : strengths.length ? "Nothing urgent. A few things are going well." : "Nothing urgent to report.";
  const tail = `Alpha found ${risks.length} risk${risks.length === 1 ? "" : "s"} and ${strengths.length} strength${strengths.length === 1 ? "" : "s"}.${health != null ? ` Data health is ${health}.` : ""}`;
  return { title, text: `${lead} ${tail}` };
}

function Money({ m, currency }) {
  if (!m || m.amount == null) return null;
  return <b className="ov-money">{fmtValue(Math.abs(m.amount), "money", currency)}</b>;
}

function FindingRow({ c, id, currency }) {
  const tone = c.tone === "risk" ? "r" : c.tone === "strength" ? "g" : c.tone === "data" ? "r" : "n";
  const label = c.tone === "risk" ? "Risk" : c.tone === "strength" ? "Strength" : c.tone === "data" ? "Data" : "Worth knowing";
  return <Link className={`ov-find ov-${tone}`} to={`/analysis/${id}/suggestions#${c.id}`}>
    <div><span className={`ov-tag t-${tone}`}>{label}</span><strong>{c.headline}</strong>{c.points?.[0] && <small>{c.points[0]}</small>}</div>
    <Money m={c.money} currency={currency}/></Link>;
}

function Ranked({ title, rows, fmt, unit, note }) {
  if (!rows?.length) return null;
  const max = Math.max(...rows.map((r) => r.value), 1);
  return <div className="ov-rank"><h4>{title}</h4>{note && <small>{note}</small>}
    <ol>{rows.map((r) => <li key={r.label}><span>{r.label}</span><b>{fmtValue(r.value, fmt, unit)}</b><i style={{ width: `${Math.max(3, (100 * r.value) / max)}%` }}/></li>)}</ol></div>;
}

export default function OverviewPage({ id, report, view }) {
  const navigate = useNavigate();
  const [q, setQ] = useState("");
  const ov = report.overview;
  const tiles = useMemo(() => allTiles(ov), [ov]);
  const sections = useMemo(() => allSections(ov), [ov]);
  const chart = (cid) => sections.flatMap((s) => s.charts).find((c) => c.id.endsWith(cid));
  const charts = sections.flatMap((s) => s.charts);
  const currency = view.currency;
  const actionIds = new Set((report.briefing?.first_actions || []).slice(0, 3).map((a) => a.insight_id));
  const allRisks = view.cards.filter((c) => c.tone === "risk" || c.tone === "data");
  const risks = allRisks.filter((c) => !actionIds.has(c.insight_id)).length ? allRisks.filter((c) => !actionIds.has(c.insight_id)) : allRisks;
  const strengths = view.cards.filter((c) => c.tone === "strength");
  const health = healthOf(report);
  const snap = snapshot(tiles, view.cards.filter((c) => c.tone === "risk"), strengths, view, health);
  const key = KEY.map((m) => tileBy(tiles, m)).filter(Boolean);
  const keyTiles = key.length >= 3 ? key : tiles.slice(0, 5);
  const notes = [...new Set(keyTiles.map((t) => t.note).filter(Boolean))];
  const aiOn = report.ai?.provider && report.ai.provider !== "none";
  const actions = (report.briefing?.first_actions || []).slice(0, 3);
  const revRaw = charts.find((c) => c.type === "line" && c.metric === "revenue");
  const partial = /not complete/i.test(tileBy(tiles, "revenue")?.note || "");
  const revTime = useMemo(() => {
    if (!revRaw || !partial || !revRaw.grains?.month) return revRaw;
    const g = revRaw.grains.month;
    return { ...revRaw, grains: { ...revRaw.grains, month: { ...g, x: g.x.slice(0, -1), series: g.series.map((x) => ({ ...x, values: x.values.slice(0, -1) })) } } };
  }, [revRaw, partial]);
  const byGroup = charts.filter((c) => c.type === "bar" && c.metric === "revenue" && c.group_col && c.rows?.length > 1).slice(0, 2);
  const prod = charts.find((c) => c.type === "table" && /product/.test(c.id));
  const weekday = chart(":weekday");
  const wd = weekday?.rows?.length === 7 ? weekday.rows : null;
  const best = wd && wd.reduce((a, b) => (b.value > a.value ? b : a)), worst = wd && wd.reduce((a, b) => (b.value < a.value ? b : a));
  const stock = ["out_of_stock", "stock_units", "stock_value"].map((m) => tileBy(tiles, m)).filter(Boolean);
  const holdings = charts.find((c) => c.type === "table" && c.id.startsWith("stock.csv"));
  const goto = (to) => navigate(`/analysis/${id}/${to}`);
  const jump = [
    ["sales", "Sales", tileBy(tiles, "revenue"), "#12976a"], ["customers", "Customers", tileBy(tiles, "customers"), "#d95926"],
    ["products", "Products", tileBy(tiles, "stock_value") || tileBy(tiles, "profit"), "#c98500"], ["trends", "Trends", tileBy(tiles, "orders") || tileBy(tiles, "profit"), "#7a5ad8"],
  ].filter(([, , t]) => t);
  const rows = report.data_check?.rows;
  const tot = rows ? Math.max(1, (rows.ok || 0) + (rows.fixed || 0) + (rows.flagged || 0) + (rows.left_out || 0)) : 1;

  return <div className="ov">
    <section className="ov-snap"><div><h2>{snap.title}</h2><p>{snap.text}</p></div>
      {health != null && <Link to={`/analysis/${id}/quality`} className="ov-score"><b>{health}</b><span>Data health</span></Link>}</section>

    <form className="ov-ask" onSubmit={(e) => { e.preventDefault(); if (q.trim().length >= 3) navigate(`/analysis/${id}/ask?q=${encodeURIComponent(q.trim())}`); }}>
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1.1-4.6A8 8 0 1 1 21 12Z"/></svg>
      <input value={q} maxLength={500} onChange={(e) => setQ(e.target.value)} aria-label="Ask your data" placeholder="Ask your data, for example: which region sells the most?"/>
      <button type="submit" className="primary-button" disabled={q.trim().length < 3}>Ask</button>
      {!aiOn && <small>The AI helper is off, so answers will not work until an AI key is set.</small>}</form>

    {keyTiles.length > 0 && <section><div className="al-tiles ov-tiles">{keyTiles.map((t) => <Tile key={`${t.metric}-${t.source}`} t={t}/>)}</div>
      {notes.length > 0 && <p className="ov-note">{notes.join(" ")} More numbers on the Sales and Customers pages.</p>}</section>}

    <div className="ov-one">
      <section className="ov-card"><div className="ov-card-head"><h3>Do this first</h3><Link to={`/analysis/${id}/suggestions`}>All suggestions →</Link></div>
        {actions.length > 0 ? <ol className="ov-actions">{actions.map((a, i) => <li key={a.insight_id}><i>{i + 1}</i><div><Link to={`/analysis/${id}/suggestions#${a.insight_id}`}>{a.title}</Link><small>{a.action}</small></div>
          {a.impact ? <b className="ov-money">{fmtValue(Math.abs(a.impact), "money", currency)}</b> : null}</li>)}</ol>
          : <p className="al-muted">Nothing needs doing first. No finding passed the checks as a problem to fix.</p>}</section>
    </div>

    <div className="ov-two">
      <section><h3 className="ov-h">Needs attention</h3>{risks.length ? risks.slice(0, 3).map((c) => <FindingRow key={c.id} c={c} id={id} currency={currency}/>) : <p className="al-muted">No risks were found.</p>}</section>
      <section><h3 className="ov-h">Going well</h3>{strengths.length ? strengths.slice(0, 3).map((c) => <FindingRow key={c.id} c={c} id={id} currency={currency}/>) : <p className="al-muted">No clear strengths stood out in this data.</p>}</section>
    </div>

    {revTime && <section><h3 className="ov-h">Revenue over time</h3><Chart spec={revTime}/></section>}

    {(prod || byGroup.length > 0) && <section><h3 className="ov-h">Top performers</h3><div className="ov-ranks">
      {prod && <Ranked title="Top products" fmt="money" unit={currency} rows={prod.rows.slice(0, 5).map((r) => ({ label: r.name || r.key, value: r.Revenue ?? r[prod.columns[0]] }))}/>}
      {byGroup.map((c) => <Ranked key={c.id} title={`Revenue by ${c.group_col}`} fmt="money" unit={currency} rows={[...c.rows].sort((a, b) => b.value - a.value).slice(0, 5).map((r) => ({ label: r.group, value: r.value }))}/>)}
      {prod?.bottom?.length > 0 && <Ranked title="Lowest sellers" note="Products with the least revenue" fmt="money" unit={currency} rows={prod.bottom.slice(0, 5).map((r) => ({ label: r.name || r.key, value: r.Revenue }))}/>}
    </div></section>}

    {(wd || stock.length > 0) && <div className="ov-two">
      {wd && <section className="ov-card"><div className="ov-card-head"><h3>Weekday pattern</h3></div>
        <div className="ov-week">{wd.map((r) => <div key={r.group} className={r.group === best.group ? "best" : r.group === worst.group ? "worst" : ""}><i style={{ height: `${Math.max(8, (100 * r.value) / best.value)}%` }}/><span>{r.group}</span></div>)}</div>
        <small className="al-muted">Best day: <b>{best.group}</b> ({fmtValue(best.value, "money", currency)} a day). Slowest: <b>{worst.group}</b> ({fmtValue(worst.value, "money", currency)}).</small></section>}
      {stock.length > 0 && <section className="ov-card"><div className="ov-card-head"><h3>Stock watch</h3><Link to={`/analysis/${id}/products`}>Products →</Link></div>
        <div className="ov-stock">{stock.map((t) => <div key={t.metric} className={t.metric === "out_of_stock" && t.value > 0 ? "warn" : ""}><strong>{fmtValue(t.value, t.fmt, t.unit)}</strong><span>{t.label}</span></div>)}</div>
        {holdings?.rows?.length > 0 && <small className="al-muted">Largest holdings: {holdings.rows.slice(0, 3).map((r) => r.name || r.key).join(", ")}.</small>}</section>}
    </div>}

    {jump.length > 0 && <section><h3 className="ov-h">Explore by area</h3><div className="ov-jump">
      {jump.map(([to, label, t, color]) => <Link key={to} to={`/analysis/${id}/${to}`}><span>{label}</span><strong>{fmtValue(t.value, t.fmt, t.unit)}</strong><small>{t.label}{t.last_period ? ` · ${change(t.last_period.change, t.fmt)}` : ""}</small><Spark values={t.spark} color={color}/><em>Open {label} →</em></Link>)}</div></section>}

    {rows && <section className="ov-card"><div className="ov-card-head"><h3>Data health</h3><Link to={`/analysis/${id}/quality`}>Open Data Quality →</Link></div>
      <p className="al-muted">{tot.toLocaleString()} rows checked · 27 checks on every file</p>
      <div className="ov-health">{[["ok", "#b9d3c6"], ["fixed", "#5b8def"], ["flagged", "#c98500"], ["left_out", "#46505a"]].map(([k, c]) => rows[k] ? <i key={k} style={{ width: `${(100 * rows[k]) / tot}%`, background: c }}/> : null)}</div>
      <small className="al-muted">Fine {(rows.ok || 0).toLocaleString()} · Cleaned {(rows.fixed || 0).toLocaleString()} · Flagged {(rows.flagged || 0).toLocaleString()} · Left out {(rows.left_out || 0).toLocaleString()}</small></section>}

    {(view.f.cannot_tell || []).length > 0 && <section className="ov-card al-caveat"><h3>What the data cannot tell you</h3><ul className="al-plain">{view.f.cannot_tell.map((c, i) => <li key={i}>{c}</li>)}</ul></section>}
    {report.limits && <details className="ov-card ov-how"><summary>How to read this</summary><ul className="al-plain al-muted">{report.limits.map((l) => <li key={l}>{l}</li>)}
      <li>Each finding says how sure it is: Calculated (plain arithmetic on your rows), Supported by evidence (holds up against chance), or Possible (an early sign). None claims a cause.</li></ul></details>}
  </div>;
}
