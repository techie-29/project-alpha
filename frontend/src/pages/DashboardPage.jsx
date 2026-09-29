import { useEffect, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getAnalytics } from "../services/analyticsApi";
import AnalyticsFilters from "../components/analytics/AnalyticsFilters";
import KpiCard from "../components/analytics/KpiCard";
import TraceabilityDrawer from "../components/analytics/TraceabilityDrawer";
import { formatMoney, formatNumber, formatPercent, titleCase } from "../utils/formatters";

const tooltipStyle = { background: "#0d141b", border: "1px solid #263541", borderRadius: 8, fontSize: 11 };

function Provenance({ datasets }) {
  return <section className="analytics-card provenance-card">
    <div className="analytics-card-heading"><div><span className="eyebrow">Input provenance</span><h2>What produced these results</h2></div><span>{datasets.length} included dataset{datasets.length === 1 ? "" : "s"}</span></div>
    {datasets.length ? <div className="provenance-grid">{datasets.map((dataset) => <article key={dataset.id}>
      <div><strong>{dataset.filename}</strong><span className="dataset-type">{dataset.datasetType}</span></div>
      <dl><div><dt>Rows</dt><dd>{formatNumber(dataset.rowsProcessed ?? dataset.rowsUploaded)}</dd></div><div><dt>Quality</dt><dd>{dataset.qualityScore === null ? "—" : `${dataset.qualityScore}/100`}</dd></div><div><dt>Mapping</dt><dd>{formatPercent(dataset.mappingCoverage)}</dd></div><div><dt>Date coverage</dt><dd>{dataset.dateFrom && dataset.dateTo ? `${String(dataset.dateFrom).slice(0, 10)} – ${String(dataset.dateTo).slice(0, 10)}` : "Not available"}</dd></div></dl>
      {dataset.missingCriticalFields?.length > 0 && <p>Missing: {dataset.missingCriticalFields.join(", ")}</p>}
    </article>)}</div> : <div className="analytics-empty">No analytics-ready datasets are included. Complete a transformation or include a dataset from the library.</div>}
  </section>;
}

export default function DashboardPage({ token }) {
  const [filters, setFilters] = useState({ preset: "monthly", datasetId: "" });
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [traceMetric, setTraceMetric] = useState(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    setLoading(true); setError("");
    getAnalytics("overview", filters, token).then((response) => active && setData(response.data)).catch((requestError) => active && setError(requestError.message)).finally(() => active && setLoading(false));
    return () => { active = false; };
  }, [filters, token]);

  const kpis = data?.kpis || {};
  return <div className="page-content analytics-page">
    <section className="page-header analytics-title"><div><span className="eyebrow">Executive dashboard</span><h1>Business performance</h1><p>Verified metrics from normalized records. Select revenue, units, or stock to inspect the source chain.</p></div><AnalyticsFilters filters={filters} onChange={setFilters} datasets={data?.provenance || []}/></section>
    {error && <div className="analytics-error">{error}</div>}
    {loading && <div className="analytics-loading"><span className="spinner"/>Calculating analytics…</div>}
    {data && <>
      <Provenance datasets={data.provenance || []}/>
      <section className="kpi-grid">
        <KpiCard label="Revenue" metric={kpis.revenue} kind="money" onTrace={() => setTraceMetric("revenue")} detail={kpis.revenue?.available ? `${formatMoney(kpis.revenue.dailyAverage)} daily · best ${kpis.revenue.bestDay?.key || "—"}` : ""}/>
        <KpiCard label="Orders" metric={kpis.orders} detail={kpis.orders?.available ? `${kpis.orders.completed} completed · ${kpis.orders.cancelled} cancelled` : ""}/>
        <KpiCard label="Units sold" metric={kpis.units} onTrace={() => setTraceMetric("units")} detail={kpis.units?.available ? `${formatNumber(kpis.units.perOrder)} per order · top ${kpis.units.bestProduct?.key || "—"}` : ""}/>
        <KpiCard label="Average order value" metric={kpis.averageOrderValue} kind="money" detail={kpis.averageOrderValue?.available ? `Highest order ${formatMoney(kpis.averageOrderValue.highestValueOrder?.value)}` : ""}/>
        <KpiCard label="Gross profit" metric={kpis.grossProfit} kind="money" detail={kpis.grossProfit?.available ? `${formatPercent(kpis.grossProfit.margin)} margin · ${formatPercent(kpis.grossProfit.coverage)} coverage` : ""}/>
        <KpiCard label="Customers" metric={kpis.customers} detail={kpis.customers?.available ? `${kpis.customers.new} new · ${kpis.customers.returning} returning` : ""}/>
        <KpiCard label="Inventory units" metric={kpis.inventory?.available ? { ...kpis.inventory, value: kpis.inventory.totalUnits } : kpis.inventory} onTrace={() => setTraceMetric("stock")} detail={kpis.inventory?.available ? `${kpis.inventory.lowStock} low · ${kpis.inventory.outOfStock} out` : ""}/>
      </section>
      <section className="chart-grid">
        <article className="analytics-card chart-card wide"><div className="analytics-card-heading"><div><span className="eyebrow">Sales trend</span><h2>Daily revenue</h2></div><span>{data.period.from} – {data.period.to}</span></div><div className="chart-space"><ResponsiveContainer width="100%" height="100%"><LineChart data={data.charts.dailyRevenue}><CartesianGrid stroke="#1c2730" vertical={false}/><XAxis dataKey="date" tick={{ fill: "#74818b", fontSize: 9 }} minTickGap={28}/><YAxis tick={{ fill: "#74818b", fontSize: 9 }}/><Tooltip contentStyle={tooltipStyle}/><Line type="monotone" dataKey="value" name="Revenue" stroke="#57e7b0" strokeWidth={2} dot={false}/></LineChart></ResponsiveContainer></div></article>
        <article className="analytics-card chart-card"><div className="analytics-card-heading"><div><span className="eyebrow">Mix</span><h2>Revenue by category</h2></div></div><div className="chart-space"><ResponsiveContainer width="100%" height="100%"><BarChart data={data.charts.categories} layout="vertical"><CartesianGrid stroke="#1c2730" horizontal={false}/><XAxis type="number" tick={{ fill: "#74818b", fontSize: 9 }}/><YAxis dataKey="name" type="category" width={85} tick={{ fill: "#9aa6af", fontSize: 9 }}/><Tooltip contentStyle={tooltipStyle}/><Bar dataKey="revenue" fill="#57e7b0" radius={[0, 4, 4, 0]}/></BarChart></ResponsiveContainer></div></article>
        <article className="analytics-card highlights-card"><div className="analytics-card-heading"><div><span className="eyebrow">Decision signals</span><h2>Priority highlights</h2></div></div>{data.intelligence.insights.length ? <ul>{data.intelligence.insights.slice(0, 5).map((insight) => <li key={insight.id}><span className={`severity-dot ${insight.severity}`}/><div><strong>{insight.title}</strong><p>{insight.explanation}</p></div></li>)}</ul> : <div className="analytics-empty">No rule-based alerts were triggered for this period.</div>}</article>
      </section>
      <footer className="page-footer"><span>ALPHA / MODULE 08</span><span>Explainable business intelligence</span></footer>
    </>}
    {traceMetric && <TraceabilityDrawer metric={traceMetric} filters={filters} token={token} onClose={() => setTraceMetric(null)}/>}
  </div>;
}
