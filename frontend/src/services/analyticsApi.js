const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

function queryString(filters = {}) {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== "") params.set(key, value);
  });
  const query = params.toString();
  return query ? `?${query}` : "";
}

async function request(path, token, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...options.headers
      }
    });
  } catch {
    throw new Error("Unable to reach the analytics server.");
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok || payload?.success === false) throw new Error(payload?.message || `Request failed (${response.status})`);
  return payload;
}

export function getAnalytics(section, filters, token) {
  return request(`/api/analytics/${section}${queryString(filters)}`, token);
}

export function getTraceability(metric, filters, token) {
  return request(`/api/analytics/trace/${metric}${queryString(filters)}`, token);
}

export { queryString };
