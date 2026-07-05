import React, { useEffect, useState } from "react";
import {
  listProjects,
  setCurrentProject,
  getCurrentProject,
  toggleWandbSync,
  deleteProject,
} from "../services/api";
import ProjectModal from "./ProjectModal";
import ProjectConnectInfo from "./ProjectConnectInfo";

/**
 * Project switcher + creator. Sits at the top of the sidebar.
 * Selecting or creating a project scopes the entire dashboard to that project's
 * isolated memory (project_id is attached to every API call). We reload on
 * change so all pages re-fetch cleanly.
 */
export default function ProjectBar({ collapsed = false }) {
  const [projects, setProjects] = useState([]);
  const [current, setCurrent] = useState(getCurrentProject());
  const [showModal, setShowModal] = useState(false);
  const [showConnect, setShowConnect] = useState(false);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listProjects()
      .then((d) => setProjects(d.projects || []))
      .catch(() => setProjects([]));
  }, []);

  function onSelect(e) {
    const id = e.target.value;
    setCurrentProject(id);
    setCurrent(id);
    window.location.reload();
  }

  const activeProject = projects.find((p) => p.project_id === current);

  async function onDelete() {
    if (!activeProject) return;
    if (
      !window.confirm(
        `Delete project "${activeProject.name}" and ALL its runs, findings, and insights? This cannot be undone.`,
      )
    )
      return;
    setBusy(true);
    try {
      await deleteProject(activeProject.project_id);
      setCurrentProject("");
      window.location.reload();
    } catch (err) {
      alert("Delete failed: " + err.message);
      setBusy(false);
    }
  }

  if (collapsed) {
    return (
      <div className="flex w-full justify-center border-b border-line px-2 py-3">
        <button
          onClick={() => setShowModal(true)}
          className="inline-flex h-11 w-11 items-center justify-center text-lg font-semibold text-cocoa transition hover:text-coffee"
          title="Create project"
          aria-label="Create project"
        >
          +
        </button>

        {showModal && <ProjectModal onClose={() => setShowModal(false)} />}
      </div>
    );
  }

  return (
    <div className="px-4 py-3">
      <div className="mb-2 text-[11px] font-semibold uppercase tracking-[0.24em] text-muted">
        Project
      </div>

      <div className="p-2">
        <select
          value={current}
          onChange={onSelect}
          className="w-full bg-transparent px-3 py-2 text-sm text-espresso outline-none ring-0"
        >
          <option value="">All memory</option>
          {projects.map((p) => (
            <option key={p.project_id} value={p.project_id}>
              {p.name}
            </option>
          ))}
        </select>
      </div>

      <button
        onClick={() => setShowModal(true)}
        className="mt-2 w-full rounded-2xl bg-slate-800 px-4 py-2 text-xs font-semibold text-slate-100 transition duration-200 hover:bg-slate-800/80"
      >
        + New project
      </button>

      {activeProject && (
        <div className="mt-3 flex gap-2">
          <button
            onClick={() => setShowConnect(true)}
            className="flex-1 rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-2 text-xs font-semibold text-sky-300 transition duration-200 hover:bg-slate-800"
          >
            Connect
          </button>
          <button
            onClick={onDelete}
            disabled={busy}
            className="flex-1 rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-2 text-xs font-semibold text-rose-300 transition duration-200 hover:bg-slate-800 disabled:opacity-50"
          >
            {busy ? "Deleting…" : "Delete"}
          </button>
        </div>
      )}

      {showConnect && activeProject && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
          onClick={() => setShowConnect(false)}
        >
          <div
            className="w-full max-w-lg bg-card p-6 max-h-[90vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-espresso">
                Connect to “{activeProject.name}”
              </h2>
              <button
                onClick={() => setShowConnect(false)}
                className="text-muted hover:text-cocoa"
              >
                ✕
              </button>
            </div>
            <ProjectConnectInfo project={activeProject} />
          </div>
        </div>
      )}

      {activeProject && activeProject.wandb?.configured && (
        <div className="mt-3 flex items-center justify-between px-2 py-2">
          <div className="flex flex-col">
            <span className="text-xs font-semibold text-espresso">
              W&B Auto-Sync
            </span>
            <span className="mt-0.5 text-[10px] leading-tight text-stone-500">
              Polls in background
            </span>
          </div>
          <button
            onClick={async () => {
              const newState = !activeProject.wandb.sync_enabled;
              await toggleWandbSync(activeProject.project_id, newState);
              setProjects(
                projects.map((p) =>
                  p.project_id === activeProject.project_id
                    ? { ...p, wandb: { ...p.wandb, sync_enabled: newState } }
                    : p,
                ),
              );
            }}
            className={`relative inline-flex h-5 w-9 items-center transition-colors ${activeProject.wandb.sync_enabled ? "bg-espresso/60" : "bg-paper/20"}`}
          >
            <span
              className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${activeProject.wandb.sync_enabled ? "translate-x-5" : "translate-x-1"}`}
            />
          </button>
        </div>
      )}

      {showModal && <ProjectModal onClose={() => setShowModal(false)} />}
    </div>
  );
}
