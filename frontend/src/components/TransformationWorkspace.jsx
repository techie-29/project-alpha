import { useState } from "react";
import { runTransformation } from "../services/transformationApi";

function ExampleTable({ title, rows }) {
  if (!rows?.length) return null;
  const hidden = new Set(["raw_values", "repaired_fields", "computed_fields", "business_id", "dataset_id"]);
  const columns = Object.keys(rows[0]).filter((key) => !hidden.has(key)).slice(0, 7);
  return <div className="transformation-example"><h3>{title}</h3><div className="preview-scroll"><table><thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead><tbody>{rows.map((row, index) => <tr key={`${title}-${index}`}>{columns.map((column) => <td key={column}>{row[column] ?? "—"}</td>)}</tr>)}</tbody></table></div></div>;
}

export default function TransformationWorkspace({ ingestionId, token }) {
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  async function handleRun() {
    setStatus("running");
    setError("");
    try {
      const response = await runTransformation(ingestionId, token);
      setResult(response.data);
      setStatus("complete");
    } catch (requestError) {
      setError(requestError.message);
      setStatus("error");
    }
  }

  if (status === "idle") return <section className="transformation-card transformation-start"><div><span className="eyebrow">Modules 5 + 6</span><h2>Transform and store structured records</h2><p>Compute supported values, preserve evidence, and write typed sales, stock, and customer records.</p></div><button className="primary-button" onClick={handleRun}>Run transformation</button></section>;
  if (status === "running") return <section className="transformation-card validation-running"><span className="spinner"/>Transforming and storing accepted rows…</section>;
  if (status === "error") return <section className="transformation-card"><div className="error-banner"><span>!</span><div><strong>Transformation could not finish</strong><p>{error}</p></div></div><button className="secondary-button validation-retry" onClick={handleRun}>Try again</button></section>;

  const { summary, quality } = result;
  return <section className="transformation-card">
    <div className="validation-header"><div><span className="eyebrow">Modules 5 + 6</span><h2>Structured storage complete</h2><p>Accepted records are normalized and traceable to their original dataset rows.</p></div><div className="quality-score"><strong>{quality.score}</strong><span>Quality / 100</span></div></div>
    <div className="validation-grid transformation-grid"><div className="validation-stat good"><span>Accepted rows</span><strong>{summary.acceptedRows}</strong></div><div className="validation-stat"><span>Sales records</span><strong>{summary.salesRecords}</strong></div><div className="validation-stat"><span>Stock snapshots</span><strong>{summary.stockSnapshots}</strong></div><div className="validation-stat"><span>Customer records</span><strong>{summary.customerRecords}</strong></div><div className="validation-stat"><span>Product records</span><strong>{summary.productRecords}</strong></div><div className="validation-stat"><span>Supplier records</span><strong>{summary.supplierRecords}</strong></div></div>
    <div className="quality-breakdown"><h3>Quality score breakdown</h3><div><span>Validation <strong>{Math.round(quality.breakdown.validationSuccessRate * 100)}%</strong></span><span>Required mapping <strong>{Math.round(quality.breakdown.mappingCoverage * 100)}%</strong></span><span>Duplicate-free <strong>{Math.round((1 - quality.breakdown.duplicateRate) * 100)}%</strong></span><span>Critical completeness <strong>{Math.round(quality.breakdown.criticalFieldCompleteness * 100)}%</strong></span></div></div>
    <ExampleTable title="Sales examples" rows={result.examples.sales}/><ExampleTable title="Stock examples" rows={result.examples.stock}/><ExampleTable title="Customer examples" rows={result.examples.customers}/><ExampleTable title="Product examples" rows={result.examples.products}/><ExampleTable title="Supplier examples" rows={result.examples.suppliers}/>
    <div className="next-stage"><div><span className="eyebrow">Pipeline handoff</span><h2>Ready for analytics</h2><p>Project Alpha can now calculate KPIs and evidence-driven insights from structured records.</p></div><button className="future-button" disabled>Open Dashboard <span>→</span></button></div>
  </section>;
}
