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
    <div className="border-b border-line px-4 py-3">
      <div className="mb-1.5 text-xs font-semibold uppercase tracking-wider text-muted">
        Project
      </div>
      <select
        value={current}
        onChange={onSelect}
        className="w-full rounded-xl border border-line bg-paper px-2.5 py-2 text-sm text-cocoa focus:border-coffee focus:outline-none focus:ring-2 focus:ring-coffee/20"
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
        className="mt-2 w-full rounded-xl border border-line py-2 text-xs font-semibold text-coffee transition-colors hover:bg-sand"
      >
        + New project
      </button>

      {showModal && <ProjectModal onClose={() => setShowModal(false)} />}
    </div>
  );
}
