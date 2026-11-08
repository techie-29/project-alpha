import { axisFmt, fmtValue } from "../../../utils/alphaFormat";

/** Small SVG charts for slides. They scale with the slide, need no measuring, and print cleanly. */
export function LineSvg({ x, y, fmt = "number", unit = "", forecast = null, w = 1000, h = 360 }) {
  const pad = { l: 72, r: 24, t: 18, b: 44 };
  const fx = forecast ? forecast.x : [];
  const labels = [...x, ...fx];
  const vals = [...y, ...(forecast ? [...forecast.low, ...forecast.high, ...forecast.mid] : [])].filter(Number.isFinite);
  const max = Math.max(...vals) * 1.08, min = Math.min(0, ...vals);
  const X = (i) => pad.l + (i / Math.max(1, labels.length - 1)) * (w - pad.l - pad.r);
  const Y = (v) => pad.t + (1 - (v - min) / (max - min || 1)) * (h - pad.t - pad.b);
  const path = (arr, off = 0) => arr.map((v, i) => `${i ? "L" : "M"}${X(i + off).toFixed(1)},${Y(v).toFixed(1)}`).join("");
  const ticks = [0, 1, 2, 3, 4].map((k) => min + ((max - min) * k) / 4);
  const every = Math.ceil(labels.length / 8);
  const joint = forecast ? [y[y.length - 1], ...forecast.mid] : [];
  const band = forecast ? [[y[y.length - 1], y[y.length - 1]], ...forecast.low.map((l, i) => [l, forecast.high[i]])] : [];
  return <svg viewBox={`0 0 ${w} ${h}`} role="img" className="dk-svg">
    {ticks.map((t, i) => <g key={i}><line x1={pad.l} x2={w - pad.r} y1={Y(t)} y2={Y(t)} className="dk-grid"/><text x={pad.l - 10} y={Y(t) + 5} textAnchor="end" className="dk-tick">{axisFmt(fmt)(t)}</text></g>)}
    <path d={`${path(y)}L${X(y.length - 1)},${Y(min)}L${X(0)},${Y(min)}Z`} className="dk-area"/>
    <path d={path(y)} className="dk-line"/>
    {forecast && <>
      <path d={`${band.map(([lo], i) => `${i ? "L" : "M"}${X(y.length - 1 + i).toFixed(1)},${Y(lo).toFixed(1)}`).join("")}${[...band].reverse().map(([, hi], i) => `L${X(y.length - 1 + band.length - 1 - i).toFixed(1)},${Y(hi).toFixed(1)}`).join("")}Z`} className="dk-band"/>
      <path d={joint.map((v, i) => `${i ? "L" : "M"}${X(y.length - 1 + i).toFixed(1)},${Y(v).toFixed(1)}`).join("")} className="dk-line dk-dash"/>
    </>}
    {labels.map((l, i) => ((i % every === 0 && labels.length - 1 - i >= every) || i === labels.length - 1) && <text key={i} x={X(i)} y={h - 14} textAnchor={i === labels.length - 1 && labels.length > 3 ? "end" : "middle"} className="dk-tick">{l}</text>)}
    <circle cx={X(y.length - 1)} cy={Y(y[y.length - 1])} r="6" className="dk-dot"/>
    <title>{unit}</title>
  </svg>;
}

export function BarsSvg({ rows, fmt = "number", unit = "", focus = null, w = 560 }) {
  const max = Math.max(...rows.map((r) => r.value)) || 1;
  const row = 56, h = rows.length * row + 8, label = 190, val = 96;
  return <svg viewBox={`0 0 ${w} ${h}`} role="img" className="dk-svg">
    {rows.map((r, i) => { const on = focus ? String(r.group) === String(focus) : i === 0; const bw = Math.max(3, ((r.value / max) * (w - label - val)));
      return <g key={r.group} transform={`translate(0 ${i * row + 4})`}>
        <text x="0" y="26" className={`dk-bar-label${on ? " on" : ""}`}>{String(r.group).slice(0, 20)}</text>
        <rect x={label} y="8" width={bw} height="26" rx="5" className={on ? "dk-bar on" : "dk-bar"}/>
        <text x={label + bw + 10} y="28" className={`dk-bar-val${on ? " on" : ""}`}>{fmtValue(r.value, fmt, unit)}</text>
      </g>; })}
  </svg>;
}

export function RingSvg({ value, label, size = 150 }) {
  const c = 2 * Math.PI * 19;
  return <div className="dk-ring" style={{ width: size, "--s": `${size}px` }}>
    <svg viewBox="0 0 44 44" width={size} height={size} aria-hidden="true"><circle cx="22" cy="22" r="19" className="dk-ring-bg"/><circle cx="22" cy="22" r="19" className="dk-ring-fg" strokeDasharray={`${(value / 100) * c} ${c}`} transform="rotate(-90 22 22)"/></svg>
    <b>{value}</b><span>{label}</span>
  </div>;
}
