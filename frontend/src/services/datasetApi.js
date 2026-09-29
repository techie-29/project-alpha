const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

async function request(path, token, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: {
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    }
  }).catch(() => { throw new Error("Unable to reach the dataset server."); });
  const payload = await response.json().catch(() => null);
  if (!response.ok || payload?.success === false) throw new Error(payload?.message || `Request failed (${response.status})`);
  return payload;
}

export const getDatasets = (token) => request("/api/datasets", token);
export const getDataset = (id, token) => request(`/api/datasets/${id}`, token);
export const setDatasetIncluded = (id, included, token) => request(`/api/datasets/${id}/inclusion`, token, {
  method: "PATCH", body: JSON.stringify({ included })
});

export async function exportDatasetFile(id, type, format, token) {
  const response = await fetch(`${API_BASE_URL}/api/datasets/${id}/export?type=${encodeURIComponent(type)}&format=${encodeURIComponent(format)}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {}
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.message || "Dataset export failed");
  }
  const disposition = response.headers.get("content-disposition") || "";
  const filename = disposition.match(/filename="([^"]+)"/)?.[1] || `dataset-${id}.${format}`;
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a"); link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url);
}
