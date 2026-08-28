const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

async function request(path, options = {}) {
  let response;

  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...options.headers,
      },
    });
  } catch {
    throw new Error("Unable to reach the backend. Make sure it is running on port 5000.");
  }

  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    const error = new Error(payload?.message || `Request failed (${response.status})`);
    error.status = response.status;
    throw error;
  }

  return payload;
}

export function registerBusiness(formData) {
  return request("/api/auth/register", {
    method: "POST",
    body: JSON.stringify(formData),
  });
}

export function loginBusiness(formData) {
  return request("/api/auth/login", {
    method: "POST",
    body: JSON.stringify(formData),
  });
}

export function getCurrentAccount(token) {
  return request("/api/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  });
}
