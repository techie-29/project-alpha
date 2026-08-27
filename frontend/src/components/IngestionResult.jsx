import DatasetStructure from "./DatasetStructure";
import DataPreview from "./DataPreview";
import { normalizeIngestionResult } from "../utils/normalizeIngestionResult";

function SummaryItem({ label, value, accent }) {
  return <div className={`summary-item ${accent ? "summary-accent" : ""}`}><span>{label}</span><strong>{value ?? "Not available"}</strong></div>;
}

export default function IngestionResult({ response, selectedFile, onReset }) {
  const result = normalizeIngestionResult(response, selectedFile);
  return <div className="ingestion-result">
    <section className="success-header"><div className="success-icon"><svg viewBox="0 0 24 24"><path d="m5 12 4 4L19 6"/></svg></div><div><span className="eyebrow">Data Ingestion Result</span><h1>Dataset ingested successfully</h1><p>Alpha received the file, extracted its structure, and prepared the result for validation.</p></div><span className="success-badge"><i/>Complete</span></section>
    <section className="result-card"><div className="result-title"><div><h2>Dataset Preview &amp; Profile</h2><p>{result.fileName}</p></div><span className="status-pill">{result.status}</span></div>
      <div className="summary-grid"><SummaryItem label="Rows extracted" value={result.rowCount} accent/><SummaryItem label="Columns found" value={result.columnCount}/><SummaryItem label="File type" value={result.fileType}/>{result.sheetName && <SummaryItem label="Sheet" value={result.sheetName}/>}</div>
    </section>
    <DatasetStructure columns={result.columns}/>
    <DataPreview rows={result.rows} columns={result.columns}/>
    <section className="next-stage"><div><span className="eyebrow">Pipeline handoff</span><h2>Ready for validation</h2><p>Business validation, cleaning, and transformation belong to the upcoming modules and are not performed during ingestion.</p></div><div className="result-actions"><button className="secondary-button" onClick={onReset}><svg viewBox="0 0 24 24"><path d="M3 12a9 9 0 1 0 3-6.7L3 8"/><path d="M3 3v5h5"/></svg>Upload Another Dataset</button><button className="future-button" disabled>Continue to Validation <span>→</span></button></div></section>
  </div>;
}
