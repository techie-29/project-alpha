const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:5000";

export async function runTransformation(ingestionId, token) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/transformation/${ingestionId}/run`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` }
    });
  } catch {
    throw new Error("Unable to reach the transformation service.");
  }
  const payload = await response.json().catch(() => null);
  if (!response.ok || payload?.success === false) {
    throw new Error(payload?.message || `Transformation failed (${response.status})`);
  }
  return payload;
}
