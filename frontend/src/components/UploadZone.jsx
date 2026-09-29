import { useRef } from "react";

export default function UploadZone({ onFilesSelect, isDragging, setIsDragging, disabled }) {
  const inputRef = useRef(null);

  function handleDrop(event) {
    event.preventDefault();
    setIsDragging(false);
    const files = [...event.dataTransfer.files];
    if (files.length) onFilesSelect(files);
  }

  function handleKeyDown(event) {
    if ((event.key === "Enter" || event.key === " ") && !disabled) {
      event.preventDefault();
      inputRef.current?.click();
    }
  }

  return <div className={`upload-zone ${isDragging ? "is-dragging" : ""} ${disabled ? "is-disabled" : ""}`} onDragOver={(event) => { event.preventDefault(); if (!disabled) setIsDragging(true); }} onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setIsDragging(false); }} onDrop={disabled ? (event) => event.preventDefault() : handleDrop} onClick={() => !disabled && inputRef.current?.click()} onKeyDown={handleKeyDown} role="button" tabIndex={disabled ? -1 : 0} aria-label="Choose or drop a dataset file">
    <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" multiple hidden disabled={disabled} onChange={(event) => { const files = [...event.target.files]; if (files.length) onFilesSelect(files); event.target.value = ""; }}/>
    <div className="upload-icon"><svg viewBox="0 0 24 24"><path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M5 20h14"/></svg></div>
    <h2>{isDragging ? "Drop your datasets here" : "Upload your business datasets"}</h2>
    <p>Drag and drop up to 10 files, or <span>browse files</span></p>
    <div className="file-rules"><span>CSV</span><span>XLSX</span><span>XLS</span><i/>10 MB per file</div>
  </div>;
}
