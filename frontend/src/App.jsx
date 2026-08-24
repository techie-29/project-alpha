"use client";

import { useState } from "react";
import Sidebar from "./components/Sidebar";
import UploadZone from "./components/UploadZone";
import FileCard from "./components/FileCard";
import IngestionResult from "./components/IngestionResult";
import { uploadDataset } from "./services/uploadApi";

const MAX_FILE_SIZE = 10 * 1024 * 1024;
const ALLOWED_EXTENSIONS = ["csv", "xlsx", "xls"];

function validateFile(file) {
  const extension = file.name.split(".").pop()?.toLowerCase();
  if (!extension || !ALLOWED_EXTENSIONS.includes(extension)) return "Unsupported file type. Choose a CSV, XLSX, or XLS file.";
  if (file.size > MAX_FILE_SIZE) return "This file is larger than 10 MB. Choose a smaller dataset.";
  return "";
}

export default function App() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  function handleFileSelect(file) {
    const validationError = validateFile(file);
    setError(validationError);
    setResult(null);
    if (validationError) { setSelectedFile(null); setStatus("invalid"); return; }
    setSelectedFile(file);
    setStatus("selected");
  }

  function resetUpload() {
    setSelectedFile(null); setError(""); setResult(null); setStatus("idle"); setIsDragging(false);
  }

  async function handleUpload() {
    if (!selectedFile) return;
    setStatus("uploading"); setError("");
    try {
      // Later: pass the JWT as the second argument to uploadDataset.
      const response = await uploadDataset(selectedFile);
      setResult(response); setStatus("success");
    } catch (uploadError) { setError(uploadError.message); setStatus("error"); }
  }

  return <div className="app-shell"><Sidebar/><main className="main-content"><header className="topbar"><div className="mobile-brand"><span>A</span>Alpha</div><div className="account-area"><div className="account-avatar">BA</div><div><strong>Business Account</strong><span><i/>Authenticated workspace</span></div></div></header><div className="page-content">
    <section className="page-header"><span className="eyebrow">Data Ingestion</span><h1>Upload Dataset</h1><p>Upload business data for Alpha to extract and prepare for the processing pipeline.</p></section>
    {status !== "success" && <section className="upload-panel"><div className="panel-heading"><div><span className="step-number">01</span><div><h2>Select a dataset</h2><p>Your file stays on this device until you click Upload Dataset.</p></div></div><div className="secure-label"><svg viewBox="0 0 24 24"><rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>Secure upload</div></div><UploadZone onFileSelect={handleFileSelect} isDragging={isDragging} setIsDragging={setIsDragging} disabled={status === "uploading"}/></section>}
    {error && <div className="error-banner" role="alert"><span>!</span><div><strong>{status === "invalid" ? "File not accepted" : "Upload could not be completed"}</strong><p>{error}</p></div></div>}
    {selectedFile && status !== "success" && <FileCard file={selectedFile} onRemove={resetUpload} onUpload={handleUpload} isUploading={status === "uploading"}/>} 
    {status === "success" && result && <IngestionResult response={result} selectedFile={selectedFile} onReset={resetUpload}/>} 
    <footer className="page-footer"><span>ALPHA / MODULE 02</span><span>Data Ingestion Gateway</span></footer>
  </div></main></div>;
}
