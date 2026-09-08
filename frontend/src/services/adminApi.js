const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

async function adminRequest(path, token, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {}),
      },
    });
  } catch {
    throw new Error("Unable to reach the Project Alpha backend.");
  }

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const error = new Error(payload?.message || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return payload;
}

export const getAdminDashboard = (token) => adminRequest("/api/admin/dashboard", token);
export const getAdminUsers = (token) => adminRequest("/api/admin/users", token);
export const getAdminDatasets = (token) => adminRequest("/api/admin/datasets", token);
export const getAdminSystem = (token) => adminRequest("/api/admin/system", token);
export const getAdminActivity = (token) => adminRequest("/api/admin/activity", token);
export const getBusinessDatasets = (token, accountId) => adminRequest(`/api/admin/users/${accountId}/datasets`, token);
export const setBusinessStatus = (token, accountId, status) => adminRequest(`/api/admin/users/${accountId}/status`, token, { method: "PATCH", body: JSON.stringify({ status }) });
export const deleteBusiness = (token, accountId) => adminRequest(`/api/admin/users/${accountId}`, token, { method: "DELETE" });
export const getDatasetDetails = (token, datasetId) => adminRequest(`/api/admin/datasets/${datasetId}`, token);
export const deleteDataset = (token, datasetId) => adminRequest(`/api/admin/datasets/${datasetId}`, token, { method: "DELETE" });
