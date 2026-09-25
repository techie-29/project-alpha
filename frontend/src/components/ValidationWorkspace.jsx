import { useState } from "react";
import { runValidation } from "../services/validationApi";

function Summary({ label, value, tone = "" }) {
  return <div className={`validation-stat ${tone}`}><span>{label}</span><strong>{value}</strong></div>;
}

export default function ValidationWorkspace({ ingestionId, token, onContinue }) {
  const [result, setResult] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");

  async function handleRun() {
    setStatus("running");
    setError("");
    try {
      const response = await runValidation(ingestionId, token);
      setResult(response.data);
      setStatus("complete");
    } catch (requestError) {
      setError(requestError.message);
      setStatus("error");
    }
  }

  if (status === "idle") {
    return <section className="validation-card validation-start"><div><span className="eyebrow">Module 4</span><h2>Validate mapped rows</h2><p>Run deterministic checks for missing values, types, dates, emails, duplicates, and suspicious values.</p></div><button className="primary-button" type="button" onClick={handleRun}>Run validation</button></section>;
  }

  if (status === "running") {
    return <section className="validation-card validation-running"><span className="spinner"/>Validating every mapped row…</section>;
  }
  if (status === "error") {
    return <section className="validation-card"><div className="error-banner"><span>!</span><div><strong>Validation could not finish</strong><p>{error}</p></div></div><button className="secondary-button validation-retry" type="button" onClick={handleRun}>Try again</button></section>;
  }

  const summary = result.summary;
  return <section className="validation-card" aria-labelledby="validation-title">
    <div className="validation-header"><div><span className="eyebrow">Module 4</span><h2 id="validation-title">Validation result</h2><p>Bad rows were isolated; usable rows continue through the pipeline.</p></div><span className="status-pill">Ready for transformation</span></div>
    <div className="validation-grid">
      <Summary label="Rows checked" value={summary.totalRows}/><Summary label="Valid" value={summary.validRows} tone="good"/><Summary label="Repaired" value={summary.repairedRows} tone="repair"/><Summary label="Skipped" value={summary.skippedRows} tone={summary.skippedRows ? "bad" : ""}/><Summary label="Success rate" value={`${Math.round(summary.validationSuccessRate * 100)}%`} tone="good"/>
    </div>
    <div className="validation-section">
      <div className="validation-section-title"><h3>Issue report</h3><span>{summary.issueCount} total issues; first {result.returnedIssueCount} shown</span></div>
      {result.issues.length > 0 ? <div className="mapping-table-wrapper"><table className="mapping-table issue-table"><thead><tr><th>Row</th><th>Field</th><th>Issue</th><th>Severity</th><th>Action</th><th>Explanation</th></tr></thead><tbody>{result.issues.map((issue, index) => <tr key={`${issue.row_index}-${issue.code}-${index}`}><td>{issue.row_index}</td><td><code>{issue.field || "row"}</code></td><td>{issue.code}</td><td><span className={`issue-severity severity-${issue.severity}`}>{issue.severity}</span></td><td>{issue.action}</td><td>{issue.message}</td></tr>)}</tbody></table></div> : <div className="empty-result">No validation issues were found.</div>}
    </div>
    <div className="validation-section">
      <div className="validation-section-title"><h3>Row outcomes</h3><span>First {result.returnedRowCount} rows shown</span></div>
      <div className="row-outcomes">{result.rows.map((row) => <div className={`row-outcome outcome-${row.status}`} key={row.sourceRowNumber}><strong>Row {row.sourceRowNumber}</strong><span>{row.status}</span><small>{row.issues.length} issue{row.issues.length === 1 ? "" : "s"}</small></div>)}</div>
    </div>
    <div className="next-stage"><div><span className="eyebrow">Pipeline handoff</span><h2>Ready for transformation</h2><p>Only valid and repaired rows will be normalized into structured business records. Skipped rows remain traceable with their reasons.</p></div><button className="primary-button" type="button" onClick={onContinue}>Continue to Transformation <span>→</span></button></div>
  </section>;
}
