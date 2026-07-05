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

  const input =
    "w-full bg-transparent px-3 py-2 text-sm text-espresso placeholder-muted/70 focus:outline-none ring-0";
  const label = "block text-xs font-medium text-cocoa mb-1";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-espresso/60 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-lg bg-card max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {!created ? (
          <form onSubmit={submit} className="p-6 space-y-4">
            <div>
              <h2 className="font-display text-xl font-semibold text-espresso">New project</h2>
              <p className="text-xs text-muted mt-0.5">
                A project isolates its own memory. You'll get a project_id to paste into your notebook or repo.
              </p>
            </div>

            <div>
              <label className={label}>Project name *</label>
              <input autoFocus className={input} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. ResNet CIFAR Sweep" />
            </div>

            <div className="border-t border-line pt-4">
              <div className="text-xs font-semibold text-cocoa uppercase tracking-wider mb-2">
                Weights & Biases <span className="text-muted normal-case font-normal">(optional — auto-syncs runs)</span>
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

            <div className="border-t border-line pt-4">
              <label className={label}>
                Significant config keys <span className="text-muted">(optional, comma-separated)</span>
              </label>
              <input className={input} value={sigKeys} onChange={(e) => setSigKeys(e.target.value)} placeholder="model, learning_rate, batch_size, optimizer" />
              <p className="text-xs text-muted mt-1">Only these define an experiment for the Pre-flight Guard; other keys (seed, paths…) are treated as noise.</p>
            </div>

            {error && <div className="text-sm text-terracotta bg-terracotta/10 border border-terracotta/25 rounded-xl p-2">{error}</div>}

            <div className="flex gap-2 justify-end pt-2">
              <button type="button" onClick={onClose} className="text-sm text-muted hover:text-cocoa px-3 py-2">Cancel</button>
              <button type="submit" disabled={busy || !name.trim()} className="bg-coffee hover:bg-coffee-deep disabled:opacity-40 text-card text-sm font-semibold px-4 py-2 rounded-xl transition-colors">
                {busy ? "Creating…" : "Create project"}
              </button>
            </div>
          </form>
        ) : (
          <div className="p-6 space-y-4">
            <div>
              <h2 className="font-display text-xl font-semibold text-olive">Project created</h2>
              <p className="text-xs text-muted mt-0.5">Paste this into your notebook or training script to start recording.</p>
            </div>

            <Field label="Project ID" value={created.project_id} onCopy={() => copy(created.project_id, "id")} copied={copied === "id"} />
            <Field label="Token" value={created.token} mono onCopy={() => copy(created.token, "tok")} copied={copied === "tok"} />

            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-cocoa">Connect via SDK</span>
                <button onClick={() => copy(snippet, "snip")} className="text-xs text-coffee hover:text-coffee-deep">{copied === "snip" ? "Copied!" : "Copy"}</button>
              </div>
              <pre className="bg-paper border border-line rounded-xl p-3 text-xs text-cocoa font-mono whitespace-pre-wrap break-all">{snippet}</pre>
            </div>

            {created.wandb?.configured && (
              <div className="bg-olive/10 border border-olive/20 rounded-xl p-3 text-xs text-olive font-medium">
                W&B auto-sync is enabled. Background polling will start automatically.
              </div>
            )}

            <div className="flex justify-end pt-2">
              <button onClick={openProject} className="bg-coffee hover:bg-coffee-deep text-card text-sm font-semibold px-4 py-2 rounded-xl transition-colors">Open project →</button>
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
        <span className="text-xs font-medium text-espresso">{label}</span>
        <button onClick={onCopy} className="text-xs text-coffee hover:text-coffee-deep">{copied ? "Copied!" : "Copy"}</button>
      </div>
      <code className={`block bg-transparent px-3 py-2 text-xs text-espresso break-all ${mono ? "font-mono" : ""}`}>{value}</code>
    </div>
  );
}
