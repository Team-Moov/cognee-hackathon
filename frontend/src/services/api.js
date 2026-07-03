/** API service — always calls the real FastAPI backend via /api prefix. */
const BASE = "/api";

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${msg}`);
  }
  return res.json();
}

async function get(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${msg}`);
  }
  return res.json();
}

// --- Runs ---
export async function listRuns(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return get(`/runs${qs ? "?" + qs : ""}`);
}
export async function rememberRun(data) {
  return post("/runs/remember", data);
}
export async function checkConfig(config, experiment) {
  return post("/runs/check-config", { config, experiment });
}
export async function getLineage(runId) {
  return get(`/runs/lineage/${runId}`);
}

// --- Query ---
export async function queryMemory(question, mode = "COMPLETION") {
  return post("/query", { question, mode });
}

// --- Files ---
export async function findFile(q) {
  return get(`/files/find?q=${encodeURIComponent(q)}`);
}
export async function getOrphans() {
  return get("/files/orphans");
}

// --- Agents ---
export async function getAgentSuggestions(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return get(`/agents/suggestions${qs ? "?" + qs : ""}`);
}
export async function dismissSuggestion(id) {
  return post(`/agents/suggestions/${id}/dismiss`, {});
}
export async function generateReport(experiment) {
  return post("/agents/report", { experiment });
}

// --- Health ---
export async function healthCheck() {
  return get("/health");
}
