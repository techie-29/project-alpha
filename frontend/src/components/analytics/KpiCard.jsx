import { formatMoney, formatNumber, formatPercent } from "../../utils/formatters";

export default function KpiCard({ label, metric, kind = "number", detail, onTrace }) {
  if (!metric?.available) return <article className="kpi-card unavailable"><span>{label}</span><strong>Unavailable</strong><p>{metric?.reason || "This metric is not supported by the included data."}</p></article>;
  const display = kind === "money" ? formatMoney(metric.value) : formatNumber(metric.value);
  const comparison = metric.previousPeriod;
  return <button className="kpi-card" type="button" onClick={onTrace} disabled={!onTrace}>
    <span>{label}</span><strong>{display}</strong>
    {comparison?.available && <small className={comparison.absolute >= 0 ? "positive" : "negative"}>{comparison.absolute >= 0 ? "+" : ""}{formatPercent(comparison.percentage)} vs previous</small>}
    <p>{detail}</p>
    {onTrace && <em>View source records →</em>}
  </button>;
}
