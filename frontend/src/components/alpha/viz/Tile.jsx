import { Area, AreaChart, ResponsiveContainer } from "recharts";
import { BAD, DEEMPH, GOOD } from "./theme";
import { change, fmtValue } from "../../../utils/alphaFormat";

function Delta({ c, fmt, polarity, label }) {
  const text = change(c, fmt);
  if (!text) return null;
  const up = c > 0, flat = Math.abs(c) < 1e-9;
  const good = polarity ? (polarity > 0) === up : null;
  const color = flat || good === null ? "#c3c2b7" : good ? GOOD : BAD;
  return <span className="al-delta" style={{ color }}><b aria-hidden="true">{flat ? "•" : up ? "▲" : "▼"}</b> {text} <i>{label}</i>{good !== null && !flat && <span className="al-sr">{good ? " (better)" : " (worse)"}</span>}</span>;
}

export default function Tile({ t }) {
  const spark = (t.spark || []).map((v, i) => ({ i, v }));
  return <div className="al-tile" title={t.how}>
    <span className="al-tile-label">{t.label}</span>
    <strong className="al-tile-value">{fmtValue(t.value, t.fmt, t.unit)}</strong>
    {t.last_period && <Delta c={t.last_period.change} fmt={t.fmt} polarity={t.polarity} label={`${t.last_period.label} vs ${t.last_period.previous_label}`}/>}
    {t.vs_last_year && <Delta c={t.vs_last_year.change} fmt={t.fmt} polarity={t.polarity} label={`vs ${t.vs_last_year.label}`}/>}
    {spark.length > 2 && <div className="al-spark" aria-hidden="true"><ResponsiveContainer><AreaChart data={spark} margin={{ top: 2, right: 0, left: 0, bottom: 0 }}>
      <Area type="monotone" dataKey="v" stroke="#3987e5" strokeWidth={1.5} fill="#3987e5" fillOpacity={0.1} dot={false} isAnimationActive={false} connectNulls/>
    </AreaChart></ResponsiveContainer></div>}

  </div>;
}
export { DEEMPH };
