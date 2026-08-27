export default function DatasetStructure({ columns }) {
  return <section className="result-section" aria-labelledby="structure-title">
    <div className="result-section-heading"><div><span className="step-number">02</span><div><h2 id="structure-title">Dataset structure</h2><p>Columns extracted from the uploaded file</p></div></div><span className="count-label">{columns.length} columns</span></div>
    {columns.length ? <div className="structure-table" role="table" aria-label="Extracted dataset columns">
      <div className="structure-row structure-head" role="row"><span role="columnheader">Column name</span><span role="columnheader">Detected type</span></div>
      {columns.map((column, index) => <div className="structure-row" role="row" key={`${column.name}-${index}`}><span role="cell"><i>{index + 1}</i>{column.name}</span><span role="cell">{column.detectedType || <em>Unknown</em>}</span></div>)}
    </div> : <div className="empty-result">No columns were returned by the server.</div>}
  </section>;
}
