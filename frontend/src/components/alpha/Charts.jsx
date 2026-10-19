import { Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { num } from "../../utils/alphaFormat";

const AXIS = { fill: "#74818b", fontSize: 10 };

export function TrendChart({ labels = [], values = [], focus = null, unit = "", height = 220 }) {
  const data = labels.map((label, i) => ({ label, value: values[i] }));
  return <div className="al-chart" style={{ height }} role="img" aria-label="Trend over time">
    <ResponsiveContainer>
      <LineChart data={data} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
        <CartesianGrid stroke="#1c2730" vertical={false}/>
        <XAxis dataKey="label" tick={AXIS} minTickGap={48} tickLine={false}/>
        <YAxis tick={AXIS} width={52} tickFormatter={(v) => num(v)} tickLine={false} axisLine={false}/>
        <Tooltip contentStyle={{ background: "#0e1319", border: "1px solid #32404d", fontSize: 12 }} formatter={(v) => [`${unit} ${num(v)}`.trim(), ""]} separator=""/>
        {focus && labels[focus[0]] !== undefined && <ReferenceArea x1={labels[focus[0]]} x2={labels[Math.min(focus[1], labels.length - 1)]} fill="#57e7b0" fillOpacity={0.16} stroke="#57e7b0" strokeOpacity={0.4}/>}
        <Line type="monotone" dataKey="value" stroke="#57e7b0" strokeWidth={1.8} dot={false} connectNulls/>
      </LineChart>
    </ResponsiveContainer>
  </div>;
}

export function Spark({ values = [], height = 36 }) {
  const data = values.map((v, i) => ({ i, v }));
  if (data.length < 3) return null;
  return <div className="al-spark" style={{ height }} aria-hidden="true"><ResponsiveContainer><AreaChart data={data} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
    <Area type="monotone" dataKey="v" stroke="#57e7b0" strokeWidth={1.4} fill="#57e7b0" fillOpacity={0.12} dot={false} isAnimationActive={false} connectNulls/>
  </AreaChart></ResponsiveContainer></div>;
}

export function BarList({ labels = [], values = [], unit = "", height = 180 }) {
  const data = labels.map((label, i) => ({ label, value: values[i] }));
  return <div className="al-chart" style={{ height }} role="img" aria-label="Comparison by group">
    <ResponsiveContainer><BarChart data={data} margin={{ top: 6, right: 8, left: 0, bottom: 0 }}>
      <CartesianGrid stroke="#1c2730" vertical={false}/>
      <XAxis dataKey="label" tick={AXIS} tickLine={false}/>
      <YAxis tick={AXIS} width={52} tickFormatter={(v) => num(v)} tickLine={false} axisLine={false}/>
      <Tooltip contentStyle={{ background: "#0e1319", border: "1px solid #32404d", fontSize: 12 }} formatter={(v) => [`${unit} ${num(v)}`.trim(), ""]} separator="" cursor={{ fill: "#ffffff10" }}/>
      <Bar dataKey="value" fill="#57e7b0" fillOpacity={0.75} radius={[3, 3, 0, 0]}/>
    </BarChart></ResponsiveContainer>
  </div>;
}
