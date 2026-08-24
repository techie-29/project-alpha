function displayValue(value) {
  if (value === null || value === undefined || value === "") return <span className="empty-cell">—</span>;
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export default function DataPreview({ rows, columns }) {
  const previewRows = rows.slice(0, 5);
  return <section className="result-section" aria-labelledby="preview-title">
    <div className="result-section-heading"><div><span className="step-number">03</span><div><h2 id="preview-title">Data preview</h2><p>First {Math.min(rows.length, 5)} rows returned by the ingestion API</p></div></div><span className="count-label">Preview only</span></div>
    {previewRows.length && columns.length ? <div className="preview-scroll"><table><thead><tr><th>#</th>{columns.map((column, index) => <th key={`${column.name}-${index}`}>{column.name}</th>)}</tr></thead><tbody>{previewRows.map((row, rowIndex) => <tr key={rowIndex}><td>{rowIndex + 1}</td>{columns.map((column, columnIndex) => <td key={`${column.name}-${columnIndex}`} title={String(row?.[column.name] ?? "")}>{displayValue(row?.[column.name])}</td>)}</tr>)}</tbody></table></div> : <div className="empty-result">No preview rows were returned by the server.</div>}
  </section>;
}
