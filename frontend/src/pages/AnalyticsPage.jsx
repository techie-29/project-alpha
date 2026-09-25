import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Area, AreaChart, Bar, BarChart, CartesianGrid, Line, LineChart, ReferenceDot, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getAnalytics } from "../services/analyticsApi";
import AnalyticsFilters from "../components/analytics/AnalyticsFilters";
import KpiCard from "../components/analytics/KpiCard";
import TraceabilityDrawer from "../components/analytics/TraceabilityDrawer";
import { formatMoney, formatNumber, formatPercent, titleCase } from "../utils/formatters";

const tooltipStyle = { background: "#0d141b", border: "1px solid #263541", borderRadius: 8, fontSize: 11 };

function Table({ headers, rows, empty }) {
  return <div className="analytics-table-wrap"><table className="analytics-table"><thead><tr>{headers.map((header) => <th key={header}>{header}</th>)}</tr></thead><tbody>{rows.length ? rows.map((row, index) => <tr key={row.key || index}>{row.cells.map((cell, cellIndex) => <td key={cellIndex}>{cell}</td>)}</tr>) : <tr><td colSpan={headers.length} className="analytics-empty">{empty}</td></tr>}</tbody></table></div>;
}

function SalesView({ data, setTrace }) {
  const kpis = data.kpis || {};
  const actual = data.charts?.dailyRevenue || [];
  const forecast = data.forecast;
  const combinedForecast = [...actual.slice(-30).map((point) => ({ ...point, actual: point.value })), ...(forecast?.points || []).map((point) => ({ ...point, forecast: point.value }))];
  return <>
    <section className="kpi-grid compact-kpis"><KpiCard label="Revenue" metric={kpis.revenue} kind="money" onTrace={() => setTrace("revenue")}/><KpiCard label="Orders" metric={kpis.orders}/><KpiCard label="Units" metric={kpis.units} onTrace={() => setTrace("units")}/><KpiCard label="AOV" metric={kpis.averageOrderValue} kind="money"/><KpiCard label="Profit" metric={kpis.grossProfit} kind="money"/></section>
    <section className="chart-grid"><article className="analytics-card chart-card wide"><div className="analytics-card-heading"><div><span className="eyebrow">Sales analytics</span><h2>Revenue trend and anomalies</h2></div><span>{data.anomalies?.anomalies?.length || 0} anomalies</span></div><div className="chart-space"><ResponsiveContainer><LineChart data={actual}><CartesianGrid stroke="#1c2730" vertical={false}/><XAxis dataKey="date" tick={{ fill: "#74818b", fontSize: 9 }} minTickGap={25}/><YAxis tick={{ fill: "#74818b", fontSize: 9 }}/><Tooltip contentStyle={tooltipStyle}/><Line dataKey="value" stroke="#57e7b0" dot={false} strokeWidth={2}/>{(data.anomalies?.anomalies || []).map((point) => <ReferenceDot key={point.date} x={point.date} y={point.value} r={5} fill="#ff8c8c" stroke="none"/>)}</LineChart></ResponsiveContainer></div></article>
      <article className="analytics-card chart-card"><div className="analytics-card-heading"><div><span className="eyebrow">Statistical forecast</span><h2>Next 14 days</h2></div>{forecast?.backtest?.ok && <span>{forecast.backtest.confidence} confidence · sMAPE {formatPercent(forecast.backtest.smape)}</span>}</div>{forecast?.ok ? <div className="chart-space"><ResponsiveContainer><LineChart data={combinedForecast}><CartesianGrid stroke="#1c2730" vertical={false}/><XAxis dataKey="date" tick={{ fill: "#74818b", fontSize: 9 }} minTickGap={25}/><YAxis tick={{ fill: "#74818b", fontSize: 9 }}/><Tooltip contentStyle={tooltipStyle}/><Line dataKey="actual" stroke="#57e7b0" dot={false}/><Line dataKey="forecast" stroke="#7cbcff" strokeDasharray="5 4" dot={false}/></LineChart></ResponsiveContainer></div> : <div className="analytics-empty">{forecast?.reason || "Forecast unavailable."}</div>}</article></section>
  </>;
}

function ProductsView({ data }) {
  const rows = (data.products || []).map((product) => ({ key: product.productKey, cells: [product.productName, product.category || "—", <span className={`abc-badge abc-${product.abcClass}`}>{product.abcClass}</span>, formatMoney(product.revenue), formatPercent(product.revenueShare), formatNumber(product.units), product.profit === null ? "Unavailable" : formatMoney(product.profit), formatPercent(product.margin)] }));
  return <section className="analytics-card"><div className="analytics-card-heading"><div><span className="eyebrow">Pareto classification</span><h2>Product performance</h2></div><span>A first 80% · B next 15% · C final 5%</span></div><Table headers={["Product", "Category", "ABC", "Revenue", "Share", "Units", "Profit", "Margin"]} rows={rows} empty="Product analytics unavailable — include sales data with product and revenue fields."/></section>;
}

