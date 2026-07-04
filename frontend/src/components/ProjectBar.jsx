import React, { useEffect, useState } from "react";
import { listProjects, setCurrentProject, getCurrentProject } from "../services/api";
import ProjectModal from "./ProjectModal";

/**
 * Project switcher + creator. Sits at the top of the sidebar.
 * Selecting or creating a project scopes the entire dashboard to that project's
 * isolated memory (project_id is attached to every API call). We reload on
 * change so all pages re-fetch cleanly.
 */
export default function ProjectBar() {
  const [projects, setProjects] = useState([]);
  const [current, setCurrent] = useState(getCurrentProject());
  const [showModal, setShowModal] = useState(false);

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

  return (
    <div className="px-4 py-3 border-b border-zinc-800">
      <div className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-1.5">
        Project
      </div>
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
        onClick={() => setShowModal(true)}
        className="mt-2 w-full text-xs text-indigo-400 hover:text-indigo-300 border border-indigo-500/30 rounded-lg py-1.5 hover:bg-indigo-600/10 transition-colors"
      >
        + New project
      </button>

      {showModal && <ProjectModal onClose={() => setShowModal(false)} />}
    </div>
  );
}
