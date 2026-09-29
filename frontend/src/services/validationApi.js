const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

async function requestValidation(ingestionId, token, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/validation/${ingestionId}${options.path || ""}`, {
      method: options.method || "GET",
      headers: { Authorization: `Bearer ${token}` }
    });
  } catch {
    throw new Error("Unable to reach the validation service.");
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok || payload?.success === false) {
    throw new Error(payload?.message || `Validation failed (${response.status})`);
  }
  return payload;
}

export function runValidation(ingestionId, token) {
  return requestValidation(ingestionId, token, { path: "/run", method: "POST" });
}

export function getValidationResult(ingestionId, token) {
  return requestValidation(ingestionId, token);
}
