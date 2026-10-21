import { useMemo, useState } from "react";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Cell, Legend, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { AXIS, DEEMPH, EMPHASIS, GRID, INK2, SERIES, tick, tooltipStyle } from "./theme";
import { axisFmt, cellText, fmtValue } from "../../../utils/alphaFormat";

const GRAIN_LABEL = { day: "Day", week: "Week", month: "Month", quarter: "Quarter", year: "Year" };

function DataTable({ head, rows }) {
  return <div className="al-table-wrap"><table className="al-table al-compact"><thead><tr>{head.map((h) => <th key={h}>{h}</th>)}</tr></thead>
    <tbody>{rows.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j}>{v}</td>)}</tr>)}</tbody></table></div>;
}

function Frame({ title, note, controls, children, table, height }) {
  const [asTable, setAsTable] = useState(false);
  return <figure className="al-fig">
    <figcaption className="al-fig-head">
      <span>{title}</span>
      <span className="al-fig-tools">{controls}{table && <button type="button" className="al-mini" onClick={() => setAsTable(!asTable)}>{asTable ? "Chart" : "Table"}</button>}</span>
    </figcaption>
    {asTable && table ? table : <div style={{ height }}>{children}</div>}
    {note && <p className="al-muted">{note}</p>}
  </figure>;
}

function TimeLine({ spec, compactView }) {
  const grains = spec.grains || null;
  const [grain, setGrain] = useState(spec.default_grain || (grains ? Object.keys(grains)[0] : null));
  const g = grains ? grains[grain] : { x: spec.x, series: [{ name: spec.title, values: spec.values }] };
  const data = useMemo(() => g.x.map((x, i) => Object.fromEntries([["x", x], ...g.series.map((s) => [s.name, s.values[i]])])), [g]);
  const fmt = spec.fmt || "number";
  const fr = spec.focus_range;
  const controls = grains && Object.keys(grains).length > 1 ? <span className="al-seg">{Object.keys(grains).map((k) => <button type="button" key={k} className={k === grain ? "is-on" : ""} onClick={() => setGrain(k)}>{GRAIN_LABEL[k]}</button>)}</span> : null;
  return <Frame title={spec.title + (spec.unit ? ` (${spec.unit})` : "")} controls={controls} height={compactView ? 180 : 240} note={spec.note}
    table={<DataTable head={["Period", ...g.series.map((s) => s.name)]} rows={g.x.map((x, i) => [x, ...g.series.map((s) => fmtValue(s.values[i], fmt, spec.unit))])}/>}>
    <ResponsiveContainer>
      <LineChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false}/>
        <XAxis dataKey="x" tick={tick} minTickGap={40} tickLine={false} axisLine={{ stroke: GRID }}/>
        <YAxis tick={tick} width={56} tickFormatter={axisFmt(fmt)} tickLine={false} axisLine={false}/>
        <Tooltip contentStyle={tooltipStyle} formatter={(v, n) => [fmtValue(v, fmt, spec.unit), n]} cursor={{ stroke: AXIS, strokeWidth: 1 }}/>
        {fr && data[fr[0]] && <ReferenceArea x1={data[fr[0]].x} x2={data[Math.min(fr[1], data.length - 1)].x} fill={EMPHASIS} fillOpacity={0.12} stroke="none"/>}
        {g.series.map((s, i) => <Line key={s.name} type="monotone" dataKey={s.name} stroke={SERIES[i % SERIES.length]} strokeWidth={2} dot={false} activeDot={{ r: 4, stroke: "#0e1319", strokeWidth: 2 }} connectNulls/>)}
        {g.series.length > 1 && <Legend wrapperStyle={{ fontSize: 12, color: INK2 }}/>}
      </LineChart>
    </ResponsiveContainer>
  </Frame>;
}

