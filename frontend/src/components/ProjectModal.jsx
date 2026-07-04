import React, { useState } from "react";
import { createProject, setCurrentProject } from "../services/api";

/**
 * New-project modal: collects a name, optional W&B credentials, and optional
 * "significant" config keys — then shows the generated project_id + token and a
 * ready-to-paste SDK snippet so the researcher can connect their notebook/repo.
 */
export default function ProjectModal({ onClose }) {
  const [name, setName] = useState("");
  const [wbEntity, setWbEntity] = useState("");
  const [wbProject, setWbProject] = useState("");
  const [wbKey, setWbKey] = useState("");
  const [sigKeys, setSigKeys] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [created, setCreated] = useState(null);
  const [copied, setCopied] = useState("");

  async function submit(e) {
    e.preventDefault();
    if (!name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const body = { name: name.trim() };
      if (wbEntity.trim()) body.wandb_entity = wbEntity.trim();
      if (wbProject.trim()) body.wandb_project = wbProject.trim();
      if (wbKey.trim()) body.wandb_api_key = wbKey.trim();
      const sk = sigKeys.split(",").map((s) => s.trim()).filter(Boolean);
      if (sk.length) body.significant_keys = sk;
      const proj = await createProject(body);
      setCreated(proj);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  function copy(text, tag) {
    navigator.clipboard?.writeText(text);
    setCopied(tag);
    setTimeout(() => setCopied(""), 1500);
  }

  function openProject() {
    setCurrentProject(created.project_id);
    window.location.reload();
  }

  const snippet = created
    ? `import groundhog\ngroundhog.init(project_id="${created.project_id}")`
    : "";
  const daemonCmd = created
    ? `python connectors/wandb_sync.py --project-id ${created.project_id} --watch --interval 60`
    : "";

  const input =
    "w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-indigo-500";
  const label = "block text-xs font-medium text-zinc-400 mb-1";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg bg-zinc-900 border border-zinc-700 rounded-2xl shadow-2xl max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {!created ? (
          <form onSubmit={submit} className="p-6 space-y-4">
            <div>
              <h2 className="text-lg font-bold text-zinc-100">New project</h2>
              <p className="text-xs text-zinc-500 mt-0.5">
                A project isolates its own memory. You'll get a project_id to paste into your notebook or repo.
              </p>
            </div>

            <div>
              <label className={label}>Project name *</label>
              <input autoFocus className={input} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. ResNet CIFAR Sweep" />
            </div>

            <div className="border-t border-zinc-800 pt-4">
              <div className="text-xs font-semibold text-zinc-400 uppercase tracking-wider mb-2">
                Weights & Biases <span className="text-zinc-600 normal-case font-normal">(optional — auto-syncs runs)</span>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className={label}>W&B entity</label>
                  <input className={input} value={wbEntity} onChange={(e) => setWbEntity(e.target.value)} placeholder="username / team" />
                </div>
                <div>
                  <label className={label}>W&B project</label>
                  <input className={input} value={wbProject} onChange={(e) => setWbProject(e.target.value)} placeholder="project name" />
                </div>
              </div>
              <div className="mt-3">
                <label className={label}>W&B API key</label>
                <input type="password" className={input} value={wbKey} onChange={(e) => setWbKey(e.target.value)} placeholder="stored locally on your machine" />
              </div>
            </div>

            <div className="border-t border-zinc-800 pt-4">
              <label className={label}>
                Significant config keys <span className="text-zinc-600">(optional, comma-separated)</span>
              </label>
              <input className={input} value={sigKeys} onChange={(e) => setSigKeys(e.target.value)} placeholder="model, learning_rate, batch_size, optimizer" />
              <p className="text-xs text-zinc-600 mt-1">Only these define an experiment for the Pre-flight Guard; other keys (seed, paths…) are treated as noise.</p>
            </div>

            {error && <div className="text-sm text-red-400 bg-red-950/30 border border-red-500/20 rounded-lg p-2">{error}</div>}

            <div className="flex gap-2 justify-end pt-2">
              <button type="button" onClick={onClose} className="text-sm text-zinc-400 hover:text-zinc-200 px-3 py-2">Cancel</button>
              <button type="submit" disabled={busy || !name.trim()} className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">
                {busy ? "Creating…" : "Create project"}
              </button>
            </div>
          </form>
        ) : (
          <div className="p-6 space-y-4">
            <div>
              <h2 className="text-lg font-bold text-emerald-400">✓ Project created</h2>
              <p className="text-xs text-zinc-500 mt-0.5">Paste this into your notebook or training script to start recording.</p>
            </div>

            <Field label="Project ID" value={created.project_id} onCopy={() => copy(created.project_id, "id")} copied={copied === "id"} />
            <Field label="Token" value={created.token} mono onCopy={() => copy(created.token, "tok")} copied={copied === "tok"} />

            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-zinc-400">Connect via SDK</span>
                <button onClick={() => copy(snippet, "snip")} className="text-xs text-indigo-400 hover:text-indigo-300">{copied === "snip" ? "Copied!" : "Copy"}</button>
              </div>
              <pre className="bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-xs text-zinc-200 font-mono whitespace-pre-wrap break-all">{snippet}</pre>
            </div>

            {created.wandb?.configured && (
              <div>
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-medium text-zinc-400">Or auto-sync from W&B</span>
                  <button onClick={() => copy(daemonCmd, "daemon")} className="text-xs text-indigo-400 hover:text-indigo-300">{copied === "daemon" ? "Copied!" : "Copy"}</button>
                </div>
                <pre className="bg-zinc-950 border border-zinc-800 rounded-lg p-3 text-xs text-zinc-200 font-mono whitespace-pre-wrap break-all">{daemonCmd}</pre>
              </div>
            )}

            <div className="flex justify-end pt-2">
              <button onClick={openProject} className="bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors">Open project →</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function Field({ label, value, onCopy, copied, mono }) {
  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-xs font-medium text-zinc-400">{label}</span>
        <button onClick={onCopy} className="text-xs text-indigo-400 hover:text-indigo-300">{copied ? "Copied!" : "Copy"}</button>
      </div>
      <code className={`block bg-zinc-950 border border-zinc-800 rounded-lg px-3 py-2 text-xs text-zinc-200 break-all ${mono ? "font-mono" : ""}`}>{value}</code>
    </div>
  );
}
