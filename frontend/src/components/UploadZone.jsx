import { useRef } from "react";

export default function UploadZone({ onFileSelect, isDragging, setIsDragging, disabled }) {
  const inputRef = useRef(null);

  function handleDrop(event) {
    event.preventDefault();
    setIsDragging(false);
    const [file] = event.dataTransfer.files;
    if (file) onFileSelect(file);
  }

  function handleKeyDown(event) {
    if ((event.key === "Enter" || event.key === " ") && !disabled) {
      event.preventDefault();
      inputRef.current?.click();
    }
  }

  return <div className={`upload-zone ${isDragging ? "is-dragging" : ""} ${disabled ? "is-disabled" : ""}`} onDragOver={(event) => { event.preventDefault(); if (!disabled) setIsDragging(true); }} onDragLeave={(event) => { if (!event.currentTarget.contains(event.relatedTarget)) setIsDragging(false); }} onDrop={disabled ? (event) => event.preventDefault() : handleDrop} onClick={() => !disabled && inputRef.current?.click()} onKeyDown={handleKeyDown} role="button" tabIndex={disabled ? -1 : 0} aria-label="Choose or drop a dataset file">
    <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" hidden disabled={disabled} onChange={(event) => { const [file] = event.target.files; if (file) onFileSelect(file); event.target.value = ""; }}/>
    <div className="upload-icon"><svg viewBox="0 0 24 24"><path d="M12 16V4"/><path d="m7 9 5-5 5 5"/><path d="M5 20h14"/></svg></div>
    <h2>{isDragging ? "Drop your dataset here" : "Upload your business dataset"}</h2>
    <p>Drag and drop a file here, or <span>browse files</span></p>
    <div className="file-rules"><span>CSV</span><span>XLSX</span><span>XLS</span><i/>Maximum 10 MB</div>
  </div>;
}
