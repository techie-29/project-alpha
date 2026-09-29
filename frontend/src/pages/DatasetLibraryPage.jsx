import { useEffect, useState } from "react";
import { exportDatasetFile, getDataset, getDatasets, setDatasetIncluded } from "../services/datasetApi";
import { formatNumber, formatPercent, titleCase } from "../utils/formatters";

export default function DatasetLibraryPage({ token }) {
  const [datasets, setDatasets] = useState([]);
  const [selected, setSelected] = useState(null);
  const [error, setError] = useState("");
  const [workingId, setWorkingId] = useState(null);
  async function refresh() {
    try { const response = await getDatasets(token); setDatasets(response.data.datasets); } catch (requestError) { setError(requestError.message); }
  }
  useEffect(() => { refresh(); }, [token]);
  async function openDataset(id) {
    setError("");
    try { const response = await getDataset(id, token); setSelected(response.data); } catch (requestError) { setError(requestError.message); }
  }
  async function toggle(dataset) {
    setWorkingId(dataset.id); setError("");
    try { await setDatasetIncluded(dataset.id, !dataset.included, token); await refresh(); if (selected?.id === dataset.id) await openDataset(dataset.id); } catch (requestError) { setError(requestError.message); } finally { setWorkingId(null); }
  }
  async function exportFile(type, format) {
    setError("");
    try { await exportDatasetFile(selected.id, type, format, token); } catch (requestError) { setError(requestError.message); }
  }
  return <div className="page-content analytics-page"><section className="page-header"><span className="eyebrow">Data trust</span><h1>Dataset library</h1><p>Control which datasets contribute to analytics and inspect mapping, validation, quality, and overlap evidence.</p></section>{error && <div className="analytics-error">{error}</div>}<section className="analytics-card"><div className="analytics-card-heading"><div><span className="eyebrow">Stored datasets</span><h2>Analytics inclusion</h2></div><span>{datasets.length} total</span></div><div className="dataset-list">{datasets.map((dataset) => <article key={dataset.id} className={dataset.included ? "included" : "excluded"}><button className="dataset-open" onClick={() => openDataset(dataset.id)}><div><strong>{dataset.filename}</strong><span>{titleCase(dataset.datasetType)} · {formatNumber(dataset.rowsUploaded)} rows · {dataset.status}</span></div><div className="dataset-quality"><strong>{dataset.qualityScore ?? "—"}</strong><span>quality</span></div></button><div className="dataset-controls"><label className="toggle"><input type="checkbox" checked={dataset.included} disabled={workingId === dataset.id} onChange={() => toggle(dataset)}/><span/>Included in analytics</label><div className="dataset-warnings">{dataset.overlapWarnings?.length > 0 && <p>⚠ Overlaps {dataset.overlapWarnings.map((warning) => warning.filename).join(", ")}</p>}{dataset.repeatedOrderCount > 0 && <p>⚠ {dataset.repeatedOrderCount} order ID{dataset.repeatedOrderCount === 1 ? "" : "s"} also appear in another dataset</p>}</div></div></article>)}</div>{!datasets.length && <div className="analytics-empty">No datasets have been uploaded yet.</div>}</section>{selected && <div className="drawer-backdrop" role="presentation" onMouseDown={(event) => event.target === event.currentTarget && setSelected(null)}><aside className="trace-drawer dataset-detail" role="dialog" aria-modal="true"><div className="drawer-heading"><div><span className="eyebrow">Dataset #{selected.id}</span><h2>{selected.filename}</h2></div><button onClick={() => setSelected(null)}>×</button></div><div className="dataset-export-actions"><button className="secondary-button" onClick={() => exportFile(selected.datasetType === "inventory" ? "stock" : "sales", "csv")}>Export normalized CSV</button><button className="secondary-button" onClick={() => exportFile(selected.datasetType === "inventory" ? "stock" : "sales", "xlsx")}>Export Excel</button><button className="secondary-button" onClick={() => exportFile("issues", "csv")}>Export issue report</button></div><div className="detail-stat-grid"><div><span>Type</span><strong>{titleCase(selected.datasetType)}</strong></div><div><span>Rows processed</span><strong>{formatNumber(selected.rowsProcessed)}</strong></div><div><span>Mapping</span><strong>{formatPercent(selected.mappingCoverage)}</strong></div><div><span>Valid rows</span><strong>{formatPercent(selected.validationSuccessRate)}</strong></div><div><span>Quality</span><strong>{selected.qualityScore ?? "—"}/100</strong></div><div><span>Included</span><strong>{selected.included ? "Yes" : "No"}</strong></div></div>{selected.quality && <section className="detail-section"><h3>Quality score breakdown</h3><pre>{JSON.stringify(selected.quality, null, 2)}</pre></section>}<section className="detail-section"><h3>Confirmed mapping</h3><pre>{JSON.stringify(selected.mapping, null, 2)}</pre></section><section className="detail-section"><h3>Validation issues (first 100)</h3>{selected.issues.length ? selected.issues.map((issue, index) => <div className="issue-row" key={`${issue.row_index}-${index}`}><strong>Row {issue.row_index} · {issue.issue_code}</strong><span>{issue.message}</span></div>) : <p>No persisted validation issues.</p>}</section></aside></div>}<footer className="page-footer"><span>ALPHA / DATASET LIBRARY</span><span>Source control and quality</span></footer></div>;
}
