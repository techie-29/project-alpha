export default function AnalyticsFilters({ filters, onChange, datasets = [] }) {
  const custom = filters.preset === "custom";
  return <div className="analytics-filters" aria-label="Analytics filters">
    <label>Period<select value={filters.preset} onChange={(event) => onChange({ ...filters, preset: event.target.value })}>
      <option value="daily">Day</option><option value="weekly">7 days</option><option value="monthly">Month</option><option value="quarterly">Quarter</option><option value="custom">Custom</option>
    </select></label>
    {custom && <><label>From<input type="date" value={filters.from || ""} onChange={(event) => onChange({ ...filters, from: event.target.value })}/></label><label>To<input type="date" value={filters.to || ""} onChange={(event) => onChange({ ...filters, to: event.target.value })}/></label></>}
    <label>Dataset<select value={filters.datasetId || ""} onChange={(event) => onChange({ ...filters, datasetId: event.target.value })}>
      <option value="">All included datasets</option>{datasets.map((dataset) => <option key={dataset.id} value={dataset.id}>{dataset.filename}</option>)}
    </select></label>
  </div>;
}
