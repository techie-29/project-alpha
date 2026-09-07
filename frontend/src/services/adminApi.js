const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

async function adminRequest(path, token) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      headers: { Authorization: `Bearer ${token}` },
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
