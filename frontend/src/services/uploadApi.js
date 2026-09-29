const DEFAULT_UPLOAD_URL = "http://localhost:5000/api/upload";

export const UPLOAD_API_URL = import.meta.env.VITE_UPLOAD_API_URL || DEFAULT_UPLOAD_URL;

export async function uploadDataset(file, jwtToken) {
  const formData = new FormData();
  formData.append("file", file);

  const headers = {};
  if (jwtToken) headers.Authorization = `Bearer ${jwtToken}`;

  let response;
  try {
    response = await fetch(UPLOAD_API_URL, { method: "POST", headers, body: formData });
  } catch {
    throw new Error("Unable to reach the upload server. Make sure the backend is running on port 5000.");
  }

  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) {
    const error = new Error(payload?.message || payload?.error || `Upload failed (${response.status}). Please try again.`);
    error.status = response.status;
    throw error;
  }
  if (!payload) throw new Error("The server returned an empty or unreadable response.");
  if (payload.success === false) {
    throw new Error(payload.message || payload.error || "The server could not ingest this dataset.");
  }
  return payload;
}

function parseXhrPayload(xhr) {
  try {
    return xhr.responseText ? JSON.parse(xhr.responseText) : null;
  } catch {
    return null;
  }
}

export function uploadDatasetBatch(files, jwtToken, onProgress = () => {}) {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));

  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${UPLOAD_API_URL}/batch`);
    if (jwtToken) xhr.setRequestHeader("Authorization", `Bearer ${jwtToken}`);

    xhr.upload.addEventListener("progress", (event) => {
      if (!event.lengthComputable) return;
      onProgress(Math.min(100, Math.round((event.loaded / event.total) * 100)));
    });

    xhr.addEventListener("load", () => {
      const payload = parseXhrPayload(xhr);
      if (xhr.status < 200 || xhr.status >= 300 || payload?.success === false) {
        const error = new Error(
          payload?.message || `Batch upload failed (${xhr.status}). Please try again.`
        );
        error.status = xhr.status;
        error.code = payload?.code;
        error.details = payload?.details;
        reject(error);
        return;
      }
      if (!payload) {
        reject(new Error("The server returned an empty or unreadable response."));
        return;
      }
      resolve(payload);
    });

    xhr.addEventListener("error", () => {
      reject(new Error("Unable to reach the upload server. Make sure the backend is running on port 5000."));
    });

    xhr.send(formData);
  });
}

export async function getUploadBatch(batchId, jwtToken) {
  const response = await fetch(`${UPLOAD_API_URL}/batches/${batchId}`, {
    headers: jwtToken ? { Authorization: `Bearer ${jwtToken}` } : {}
  });
  const payload = await response.json().catch(() => null);
  if (!response.ok || payload?.success === false) {
    throw new Error(payload?.message || "Could not load batch progress");
  }
  return payload;
}