function Bars({ spec, compactView }) {
  const rows = (spec.rows || []).filter((r) => r.value !== null && r.value !== undefined);
  const fmt = spec.fmt || "number";
  const horizontal = !spec.keep_order && (rows.length > 6 || rows.some((r) => String(r.group).length > 10));
  const data = rows.map((r) => ({ ...r, group: String(r.group) }));
  const height = horizontal ? Math.max(120, 28 * data.length + 30) : (compactView ? 180 : 220);
  const focus = spec.focus;
  const table = <DataTable head={["Group", "Value", ...(rows.some((r) => r.share != null) ? ["Share"] : []), ...(rows.some((r) => r.rows != null) ? ["Rows"] : [])]}
    rows={rows.map((r) => [r.group, fmtValue(r.value, fmt, spec.unit), ...(rows.some((x) => x.share != null) ? [r.share != null ? `${(r.share * 100).toFixed(1)}%` : ""] : []), ...(rows.some((x) => x.rows != null) ? [r.rows?.toLocaleString() ?? ""] : [])])}/>;
  return <Frame title={spec.title + (spec.unit ? ` (${spec.unit})` : "")} height={height} table={table} note={spec.note}>
    <ResponsiveContainer>
      {horizontal
        ? <BarChart data={data} layout="vertical" margin={{ top: 4, right: 56, left: 8, bottom: 0 }} barCategoryGap={6}>
            <CartesianGrid stroke={GRID} horizontal={false}/>
            <XAxis type="number" tick={tick} tickFormatter={axisFmt(fmt)} axisLine={false} tickLine={false} domain={[(d) => Math.min(0, d), "auto"]}/>
            <YAxis type="category" dataKey="group" tick={{ ...tick, fill: INK2 }} width={130} tickLine={false} axisLine={{ stroke: GRID }}/>
            <Tooltip contentStyle={tooltipStyle} formatter={(v) => [fmtValue(v, fmt, spec.unit), spec.metric_label || "Value"]} cursor={{ fill: "#ffffff08" }}/>
            <Bar dataKey="value" maxBarSize={20} radius={[0, 4, 4, 0]} label={{ position: "right", fill: INK2, fontSize: 11, formatter: (v) => fmtValue(v, fmt) }}>
              {data.map((r) => <Cell key={r.group} fill={focus ? (r.group === focus ? EMPHASIS : DEEMPH) : (r.other ? DEEMPH : EMPHASIS)}/>)}
            </Bar>
          </BarChart>
        : <BarChart data={data} margin={{ top: 16, right: 8, left: 0, bottom: 0 }} barCategoryGap="20%">
            <CartesianGrid stroke={GRID} vertical={false}/>
            <XAxis dataKey="group" tick={tick} tickLine={false} axisLine={{ stroke: GRID }} interval={data.length > 14 ? "preserveStartEnd" : 0} minTickGap={4}/>
            <YAxis tick={tick} width={52} tickFormatter={axisFmt(fmt)} tickLine={false} axisLine={false}/>
            <Tooltip contentStyle={tooltipStyle} formatter={(v) => [fmtValue(v, fmt, spec.unit), "Value"]} cursor={{ fill: "#ffffff08" }}/>
            <Bar dataKey="value" maxBarSize={24} radius={[4, 4, 0, 0]}>
              {data.map((r) => <Cell key={r.group} fill={focus ? (r.group === focus ? EMPHASIS : DEEMPH) : EMPHASIS}/>)}
            </Bar>
          </BarChart>}
    </ResponsiveContainer>
  </Frame>;
}

function Stacked({ spec, counts }) {
  const series = spec.series || [];
  const data = spec.x.map((x, i) => Object.fromEntries([["x", x], ...series.map((s) => [s.name, s.values[i]])]));
  const fmt = counts ? "count" : "pct";
  const table = <DataTable head={["Period", ...series.map((s) => s.name)]} rows={spec.x.map((x, i) => [x, ...series.map((s) => fmtValue(s.values[i], fmt))])}/>;
  return <Frame title={spec.title} height={260} table={table} note={spec.note}>
    <ResponsiveContainer>
      {counts
        ? <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }} barCategoryGap={2}>
            <CartesianGrid stroke={GRID} vertical={false}/>
            <XAxis dataKey="x" tick={tick} minTickGap={40} tickLine={false} axisLine={{ stroke: GRID }}/>
            <YAxis tick={tick} width={52} tickFormatter={axisFmt("count")} tickLine={false} axisLine={false}/>
            <Tooltip contentStyle={tooltipStyle} formatter={(v, n) => [fmtValue(v, "count"), n]} cursor={{ fill: "#ffffff08" }}/>
            <Legend wrapperStyle={{ fontSize: 12, color: INK2 }}/>
            {series.map((s, i) => <Bar key={s.name} dataKey={s.name} stackId="a" fill={SERIES[i]} stroke="#0e1319" strokeWidth={1}/>)}
          </BarChart>
        : <AreaChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
            <CartesianGrid stroke={GRID} vertical={false}/>
            <XAxis dataKey="x" tick={tick} minTickGap={40} tickLine={false} axisLine={{ stroke: GRID }}/>
            <YAxis tick={tick} width={44} tickFormatter={axisFmt("pct")} domain={[0, 1]} tickLine={false} axisLine={false}/>
            <Tooltip contentStyle={tooltipStyle} formatter={(v, n) => [fmtValue(v, "pct"), n]}/>
            <Legend wrapperStyle={{ fontSize: 12, color: INK2 }}/>
            {series.map((s, i) => <Area key={s.name} type="monotone" dataKey={s.name} stackId="a" stroke={SERIES[i % SERIES.length]} strokeWidth={s.name === spec.focus ? 2.5 : 1.2} fill={SERIES[i % SERIES.length]} fillOpacity={s.name === spec.focus || !spec.focus ? 0.35 : 0.12}/>)}
          </AreaChart>}
    </ResponsiveContainer>
  </Frame>;
}

