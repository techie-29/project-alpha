const API = (import.meta.env.VITE_API_BASE_URL || "http://localhost:5000") + "/api/alpha";

async function request(path, token, { method = "GET", body } = {}) {
  let response;
  try {
    response = await fetch(`${API}${path}`, {
      method,
      headers: { Authorization: `Bearer ${token}`, ...(body ? { "Content-Type": "application/json" } : {}) },
      body: body ? JSON.stringify(body) : undefined
    });
  } catch {
    throw new Error("Unable to reach the server. Make sure the backend is running.");
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok || payload?.success === false) {
    const error = new Error(payload?.message || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return payload;
}

export const listFiles = (token) => request("/files", token).then((r) => r.files);
export const deleteFile = (id, token) => request(`/files/${id}`, token, { method: "DELETE" });
export const readFiles = (fileIds, confirmations, token) => request("/read", token, { method: "POST", body: { fileIds, confirmations } }).then((r) => r.reading);
export const startAnalysis = (fileIds, confirmations, token) => request("/analyses", token, { method: "POST", body: { fileIds, confirmations } }).then((r) => r.id);
export const listAnalyses = (token) => request("/analyses", token).then((r) => r.analyses);
export const getAnalysis = (id, token) => request(`/analyses/${id}`, token).then((r) => r.analysis);
export const getReport = (id, token) => request(`/analyses/${id}/report`, token).then((r) => r.report);
export const sendFeedback = (id, findingId, verdict, token) => request(`/analyses/${id}/feedback`, token, { method: "POST", body: { findingId, verdict } });
export const sendAnswer = (id, questionId, answer, token) => request(`/analyses/${id}/answers`, token, { method: "POST", body: { questionId, answer } });

/** Upload files with progress (fetch cannot report upload progress). */
export function uploadFiles(files, token, onProgress = () => {}) {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API}/files`);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.upload.addEventListener("progress", (e) => e.lengthComputable && onProgress(Math.round((e.loaded / e.total) * 100)));
    xhr.addEventListener("load", () => {
      let payload = null;
      try { payload = JSON.parse(xhr.responseText); } catch { /* not json */ }
      if (xhr.status >= 200 && xhr.status < 300 && payload?.success) return resolve(payload.files);
      reject(new Error(payload?.message || `Upload failed (${xhr.status})`));
    });
    xhr.addEventListener("error", () => reject(new Error("Unable to reach the server. Make sure the backend is running.")));
    xhr.send(form);
  });
}
export const askAlpha = (id, question, token) => request(`/analyses/${id}/ask`, token, { method: "POST", body: { question } }).then((r) => r.result);
