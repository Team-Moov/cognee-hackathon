import React, { useEffect, useState } from "react";
import { listProjects, createProject, setCurrentProject, getCurrentProject } from "../services/api";

/**
 * Project switcher + creator. Sits at the top of the sidebar.
 * Selecting or creating a project scopes the entire dashboard to that project's
 * isolated memory (project_id is attached to every API call). We reload on
 * change so all pages re-fetch cleanly.
 */
export default function ProjectBar() {
  const [projects, setProjects] = useState([]);
  const [current, setCurrent] = useState(getCurrentProject());
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");

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

  async function onCreate() {
    if (!name.trim()) return;
    try {
      const proj = await createProject({ name: name.trim() });
      setCurrentProject(proj.project_id);
      window.location.reload();
    } catch (err) {
      alert("Failed to create project: " + err.message);
    }
  }

  return (
    <div className="px-4 py-3 border-b border-zinc-800">
      <div className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">
        Project
      </div>
      {!creating ? (
        <>
          <select
            value={current}
            onChange={onSelect}
            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-2.5 py-1.5 text-sm text-zinc-100 focus:outline-none focus:border-indigo-500"
          >
            <option value="">All memory (unscoped)</option>
            {projects.map((p) => (
              <option key={p.project_id} value={p.project_id}>
                {p.name}
              </option>
            ))}
          </select>
          <button
            onClick={() => setCreating(true)}
            className="mt-2 w-full text-xs text-indigo-400 hover:text-indigo-300 border border-indigo-500/30 rounded-lg py-1.5 hover:bg-indigo-600/10 transition-colors"
          >
            + New project
          </button>
        </>
      ) : (
        <div className="space-y-2">
          <input
            autoFocus
            value={name}
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onCreate()}
            placeholder="Project name…"
            className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-2.5 py-1.5 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
          />
          <div className="flex gap-2">
            <button
              onClick={onCreate}
              className="flex-1 text-xs bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg py-1.5 transition-colors"
            >
              Create
            </button>
            <button
              onClick={() => { setCreating(false); setName(""); }}
              className="text-xs text-zinc-400 hover:text-zinc-200 px-2"
            >
              Cancel
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
