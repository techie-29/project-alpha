import { BarsSvg, LineSvg, RingSvg } from "./Charts";

const GRADE = { good: "close", fair: "reasonably close", weak: "rough" };

/** One slide, drawn at a fixed 1280 x 720 size. The player scales it to the screen. */
export default function Slide({ s, index, total }) {
  const foot = <div className="dk-foot"><span>{s.biz || ""}</span><span>{index + 1} / {total}</span></div>;
  switch (s.kind) {
    case "title": return <div className="dk-slide dk-title">
      <div className="dk-title-bar"/><div><h1>{s.title}</h1>{s.subtitle && <p className="dk-sub">{s.subtitle}</p>}{s.presenter && <p className="dk-by">Presented by {s.presenter}</p>}</div></div>;
    case "snapshot": return <div className="dk-slide"><h2>{s.title}</h2>
      <div className="dk-figs">{s.figures.map((f) => <div key={f.label} className="dk-fig"><span>{f.label}</span><b>{f.value}</b>{f.change && <small className={`dk-${f.tone}`}>{f.tone === "flat" ? "•" : f.change.startsWith("-") || f.change.startsWith("−") ? "▼" : "▲"} {f.change}</small>}</div>)}</div>
      <div className="dk-rings">{s.business && <RingSvg value={s.business.score} label={`business health: ${s.business.label.toLowerCase()}`}/>}{s.data != null && <RingSvg value={s.data} label="data health: how clean the files are"/>}</div>{foot}</div>;
    case "sales": return <div className="dk-slide"><h2>{s.title}</h2><div className="dk-chart"><LineSvg {...s.line} h={400}/></div><p className="dk-cap">{s.caption}</p>{foot}</div>;
    case "risk": return <div className="dk-slide dk-risk">
      <div className="dk-left"><span className="dk-badge">Problem {s.n}</span><h2>{s.title}</h2>
        {s.money && <p className="dk-money"><b>{s.money}</b> involved</p>}
        {s.point && <p className="dk-point">{s.point}</p>}
        {s.action && <div className="dk-do"><strong>What to do</strong><p>{s.action}</p></div>}</div>
      {s.chart && <div className="dk-right"><p className="dk-ct">{s.chart.title}</p><BarsSvg rows={s.chart.rows} fmt={s.chart.fmt} unit={s.chart.unit} focus={s.chart.focus}/></div>}{s.table && <div className="dk-right"><p className="dk-ct">{s.table.title}</p><table className="dk-tbl"><thead><tr>{s.table.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead><tbody>{s.table.rows.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j}>{v}</td>)}</tr>)}</tbody></table></div>}{foot}</div>;
    case "good": return <div className="dk-slide"><h2>{s.title}</h2><div className="dk-cards">{s.items.map((it, i) => <div key={i} className="dk-card"><h3>{it.headline}</h3><p>{it.point}</p></div>)}</div>{foot}</div>;
    case "forecast": return <div className="dk-slide dk-fc"><div className="dk-left2"><h2>{s.title}</h2><div className="dk-chart"><LineSvg {...s.line} forecast={s.forecast} w={760} h={400}/></div></div>
      <div className="dk-right2"><span className="dk-badge">estimate</span><p className="dk-big">{s.total.mid}</p><p className="dk-point">most likely over three months. Likely between {s.total.low} and {s.total.high}.</p>
        <div className="dk-do"><strong>How far to trust it</strong><p>{s.trust ? `Tested on your last 3 months: off by about ${s.trust.error}% a month (${GRADE[s.trust.grade]}).` : s.untested}</p></div></div>{foot}</div>;
    case "actions": return <div className="dk-slide"><h2>{s.title}</h2><ol className="dk-actions">{s.items.map((a, i) => <li key={i}><i>{i + 1}</i><div><strong>{a.title}</strong><p>{a.action}</p></div>{a.impact && <b>{a.impact}</b>}</li>)}</ol>{foot}</div>;
    case "quality": { const r = s.rows, t = s.total || 1; const seg = [["ok", "Fine", r.ok], ["fixed", "Cleaned", r.fixed], ["flagged", "Flagged", r.flagged], ["left", "Left out", r.left_out]];
      return <div className="dk-slide dk-q"><h2>{s.title}</h2><div className="dk-qrow">{s.health != null && <RingSvg value={s.health} label="data health" size={200}/>}
        <div className="dk-qbars"><div className="dk-stack">{seg.map(([k, , v]) => <i key={k} className={`dk-s-${k}`} style={{ flex: Math.max(v, 0) / t || 0 }}/>)}</div>
          <ul>{seg.map(([k, l, v]) => <li key={k}><i className={`dk-s-${k}`}/><span>{l}</span><b>{(v || 0).toLocaleString()}</b></li>)}</ul><p className="dk-cap">{s.headline}</p></div></div>{foot}</div>; }
    case "close": return <div className="dk-slide dk-close"><h2>{s.title}</h2><ul className="dk-bul">{s.bullets.map((b, i) => <li key={i}>{b}</li>)}</ul>
      <p className="dk-thanks">Thank you{s.presenter ? `. ${s.presenter}` : ""}</p>{foot}</div>;
    default: return null;
  }
}
