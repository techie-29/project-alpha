function formatFileSize(bytes) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
}

function getFileType(file) {
  return file.name.split(".").pop()?.toUpperCase() || "File";
}

export default function FileCard({ file, onRemove, onUpload, isUploading }) {
  return <section className="selected-file" aria-labelledby="selected-file-title">
    <div className="section-heading"><div><span className="eyebrow">Ready to upload</span><h2 id="selected-file-title">Selected file</h2></div></div>
    <div className="file-card"><div className="file-type-icon">{getFileType(file)}</div><div className="file-details"><strong title={file.name}>{file.name}</strong><span>{getFileType(file)} dataset <i/> {formatFileSize(file.size)}</span></div><button className="text-button" onClick={onRemove} disabled={isUploading} aria-label={`Remove ${file.name}`}>Remove</button><button className="primary-button" onClick={onUpload} disabled={isUploading}>{isUploading ? <><span className="spinner"/>Uploading and processing…</> : <><svg viewBox="0 0 24 24"><path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M5 20h14"/></svg>Upload Dataset</>}</button></div>
  </section>;
}
