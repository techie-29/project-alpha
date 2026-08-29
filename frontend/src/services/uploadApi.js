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
