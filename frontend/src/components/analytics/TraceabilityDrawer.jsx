import { useEffect, useState } from "react";
import { getTraceability } from "../../services/analyticsApi";
import { formatMoney, formatNumber, titleCase } from "../../utils/formatters";

export default function TraceabilityDrawer({ metric, filters, token, onClose }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    getTraceability(metric, filters, token).then((response) => active && setData(response.data)).catch((requestError) => active && setError(requestError.message));
    return () => { active = false; };
  }, [metric, filters, token]);
  return <div className="drawer-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && onClose()}>
    <aside className="trace-drawer" role="dialog" aria-modal="true" aria-labelledby="trace-title">
      <div className="drawer-heading"><div><span className="eyebrow">Metric traceability</span><h2 id="trace-title">{titleCase(metric)} evidence</h2></div><button onClick={onClose} aria-label="Close">×</button></div>
      {error && <div className="analytics-error">{error}</div>}
      {!data && !error && <div className="analytics-loading"><span className="spinner"/>Loading source evidence…</div>}
      {data && <><div className="trace-summary"><div><span>Records</span><strong>{formatNumber(data.recordCount)}</strong></div><div><span>Recomputed total</span><strong>{metric === "revenue" ? formatMoney(data.total) : formatNumber(data.total)}</strong></div></div>
        <p className="trace-chain">Metric → normalized record → mapping and transformations → original row → source file</p>
        <div className="trace-records">{data.records.map((record) => <details key={record.id} className="trace-record"><summary><span>{record.sourceFile} · row {record.sourceRowNumber}</span><strong>{metric === "revenue" ? formatMoney(record.value) : formatNumber(record.value)}</strong></summary><div><h3>Normalized record</h3><pre>{JSON.stringify(record.normalized, null, 2)}</pre><h3>Mapping and computed fields</h3><pre>{JSON.stringify({ mapping: record.mapping, computedFields: record.computedFields, repairedFields: record.repairedFields }, null, 2)}</pre><h3>Original row</h3><pre>{JSON.stringify(record.rawValues, null, 2)}</pre></div></details>)}</div>
      </>}
    </aside>
  </div>;
}
