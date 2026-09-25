const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

async function mappingRequest(ingestionId, token, options = {}) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/header-mapping/${ingestionId}`, {
      ...options,
      headers: {
        Authorization: `Bearer ${token}`,
        ...(options.body ? { "Content-Type": "application/json" } : {}),
        ...(options.headers || {})
      }
    });
  } catch {
    throw new Error("Unable to reach the header-mapping service.");
  }

  const payload = await response.json().catch(() => null);
  if (!response.ok || payload?.success === false) {
    const error = new Error(payload?.message || `Header mapping failed (${response.status})`);
    error.status = response.status;
    error.code = payload?.code;
    throw error;
  }
  return payload;
}

export function getHeaderMappingWorkspace(ingestionId, token) {
  return mappingRequest(ingestionId, token);
}

export function confirmHeaderMapping(ingestionId, mappings, saveTemplate, token) {
  return mappingRequest(ingestionId, token, {
    method: "PUT",
    body: JSON.stringify({ mappings, saveTemplate })
  });
}

// Kept for callers from the original Module 3 implementation.
export function runHeaderMapping(ingestionId, token = localStorage.getItem("alphaToken")) {
  return getHeaderMappingWorkspace(ingestionId, token);
}
