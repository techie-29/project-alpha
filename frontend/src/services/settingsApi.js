const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

async function request(path, token, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), Authorization: `Bearer ${token}` }
  }).catch(() => { throw new Error("Unable to reach the settings server."); });
  const payload = await response.json().catch(() => null);
  if (!response.ok || payload?.success === false) throw new Error(payload?.message || `Request failed (${response.status})`);
  return payload;
}

export const getSettings = (token) => request("/api/settings", token);
export const updateSettings = (body, token) => request("/api/settings", token, { method: "PATCH", body: JSON.stringify(body) });
export const changePassword = (body, token) => request("/api/settings/password", token, { method: "PATCH", body: JSON.stringify(body) });