function Pareto({ spec }) {
  const data = spec.points.map((p) => ({ x: Math.round(p.x * 100), y: p.y }));
  return <Frame title={spec.title} height={220} table={<DataTable head={["Top % of them", "Share of revenue"]} rows={data.map((d) => [`${d.x}%`, `${(d.y * 100).toFixed(1)}%`])}/>}>
    <ResponsiveContainer>
      <AreaChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 0 }}>
        <CartesianGrid stroke={GRID} vertical={false}/>
        <XAxis dataKey="x" tick={tick} tickFormatter={(v) => `${v}%`} tickLine={false} axisLine={{ stroke: GRID }}/>
        <YAxis tick={tick} width={44} domain={[0, 1]} tickFormatter={axisFmt("pct")} tickLine={false} axisLine={false}/>
        <Tooltip contentStyle={tooltipStyle} formatter={(v) => [`${(v * 100).toFixed(1)}%`, "Share of revenue"]} labelFormatter={(l) => `Top ${l}%`}/>
        <Area type="monotone" dataKey="y" stroke={EMPHASIS} strokeWidth={2} fill={EMPHASIS} fillOpacity={0.1}/>
      </AreaChart>
    </ResponsiveContainer>
  </Frame>;
}

function RankTable({ spec }) {
  const cols = spec.columns || [];
  const fmts = spec.fmts || {};
  const rows = spec.rows || [];
  const main = cols[0];
  const max = Math.max(...rows.map((r) => Math.abs(r[main] || 0)), 1);
  return <figure className="al-fig">
    <figcaption className="al-fig-head"><span>{spec.title}{spec.count ? ` (top ${rows.length} of ${spec.count.toLocaleString()})` : ""}</span></figcaption>
    <div className="al-table-wrap"><table className="al-table al-compact">
      <thead><tr><th>#</th><th>Name</th>{cols.map((c) => <th key={c}>{c}</th>)}{rows.some((r) => r.share != null) && <th>Share</th>}</tr></thead>
      <tbody>{rows.map((r, i) => <tr key={r.key || i}>
        <td className="al-num">{i + 1}</td>
        <td>{r.name ? <><strong>{r.name}</strong> <span className="al-muted">{r.key}</span></> : r.key}</td>
        {cols.map((c, j) => <td key={c} className="al-num">{j === 0 && <span className="al-bar"><i style={{ width: `${(Math.abs(r[c] || 0) / max) * 100}%` }}/></span>}{fmtValue(r[c], fmts[c] || "number", fmts[c] === "money" ? spec.unit : "")}</td>)}
        {rows.some((x) => x.share != null) && <td className="al-num">{r.share != null ? `${(r.share * 100).toFixed(1)}%` : ""}</td>}
      </tr>)}</tbody></table></div>
    {spec.bottom?.length > 0 && <p className="al-muted">Smallest: {spec.bottom.map((b) => `${b.name || b.key} (${fmtValue(b[main], fmts[main] || "number", spec.unit)})`).join(", ")}</p>}
  </figure>;
}

export function Histogram({ spec }) {
  const s = spec.stats || {};
  const note = s.median != null ? `Middle value ${fmtValue(s.median, spec.fmt === "count" ? "number" : spec.fmt)}; most values between ${fmtValue(s.p10)} and ${fmtValue(s.p90)}.` :
    s.repeat_rate != null ? `${(s.repeat_rate * 100).toFixed(0)}% of ${s.customers.toLocaleString()} customers bought more than once.` : null;
  return <Bars spec={{ ...spec, keep_order: true, fmt: "count", note }}/>;
}

export default function Chart({ spec, compactView }) {
  if (!spec) return null;
  switch (spec.type) {
    case "line": return <TimeLine spec={spec} compactView={compactView}/>;
    case "bar": case "binned": return <Bars spec={spec} compactView={compactView}/>;
    case "histogram": return <Histogram spec={spec}/>;
    case "stacked": return <Stacked spec={spec}/>;
    case "stacked_count": return <Stacked spec={spec} counts/>;
    case "pareto": return <Pareto spec={spec}/>;
    case "table": return <RankTable spec={spec}/>;
    default: return null;
  }
}

export function RowsTable({ evidence }) {
  if (!evidence?.rows?.length) return null;
  return <div className="al-block">
    <h4>The rows behind this <span className="al-muted">({evidence.total?.toLocaleString()} in total, showing {evidence.rows.length})</span></h4>
    <div className="al-table-wrap"><table className="al-table al-compact">
      <thead><tr>{evidence.columns.map((c) => <th key={c}>{c.replaceAll("_", " ")}</th>)}</tr></thead>
      <tbody>{evidence.rows.map((r, i) => <tr key={i}>{r.map((v, j) => <td key={j}>{cellText(v)}</td>)}</tr>)}</tbody>
    </table></div>
    <p className="al-muted">From {evidence.file}. "Source row" is the row number in that file.</p>
  </div>;
}
