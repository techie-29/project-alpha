import { useEffect, useState } from "react";
import { getAnalytics } from "../services/analyticsApi";
import AnalyticsFilters from "../components/analytics/AnalyticsFilters";
import { formatMoney, formatNumber, formatPercent } from "../utils/formatters";

function downloadCsv(filename, rows) {
  const escape = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
  const csv = rows.map((row) => row.map(escape).join(",")).join("\n");
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const link = document.createElement("a"); link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url);
}

export default function ReportsPage({ token }) {
  const [filters, setFilters] = useState({ preset: "monthly" });
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => { let active = true; getAnalytics("overview", filters, token).then((response) => active && setData(response.data)).catch((requestError) => active && setError(requestError.message)); return () => { active = false; }; }, [filters, token]);
  function exportProducts() {
    downloadCsv("alpha-product-analytics.csv", [["Product", "Category", "ABC class", "Revenue", "Revenue share", "Units", "Profit", "Margin"], ...(data.products || []).map((product) => [product.productName, product.category, product.abcClass, product.revenue, product.revenueShare, product.units, product.profit, product.margin])]);
  }
  return <div className="page-content analytics-page report-page"><section className="page-header analytics-title"><div><span className="eyebrow">Reports and exports</span><h1>Executive summary</h1><p>Print a management-ready summary or export the current filtered product table as CSV.</p></div><AnalyticsFilters filters={filters} onChange={setFilters} datasets={data?.provenance || []}/></section>{error && <div className="analytics-error">{error}</div>}{!data && !error && <div className="analytics-loading"><span className="spinner"/>Preparing report…</div>}{data && <><div className="report-actions"><button className="primary-button" onClick={() => window.print()}>Print executive summary</button><button className="secondary-button" onClick={exportProducts}>Export product CSV</button></div><section className="print-summary analytics-card"><div className="report-brand"><strong>Project Alpha</strong><span>Executive Business Intelligence Summary</span></div><div className="report-period"><span>Reporting period</span><strong>{data.period.from} – {data.period.to}</strong></div><div className="report-kpis"><div><span>Revenue</span><strong>{data.kpis.revenue.available ? formatMoney(data.kpis.revenue.value) : "Unavailable"}</strong><small>{data.kpis.revenue.previousPeriod?.available ? `${formatPercent(data.kpis.revenue.previousPeriod.percentage)} vs previous` : data.kpis.revenue.reason}</small></div><div><span>Orders</span><strong>{data.kpis.orders.available ? formatNumber(data.kpis.orders.value) : "Unavailable"}</strong><small>{data.kpis.orders.available ? `${data.kpis.orders.completed} completed` : data.kpis.orders.reason}</small></div><div><span>Gross profit</span><strong>{data.kpis.grossProfit.available ? formatMoney(data.kpis.grossProfit.value) : "Unavailable"}</strong><small>{data.kpis.grossProfit.available ? `${formatPercent(data.kpis.grossProfit.margin)} margin` : data.kpis.grossProfit.reason}</small></div><div><span>Inventory</span><strong>{data.kpis.inventory.available ? `${formatNumber(data.kpis.inventory.totalUnits)} units` : "Unavailable"}</strong><small>{data.kpis.inventory.available ? `${data.kpis.inventory.lowStock} low stock` : data.kpis.inventory.reason}</small></div></div><div className="report-section"><h2>Source datasets</h2>{data.provenance.map((dataset) => <p key={dataset.id}><strong>{dataset.filename}</strong> · {dataset.rowsProcessed ?? dataset.rowsUploaded} rows · quality {dataset.qualityScore ?? "—"}/100</p>)}</div><div className="report-section"><h2>Priority decisions</h2>{data.intelligence.insights.slice(0, 8).map((insight) => <div key={insight.id}><strong>{insight.title}</strong><p>{insight.explanation}{insight.action ? ` ${insight.action}` : ""}</p></div>)}</div><footer>Generated from verified Project Alpha metrics. Statistical forecasts are identified separately and never presented as actuals.</footer></section></>} </div>;
}