function InventoryView({ data, setTrace }) {
  const kpi = data.kpi;
  const rows = (data.inventory || []).map((item) => ({ key: item.productKey, cells: [item.productName, formatNumber(item.stock), item.reorderLevel ?? "—", item.daysOfCover === null ? "No recent sales" : `${formatNumber(item.daysOfCover)} days`, formatNumber(item.velocity), item.inventoryValue === null ? "Unavailable" : formatMoney(item.inventoryValue), item.supplier_name || "—"] }));
  return <><section className="kpi-grid compact-kpis"><KpiCard label="Products" metric={kpi?.available ? { available: true, value: kpi.products } : kpi}/><KpiCard label="Units in stock" metric={kpi?.available ? { available: true, value: kpi.totalUnits } : kpi} onTrace={() => setTrace("stock")}/><KpiCard label="Healthy" metric={kpi?.available ? { available: true, value: kpi.healthy } : kpi}/><KpiCard label="Low stock" metric={kpi?.available ? { available: true, value: kpi.lowStock } : kpi}/><KpiCard label="Out of stock" metric={kpi?.available ? { available: true, value: kpi.outOfStock } : kpi}/></section><section className="analytics-card"><div className="analytics-card-heading"><div><span className="eyebrow">Latest valid snapshot only</span><h2>Stock-out risk ranking</h2></div></div><Table headers={["Product", "Stock", "Reorder", "Days of cover", "Daily velocity", "Value", "Supplier"]} rows={rows} empty="Inventory analytics unavailable — include stock_qty data."/></section></>;
}

function CustomersView({ data }) {
  const rfm = data.customers?.rfm;
  const rows = (rfm?.customers || []).map((customer) => ({ key: customer.customerKey, cells: [customer.customerName, customer.segment, `${customer.recency} days`, customer.frequency, formatMoney(customer.monetary), `${customer.recencyScore}/${customer.frequencyScore}/${customer.monetaryScore}`] }));
  return <><section className="kpi-grid compact-kpis"><KpiCard label="Customers" metric={data.kpi}/>{data.customers?.concentration && <KpiCard label="Top 10% revenue share" metric={{ available: true, value: data.customers.concentration.topTenPercentShare * 100 }} detail="Percent of customer revenue"/>}</section><section className="analytics-card"><div className="analytics-card-heading"><div><span className="eyebrow">RFM segmentation</span><h2>Customer value and engagement</h2></div><span>Recency / frequency / monetary scored 1–5</span></div><Table headers={["Customer", "Segment", "Recency", "Orders", "Spend", "R/F/M"]} rows={rows} empty={rfm?.reason || "Customer analytics unavailable."}/></section></>;
}

export default function AnalyticsPage({ token, kind }) {
  const [searchParams] = useSearchParams();
  const searchKey = searchParams.toString();
  const [filters, setFilters] = useState(() => ({
    preset: searchParams.get("preset") || "monthly",
    datasetId: searchParams.get("datasetId") || "",
    product: searchParams.get("product") || "",
    category: searchParams.get("category") || "",
    customer: searchParams.get("customer") || "",
    status: searchParams.get("status") || ""
  }));
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  const [trace, setTrace] = useState(null);
  useEffect(() => {
    if (!searchKey) return;
    setFilters((current) => ({
      ...current,
      product: searchParams.get("product") || current.product,
      category: searchParams.get("category") || current.category,
      customer: searchParams.get("customer") || current.customer,
      status: searchParams.get("status") || current.status
    }));
  }, [searchKey]);
  useEffect(() => {
    let active = true; setError(""); setData(null);
    getAnalytics(kind, filters, token).then((response) => active && setData(response.data)).catch((requestError) => active && setError(requestError.message));
    return () => { active = false; };
  }, [kind, filters, token]);
  return <div className="page-content analytics-page"><section className="page-header analytics-title"><div><span className="eyebrow">Detailed analytics</span><h1>{titleCase(kind)}</h1><p>Filtered, explainable analysis calculated from included structured records.</p></div><AnalyticsFilters filters={filters} onChange={setFilters}/></section>{error && <div className="analytics-error">{error}</div>}{!data && !error && <div className="analytics-loading"><span className="spinner"/>Calculating {kind} analytics…</div>}{data && kind === "sales" && <SalesView data={data} setTrace={setTrace}/>} {data && kind === "products" && <ProductsView data={data}/>} {data && kind === "inventory" && <InventoryView data={data} setTrace={setTrace}/>} {data && kind === "customers" && <CustomersView data={data}/>}<footer className="page-footer"><span>ALPHA / {titleCase(kind)}</span><span>Verified structured records</span></footer>{trace && <TraceabilityDrawer metric={trace} filters={filters} token={token} onClose={() => setTrace(null)}/>}</div>;
}
