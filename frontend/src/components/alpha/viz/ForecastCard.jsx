import { fmtValue } from "../../../utils/alphaFormat";

const GRADE = { good: ["close", "g"], fair: ["reasonably close", "m"], weak: ["rough", "w"] };

/** The forecast in plain words, with the test of how well the same method predicted the owner's own recent months. */
export default function ForecastCard({ forecast: f, fmt = "number", unit = ""}) {
  if (!f) return null;
  const money = (v) => fmtValue(v, fmt, unit);
  if (f.status !== "ok") return <p className="fc-none">{f.reason}</p>;
  const bt = f.backtest;
  const grade = bt && GRADE[bt.grade];
  return <div className="fc">
    <div className="fc-head">
      <h4>Next 3 months <span className="fc-tag">estimate</span></h4>
      <p>About <b>{money(f.total.mid)}</b> in total. Most likely between <b>{money(f.total.low)}</b> and <b>{money(f.total.high)}</b>.</p>
    </div>
    <table className="fc-table"><thead><tr><th>Month</th><th>Most likely</th><th>Low case</th><th>High case</th></tr></thead>
      <tbody>{f.x.map((x, i) => <tr key={x}><td>{x}</td><td><b>{money(f.mid[i])}</b></td><td>{money(f.low[i])}</td><td>{money(f.high[i])}</td></tr>)}</tbody></table>
    {bt ? <div className={`fc-test fc-${grade[1]}`}>
      <strong>How far to trust it</strong>
      <p>We hid your last 3 months ({bt.months[0]} to {bt.months[bt.months.length - 1]}), predicted them from what came before, and compared. The predictions were off by about <b>{Math.round(bt.error * 100)}%</b> a month: {grade[0]}.</p>
      <table className="fc-table"><thead><tr><th>Month</th><th>Predicted</th><th>What happened</th></tr></thead>
        <tbody>{bt.months.map((m, i) => <tr key={m}><td>{m}</td><td>{money(bt.predicted[i])}</td><td>{money(bt.actual[i])}</td></tr>)}</tbody></table>
    </div> : <p className="fc-untested">{f.untested}</p>}
    <p className="fc-how">{f.method}, using {f.history_months} complete months. It cannot know about a new shop, a price change or a festival you have not had before.</p>
  </div>;
}
