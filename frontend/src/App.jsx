"use client";

import { useEffect, useState } from "react";
import AuthPage from "./components/AuthPage";
import Sidebar from "./components/Sidebar";
import UploadZone from "./components/UploadZone";
import FileCard from "./components/FileCard";
import IngestionResult from "./components/IngestionResult";
import { getCurrentAccount } from "./services/authApi";
import { uploadDataset } from "./services/uploadApi";

const TOKEN_KEY = "alphaToken";
const MAX_FILE_SIZE = 10 * 1024 * 1024;
const ALLOWED_EXTENSIONS = ["csv", "xlsx", "xls"];

function validateFile(file) {
  const extension = file.name.split(".").pop()?.toLowerCase();
  if (!extension || !ALLOWED_EXTENSIONS.includes(extension)) return "Unsupported file type. Choose a CSV, XLSX, or XLS file.";
  if (file.size > MAX_FILE_SIZE) return "This file is larger than 10 MB. Choose a smaller dataset.";
  return "";
}

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [account, setAccount] = useState(null);
  const [authStatus, setAuthStatus] = useState(token ? "checking" : "signed-out");
  const [selectedFile, setSelectedFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [result, setResult] = useState(null);

  useEffect(() => {
    if (!token) return;

    let active = true;
    getCurrentAccount(token)
      .then((response) => {
        if (!active) return;
        setAccount(response.data.account);
        setAuthStatus("signed-in");
      })
      .catch(() => {
        if (!active) return;
        localStorage.removeItem(TOKEN_KEY);
        setToken(null);
        setAccount(null);
        setAuthStatus("signed-out");
      });

    return () => { active = false; };
  }, [token]);

  function handleAuthenticated(authData) {
    localStorage.setItem(TOKEN_KEY, authData.token);
    setToken(authData.token);
    setAccount(authData.account);
    setAuthStatus("signed-in");
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setAccount(null);
    setAuthStatus("signed-out");
    resetUpload();
  }

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
      const response = await uploadDataset(selectedFile, token);
      setResult(response); setStatus("success");
    } catch (uploadError) {
      if (uploadError.status === 401) { handleLogout(); return; }
      setError(uploadError.message); setStatus("error");
    }
  }

  if (authStatus === "checking") return <div className="auth-loading">Checking your session...</div>;
  if (authStatus !== "signed-in") return <AuthPage onAuthenticated={handleAuthenticated}/>;

  const accountLabel = account?.businessName || account?.email || "Business Account";
  const initials = accountLabel.slice(0, 2).toUpperCase();

  return <div className="app-shell"><Sidebar/><main className="main-content"><header className="topbar"><div className="mobile-brand"><span>A</span>Alpha</div><div className="account-area"><div className="account-avatar">{initials}</div><div><strong>{accountLabel}</strong><span><i/>Authenticated workspace</span></div><button className="logout-button" type="button" onClick={handleLogout}>Sign out</button></div></header><div className="page-content">
    <section className="page-header"><span className="eyebrow">Data Ingestion</span><h1>Upload Dataset</h1><p>Upload business data for Alpha to extract and prepare for the processing pipeline.</p></section>
    {status !== "success" && <section className="upload-panel"><div className="panel-heading"><div><span className="step-number">01</span><div><h2>Select a dataset</h2><p>Your file stays on this device until you click Upload Dataset.</p></div></div><div className="secure-label"><svg viewBox="0 0 24 24"><rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>JWT protected</div></div><UploadZone onFileSelect={handleFileSelect} isDragging={isDragging} setIsDragging={setIsDragging} disabled={status === "uploading"}/></section>}
    {error && <div className="error-banner" role="alert"><span>!</span><div><strong>{status === "invalid" ? "File not accepted" : "Upload could not be completed"}</strong><p>{error}</p></div></div>}
    {selectedFile && status !== "success" && <FileCard file={selectedFile} onRemove={resetUpload} onUpload={handleUpload} isUploading={status === "uploading"}/>}
    {status === "success" && result && <IngestionResult response={result} selectedFile={selectedFile} onReset={resetUpload}/>} 
    <footer className="page-footer"><span>ALPHA / MODULES 01 + 02</span><span>Authentication + Data Ingestion</span></footer>
  </div></main></div>;
}
