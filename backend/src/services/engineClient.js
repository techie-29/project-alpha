/** Thin HTTP client for the Python engine. URL and key come from the environment (placeholders in .env.example). */
function createEngineClient({ baseUrl = process.env.ENGINE_URL || "http://127.0.0.1:8001", apiKey = process.env.ENGINE_API_KEY || "", fetchImpl = fetch } = {}) {
  async function call(method, path, body) {
    let response;
    try {
      response = await fetchImpl(`${baseUrl}${path}`, {
        method,
        headers: { "content-type": "application/json", "x-engine-key": apiKey },
        body: body === undefined ? undefined : JSON.stringify(body)
      });
    } catch (cause) {
      const error = new Error("The analysis engine is not reachable. Make sure it is running.");
      error.status = 503;
      error.expose = true;
      throw error;
    }
    if (!response.ok) {
      let detail = "";
      try { detail = (await response.json()).detail || ""; } catch { /* ignore */ }
      const error = new Error(detail || `The analysis engine answered ${response.status}`);
      error.status = response.status === 404 ? 404 : response.status >= 500 ? 502 : 400;
      error.expose = true;
      throw error;
    }
    return response.json();
  }
  return {
    read: (body) => call("POST", "/v1/read", body),
    analyze: (body) => call("POST", "/v1/analyze", body),
    job: (id) => call("GET", `/v1/jobs/${encodeURIComponent(id)}`),
    report: (id) => call("GET", `/v1/reports/${encodeURIComponent(id)}`),
    health: () => call("GET", "/v1/health")
  };
}

module.exports = { createEngineClient };
