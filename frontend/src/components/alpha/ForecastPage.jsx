import Chart from "./viz/Chart";
import { allSections } from "./AreaPage";
import { fmtValue } from "../../utils/alphaFormat";

const GRADE = { good: "close", fair: "reasonably close", weak: "rough" };

/** The forecast on its own page: for each measure that can be forecast, the headline, the chart, and how far to trust it. */
export default function ForecastPage({ report }) {
  const charts = allSections(report.overview).flatMap((s) => s.charts.map((c) => ({ ...c, _part: s.part })))
    .filter((c) => c.type === "line" && c.forecast);
  const ok = charts.filter((c) => c.forecast.status === "ok");
  const none = charts.filter((c) => c.forecast.status !== "ok");
  if (!charts.length) return <div className="al-panel fc-empty"><h3>No forecast for this analysis</h3>
    <p>Alpha forecasts revenue and orders month by month. It needs dates in your files, at least 5 months of history and 6 complete months of sales.</p>
    <p className="al-muted">If your data is long enough, this analysis was probably made before forecasting existed. Run it again and the forecast will appear here.</p></div>;
  return <div className="fcp">
    <p className="al-muted">An estimate from your own history: the trend plus your usual seasonal pattern. It is tested against your last 3 months so you can see how far to trust it. It is not a promise.</p>
    {ok.map((c) => {
      const f = c.forecast, bt = f.backtest, money = (v) => fmtValue(v, c.fmt, c.unit);
      return <section key={c.id} className="fcp-sec">
        <header className="fcp-head">
          <div><span className="fcp-k">{c.title.replace(/ over time$/i, "")}{c._part ? ` · ${c._part}` : ""}</span>
            <h3>About {money(f.total.mid)} over the next 3 months</h3>
            <p>Most likely between {money(f.total.low)} and {money(f.total.high)}.</p></div>
          {bt ? <span className={`fcp-trust fcp-${bt.grade}`}>{bt.grade === "good" ? "Reliable" : bt.grade === "fair" ? "Fairly reliable" : "Rough"}<small>off by about {Math.round(bt.error * 100)}% a month in the test ({GRADE[bt.grade]})</small></span>
            : <span className="fcp-trust fcp-none">Not tested<small>too little history to test it</small></span>}
        </header>
        <Chart spec={{ ...c, default_grain: "month" }}/>
      </section>;
    })}
    {none.map((c) => <section key={c.id} className="fcp-sec fcp-off"><h3>{c.title.replace(/ over time$/i, "")}: no forecast</h3><p className="al-muted">{c.forecast.reason}</p></section>)}
  </div>;
}
