import React, { useState } from "react";

/**
 * Reusable "how to connect to this project" panel — project_id, token, SDK
 * snippet, and W&B daemon command, each with a copy button. Used right after
 * creation and later via the "Connect" button, so the id/token are always
 * retrievable (never shown once and lost).
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
      {project.wandb?.configured && (
        <Block label="Or auto-sync from W&B" text={daemonCmd} onCopy={() => copy(daemonCmd, "daemon")} copied={copied === "daemon"} />
      )}
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
