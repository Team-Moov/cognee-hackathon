/** API service — always calls the real FastAPI backend via /api prefix. */
const BASE = "/api";

// --- Current project (persisted) -------------------------------------------
// Every scoped call automatically carries the selected project_id so the whole
// dashboard shows one project's isolated memory. Empty = unscoped (all).
let _projectId = localStorage.getItem("gh_project") || "";
export function setCurrentProject(id) {
  _projectId = id || "";
  if (_projectId) localStorage.setItem("gh_project", _projectId);
  else localStorage.removeItem("gh_project");
}
export function getCurrentProject() {
  return _projectId;
}
function withProjectParams(params = {}) {
  const p = { ...params };
  if (_projectId) p.project_id = _projectId;
  return p;
}
function withProjectBody(body = {}) {
  return _projectId ? { ...body, project_id: _projectId } : body;
}

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

async function put(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${msg}`);
  }
  return res.json();
}

async function del(path) {
  const res = await fetch(`${BASE}${path}`, { method: "DELETE" });
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${msg}`);
  }
  return res.json();
}

// --- Projects ---
export async function listProjects() {
  return get("/projects");
}
export async function createProject(body) {
  return post("/projects", body);
}
export async function getProject(id) {
  return get(`/projects/${id}`);
}
export async function deleteProject(id) {
  return del(`/projects/${id}`);
}
export async function toggleWandbSync(id, enabled) {
  return put(`/projects/${id}/wandb/sync`, { enabled });
}
export async function setProjectWandb(id, { entity, project, api_key, default_dataset }) {
  return post(`/projects/${id}/wandb`, { entity, project, api_key, default_dataset });
}

// --- Insights + Graph (scoped) ---
export async function getInsights() {
  const qs = new URLSearchParams(withProjectParams()).toString();
  return get(`/insights${qs ? "?" + qs : ""}`);
}
export async function getGraph() {
  const qs = new URLSearchParams(withProjectParams()).toString();
  return get(`/graph${qs ? "?" + qs : ""}`);
}

// --- Runs (scoped) ---
export async function listRuns(params = {}) {
  const qs = new URLSearchParams(withProjectParams(params)).toString();
  return get(`/runs${qs ? "?" + qs : ""}`);
}
export async function rememberRun(data) {
  return post("/runs/remember", withProjectBody(data));
}
export async function checkConfig(config, experiment) {
  return post("/runs/check-config", withProjectBody({ config, experiment }));
}
export async function getLineage(runId) {
  return get(`/runs/lineage/${runId}`);
}
export async function deleteRun(runId) {
  return del(`/runs/${runId}`);
}

// --- Query (scoped) ---
export async function queryMemory(question, mode = "COMPLETION") {
  return post("/query", withProjectBody({ question, mode }));
}

// --- Files ---
export async function findFile(q) {
  return get(`/files/find?q=${encodeURIComponent(q)}`);
}
export async function getOrphans() {
  return get("/files/orphans");
}

// --- Agents (scoped) ---
export async function getAgentSuggestions(params = {}) {
  const qs = new URLSearchParams(withProjectParams(params)).toString();
  return get(`/agents/suggestions${qs ? "?" + qs : ""}`);
}
export async function dismissSuggestion(id) {
  return post(`/agents/suggestions/${id}/dismiss`, {});
}
export async function generateReport(experiment) {
  return post("/agents/report", withProjectBody({ experiment }));
}

// --- Health ---
export async function healthCheck() {
  return get("/health");
}
