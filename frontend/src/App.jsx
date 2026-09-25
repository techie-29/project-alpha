"use client";

import { useEffect, useMemo, useState } from "react";
import AuthPage from "./components/AuthPage";
import Sidebar from "./components/Sidebar";
import UploadZone from "./components/UploadZone";
import UploadQueue from "./components/UploadQueue";
import IngestionResult from "./components/IngestionResult";
import HeaderMappingWorkspace from "./components/HeaderMappingWorkspace";
import ValidationWorkspace from "./components/ValidationWorkspace";
import TransformationWorkspace from "./components/TransformationWorkspace";
import AdminPanel from "./components/AdminPanel";
import { getCurrentAccount } from "./services/authApi";
import { uploadDatasetBatch } from "./services/uploadApi";
import { makeQueueItems, MAX_BATCH_FILES } from "./utils/uploadQueue";

const TOKEN_KEY = "alphaToken";

export default function App() {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [account, setAccount] = useState(null);
  const [authStatus, setAuthStatus] = useState(token ? "checking" : "signed-out");
  const [queue, setQueue] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isBusy, setIsBusy] = useState(false);
  const [error, setError] = useState("");
  const [batch, setBatch] = useState(null);
  const [activeResultId, setActiveResultId] = useState(null);
  const [mappingTargetId, setMappingTargetId] = useState(null);
  const [validationTargetId, setValidationTargetId] = useState(null);
  const [transformationTargetId, setTransformationTargetId] = useState(null);

  useEffect(() => {
    if (!token) return;
    let active = true;
    getCurrentAccount(token).then((response) => {
      if (!active) return;
      setAccount(response.data.account);
      setAuthStatus("signed-in");
    }).catch(() => {
      if (!active) return;
      localStorage.removeItem(TOKEN_KEY);
      setToken(null);
      setAccount(null);
      setAuthStatus("signed-out");
    });
    return () => { active = false; };
  }, [token]);

  const activeResult = useMemo(
    () => queue.find((item) => item.id === activeResultId && item.response),
    [activeResultId, queue]
  );

  function handleAuthenticated(authData) {
    localStorage.setItem(TOKEN_KEY, authData.token);
    setToken(authData.token);
    setAccount(authData.account);
    setAuthStatus("signed-in");
  }

  function resetUpload() {
    setQueue([]);
    setError("");
    setBatch(null);
    setActiveResultId(null);
    setMappingTargetId(null);
    setValidationTargetId(null);
    setTransformationTargetId(null);
    setIsBusy(false);
    setIsDragging(false);
  }

  function handleLogout() {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setAccount(null);
    setAuthStatus("signed-out");
    resetUpload();
  }

  function handleFilesSelect(files) {
    const items = makeQueueItems(files);
    setQueue(items);
    setBatch(null);
    setActiveResultId(null);
    setMappingTargetId(null);
    setValidationTargetId(null);
    setTransformationTargetId(null);
    setError(files.length > MAX_BATCH_FILES
      ? `Only the first ${MAX_BATCH_FILES} files were added to this batch.`
      : "");
  }

  function removeQueueItem(itemId) {
    setQueue((items) => items.filter((item) => item.id !== itemId));
    if (activeResultId === itemId) setActiveResultId(null);
    if (mappingTargetId === itemId) setMappingTargetId(null);
    if (validationTargetId === itemId) setValidationTargetId(null);
    if (transformationTargetId === itemId) setTransformationTargetId(null);
  }

  function viewQueueResult(itemId) {
    setActiveResultId(itemId);
    setMappingTargetId(null);
    setValidationTargetId(null);
    setTransformationTargetId(null);
  }

  async function handleBatchUpload() {
    const uploadableItems = queue.filter((item) => item.status === "queued");
    if (!uploadableItems.length) return;

    const uploadIds = new Set(uploadableItems.map((item) => item.id));
    setIsBusy(true);
    setError("");
    setActiveResultId(null);
    setMappingTargetId(null);
    setValidationTargetId(null);
    setTransformationTargetId(null);
    setQueue((items) => items.map((item) => uploadIds.has(item.id)
      ? { ...item, status: "uploading", progress: 0, error: "" }
      : item));

    try {
      const response = await uploadDatasetBatch(
        uploadableItems.map((item) => item.file),
        token,
        (progress) => setQueue((items) => items.map((item) => {
          if (!uploadIds.has(item.id)) return item;
          return {
            ...item,
            progress,
            status: progress >= 100 ? "processing" : "uploading"
          };
        }))
      );

      const resultsById = new Map();
      response.data.items.forEach((result) => {
        const queueItem = uploadableItems[result.fileIndex];
        if (queueItem) resultsById.set(queueItem.id, result);
      });

      setQueue((items) => items.map((item) => {
        const result = resultsById.get(item.id);
        if (!result) {
          return uploadIds.has(item.id)
            ? { ...item, status: "failed", error: "The server did not return a result for this file." }
            : item;
        }
        if (result.status === "completed") {
          return {
            ...item,
            status: "completed",
            progress: 100,
            response: { success: true, data: result.data },
            error: ""
          };
        }
        return {
          ...item,
          status: "failed",
          progress: 100,
          error: result.error?.message || "This file could not be processed."
        };
      }));

      setBatch(response.data.batch);
      const firstCompleted = response.data.items.find((item) => item.status === "completed");
      if (firstCompleted) setActiveResultId(uploadableItems[firstCompleted.fileIndex]?.id || null);
    } catch (uploadError) {
      setQueue((items) => items.map((item) => uploadIds.has(item.id)
        ? { ...item, status: "failed", error: uploadError.message }
        : item));
      setError(uploadError.message || "The upload batch could not be completed.");
    } finally {
      setIsBusy(false);
    }
  }

  if (authStatus === "checking") {
    return <div className="auth-loading">Checking your session...</div>;
  }
  if (authStatus !== "signed-in") {
    return <AuthPage onAuthenticated={handleAuthenticated}/>;
  }
  if (account?.role === "admin") {
    return <AdminPanel token={token} account={account} onLogout={handleLogout}/>;
  }

  const accountLabel = account?.businessName || account?.email || "Business Account";
  const initials = accountLabel.slice(0, 2).toUpperCase();

  return <div className="app-shell">
    <Sidebar/>
    <main className="main-content">
      <header className="topbar">
        <div className="mobile-brand"><span>A</span>Alpha</div>
        <div className="account-area">
          <div className="account-avatar">{initials}</div>
          <div><strong>{accountLabel}</strong><span><i/>Authenticated workspace</span></div>
          <button className="logout-button" type="button" onClick={handleLogout}>Sign out</button>
        </div>
      </header>

      <div className="page-content">
        <section className="page-header">
          <span className="eyebrow">Data Ingestion</span>
          <h1>Upload Dataset Batch</h1>
          <p>Select sales, inventory, customer, product, or supplier files. Alpha processes each file independently and never merges them blindly.</p>
        </section>

        {queue.length === 0 && <section className="upload-panel">
          <div className="panel-heading"><div><span className="step-number">01</span><div><h2>Select datasets</h2><p>Files stay on this device until you start the batch.</p></div></div><div className="secure-label"><svg viewBox="0 0 24 24"><rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>JWT protected</div></div>
          <UploadZone onFilesSelect={handleFilesSelect} isDragging={isDragging} setIsDragging={setIsDragging} disabled={isBusy}/>
        </section>}

        {error && <div className="error-banner" role="alert"><span>!</span><div><strong>Batch notice</strong><p>{error}</p></div></div>}

        {queue.length > 0 && <UploadQueue
          items={queue}
          onRemove={removeQueueItem}
          onUpload={handleBatchUpload}
          onViewResult={viewQueueResult}
          isBusy={isBusy}
        />}

        {batch && <section className={`batch-summary batch-${batch.status}`}>
          <div><span className="eyebrow">Batch #{batch.id}</span><h2>{batch.status === "completed" ? "All files are ready for mapping" : "Batch completed with file-level issues"}</h2></div>
          <div className="batch-counts"><span><strong>{batch.completedFiles}</strong> completed</span><span><strong>{batch.failedFiles}</strong> failed</span><span><strong>{batch.totalFiles}</strong> total</span></div>
          <button className="secondary-button" type="button" onClick={resetUpload}>Start another batch</button>
        </section>}

        {activeResult && <IngestionResult
          response={activeResult.response}
          selectedFile={activeResult.file}
          onReset={resetUpload}
          onContinueToMapping={() => {
            setMappingTargetId(activeResult.id);
            setValidationTargetId(null);
            setTransformationTargetId(null);
          }}
        />}

        {activeResult && mappingTargetId === activeResult.id && <HeaderMappingWorkspace
          ingestionId={activeResult.response.data.handoff.ingestionId}
          token={token}
          onConfirmed={() => setValidationTargetId(activeResult.id)}
        />}

        {activeResult && validationTargetId === activeResult.id && <ValidationWorkspace
          ingestionId={activeResult.response.data.handoff.ingestionId}
          token={token}
          onContinue={() => setTransformationTargetId(activeResult.id)}
        />}

        {activeResult && transformationTargetId === activeResult.id && <TransformationWorkspace
          ingestionId={activeResult.response.data.handoff.ingestionId}
          token={token}
        />}

        <footer className="page-footer"><span>ALPHA / MODULES 01–06</span><span>Authentication through Structured Storage</span></footer>
      </div>
    </main>
  </div>;
}
