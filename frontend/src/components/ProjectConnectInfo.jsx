import React, { useState } from "react";
import { setProjectWandb } from "../services/api";

/**
 * Reusable "how to connect to this project" panel — project_id, token, SDK
 * snippet, a W&B credential form (attach/update creds on an EXISTING project),
 * and the W&B daemon command. Used right after creation and later via the
 * "Connect" button, so the id/token are always retrievable.
 */
export default function ProjectConnectInfo({ project }) {
  const [copied, setCopied] = useState("");
  function copy(text, tag) {
    navigator.clipboard?.writeText(text);
    setCopied(tag);
    setTimeout(() => setCopied(""), 1500);
  }

  const snippet = `import groundhog\ngroundhog.init(project_id="${project.project_id}")`;
  const daemonCmd = `python connectors/wandb_sync.py --project-id ${project.project_id} --watch --interval 60`;

  return (
    <div className="space-y-4">
      <Field label="Project ID" value={project.project_id} mono onCopy={() => copy(project.project_id, "id")} copied={copied === "id"} />
      {project.token && (
        <Field label="Token" value={project.token} mono onCopy={() => copy(project.token, "tok")} copied={copied === "tok"} />
      )}
      <Block label="Connect via SDK" text={snippet} onCopy={() => copy(snippet, "snip")} copied={copied === "snip"} />

      <WandbConnect project={project} />

      {project.wandb?.configured && (
        <Block label="Or auto-sync from W&B (CLI)" text={daemonCmd} onCopy={() => copy(daemonCmd, "daemon")} copied={copied === "daemon"} />
      )}
    </div>
  );
}

function WandbConnect({ project }) {
  const wb = project.wandb || {};
  const [entity, setEntity] = useState(wb.entity || "");
  const [proj, setProj] = useState(wb.project || "");
  const [apiKey, setApiKey] = useState("");
  const [defaultDataset, setDefaultDataset] = useState(wb.default_dataset || "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const input =
    "w-full bg-paper border border-line rounded-lg px-3 py-2 text-xs text-cocoa placeholder-muted/70 focus:outline-none focus:border-coffee focus:ring-2 focus:ring-coffee/20";

  async function save() {
    if (!proj.trim() || !apiKey.trim()) {
      setError("W&B project and API key are required.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      await setProjectWandb(project.project_id, {
        entity: entity.trim() || null,
        project: proj.trim(),
        api_key: apiKey.trim(),
        default_dataset: defaultDataset.trim() || null,
      });
      window.location.reload(); // re-fetch so sync toggle + status appear
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-line bg-sand/40 p-3">
      <div className="mb-2 flex items-center justify-between">
        <span className="text-xs font-semibold text-espresso">Weights &amp; Biases</span>
        {wb.configured ? (
          <span className="rounded-full bg-olive/15 px-2 py-0.5 text-[10px] font-semibold text-olive">
            connected{wb.sync_enabled ? " · auto-sync on" : ""}
          </span>
        ) : (
          <span className="text-[10px] text-muted">not connected</span>
        )}
      </div>
      <div className="grid grid-cols-2 gap-2">
        <input className={input} value={entity} onChange={(e) => setEntity(e.target.value)} placeholder="entity (optional)" />
        <input className={input} value={proj} onChange={(e) => setProj(e.target.value)} placeholder="project name" />
      </div>
      <input
        type="password"
        className={`${input} mt-2`}
        value={apiKey}
        onChange={(e) => setApiKey(e.target.value)}
        placeholder={wb.configured ? "API key (enter to update)" : "API key"}
      />
      <input
        className={`${input} mt-2`}
        value={defaultDataset}
        onChange={(e) => setDefaultDataset(e.target.value)}
        placeholder="default dataset for synced runs (optional)"
      />
      {error && <div className="mt-2 text-[11px] text-terracotta">{error}</div>}
      <button
        onClick={save}
        disabled={busy}
        className="mt-2 w-full rounded-lg bg-coffee py-1.5 text-xs font-semibold text-card transition-colors hover:bg-coffee-deep disabled:opacity-40"
      >
        {busy ? "Saving…" : wb.configured ? "Update W&B credentials" : "Connect W&B & enable sync"}
      </button>
      <p className="mt-1.5 text-[10px] leading-tight text-muted">
        Stored locally. Enables app→W&B mirroring on every run and background polling of new W&B runs.
      </p>
    </div>
  );
}

function Field({ label, value, onCopy, copied, mono }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <span className="text-xs font-medium text-muted">{label}</span>
        <button onClick={onCopy} className="text-xs text-coffee hover:text-coffee-deep">{copied ? "Copied!" : "Copy"}</button>
      </div>
      <code className={`block break-all rounded-lg border border-line bg-paper px-3 py-2 text-xs text-cocoa ${mono ? "font-mono" : ""}`}>{value}</code>
    </div>
  );
}

function Block({ label, text, onCopy, copied }) {
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <span className="text-xs font-medium text-muted">{label}</span>
        <button onClick={onCopy} className="text-xs text-coffee hover:text-coffee-deep">{copied ? "Copied!" : "Copy"}</button>
      </div>
      <pre className="whitespace-pre-wrap break-all rounded-lg border border-line bg-paper p-3 font-mono text-xs text-cocoa">{text}</pre>
    </div>
  );
}
