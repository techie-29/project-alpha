import { useEffect, useState } from "react";

const PAGE_SIZE = 5;

function displayValue(value) {
  if (value === null || value === undefined || value === "") return <span className="empty-cell">—</span>;
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export default function DataPreview({ rows, columns }) {
  const [currentPage, setCurrentPage] = useState(0);
  const lastPage = Math.max(0, Math.ceil(rows.length / PAGE_SIZE) - 1);
  const safePage = Math.min(currentPage, lastPage);
  const startIndex = safePage * PAGE_SIZE;
  const endIndex = Math.min(startIndex + PAGE_SIZE, rows.length);
  const previewRows = rows.slice(startIndex, endIndex);
  const rangeLabel = rows.length === 0
    ? "No rows available"
    : startIndex === 0
      ? `Showing first ${endIndex} of ${rows.length} rows`
      : `Showing rows ${startIndex + 1}–${endIndex} of ${rows.length}`;
  const compactRange = rows.length === 0
    ? "0 rows"
    : `${startIndex + 1}–${endIndex} of ${rows.length}`;

  useEffect(() => {
    setCurrentPage(0);
  }, [rows]);

  return <section className="result-section" aria-labelledby="preview-title">
    <div className="result-section-heading"><div><span className="step-number">03</span><div><h2 id="preview-title">Data preview</h2><p>{rangeLabel}</p></div></div><span className="count-label">{compactRange}</span></div>
    {previewRows.length && columns.length ? <>
      <div className="preview-scroll"><table><thead><tr><th>#</th>{columns.map((column, index) => <th key={`${column.name}-${index}`}>{column.name}</th>)}</tr></thead><tbody>{previewRows.map((row, rowIndex) => <tr key={startIndex + rowIndex}><td>{startIndex + rowIndex + 1}</td>{columns.map((column, columnIndex) => <td key={`${column.name}-${columnIndex}`} title={String(row?.[column.name] ?? "")}>{displayValue(row?.[column.name])}</td>)}</tr>)}</tbody></table></div>
      {rows.length > PAGE_SIZE && <nav className="preview-pagination" aria-label="Dataset preview pages">
        <button type="button" className="pagination-button" onClick={() => setCurrentPage((page) => Math.max(0, page - 1))} disabled={safePage === 0} aria-label="Show previous five rows">‹</button>
        <span>{rangeLabel}</span>
        <button type="button" className="pagination-button" onClick={() => setCurrentPage((page) => Math.min(lastPage, page + 1))} disabled={safePage === lastPage} aria-label="Show next five rows">›</button>
      </nav>}
    </> : <div className="empty-result">No preview rows were returned by the server.</div>}
  </section>;
}
