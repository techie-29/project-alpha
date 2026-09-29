function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

const STATUS_LABELS = {
  queued: "Queued",
  invalid: "Not accepted",
  uploading: "Uploading",
  processing: "Parsing and profiling",
  completed: "Ready for mapping",
  failed: "Needs attention"
};

export default function UploadQueue({
  items,
  onRemove,
  onUpload,
  onViewResult,
  isBusy
}) {
  const validCount = items.filter((item) => item.status === "queued").length;

  return <section className="upload-queue" aria-labelledby="upload-queue-title">
    <div className="queue-heading">
      <div><span className="eyebrow">Batch queue</span><h2 id="upload-queue-title">{items.length} selected file{items.length === 1 ? "" : "s"}</h2></div>
      {validCount > 0 && <button className="primary-button" type="button" onClick={onUpload} disabled={isBusy}>
        {isBusy ? <><span className="spinner"/>Processing batch…</> : `Upload ${validCount} file${validCount === 1 ? "" : "s"}`}
      </button>}
    </div>

    <div className="queue-items">
      {items.map((item) => <article className={`queue-item queue-${item.status}`} key={item.id}>
        <div className="file-type-icon">{item.file.name.split(".").pop()?.toUpperCase()}</div>
        <div className="queue-file-details">
          <strong title={item.file.name}>{item.file.name}</strong>
          <span>{formatFileSize(item.file.size)}</span>
          {(item.status === "uploading" || item.status === "processing") && <div className="queue-progress" aria-label={`${item.progress}% uploaded`}><i style={{ width: `${item.progress}%` }}/></div>}
          {item.error && <small>{item.error}</small>}
        </div>
        <span className={`queue-status status-${item.status}`}><i/>{STATUS_LABELS[item.status]}</span>
        {item.status === "completed" && <button className="queue-action" type="button" onClick={() => onViewResult(item.id)}>Preview</button>}
        {(item.status === "queued" || item.status === "invalid" || item.status === "failed") && <button className="queue-action" type="button" onClick={() => onRemove(item.id)} disabled={isBusy}>Remove</button>}
      </article>)}
    </div>
  </section>;
}
