import React, { useState } from "react";
import { rememberRun, getCurrentProject } from "../services/api";

/**
 * "Log run" modal: records a run into the current project's Groundhog memory AND
 * (if the project has W&B credentials) mirrors it into W&B as a real run. This is
 * the create-in-the-frontend → shows-up-in-W&B path.
 */
const STATUSES = ["completed", "failed", "aborted"];

export default function LogRunModal({ onClose, onLogged }) {
  const [experiment, setExperiment] = useState("");
  const [thread, setThread] = useState("default");
  const [status, setStatus] = useState("completed");
  const [configText, setConfigText] = useState(
    '{\n  "model": "ResNet50",\n  "learning_rate": 0.001,\n  "batch_size": 32,\n  "optimizer": "AdamW"\n}'
  );
  const [metricsText, setMetricsText] = useState(
    '{\n  "val_loss": 0.21,\n  "val_accuracy": 0.91\n}'
  );
  const [rationale, setRationale] = useState("");
  const [gpuHours, setGpuHours] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);

  const projectId = getCurrentProject();

  function parseJson(text, label) {
    if (!text.trim()) return {};
    try {
      const v = JSON.parse(text);
      if (typeof v !== "object" || Array.isArray(v)) throw new Error("must be a JSON object");
      return v;
    } catch (e) {
      throw new Error(`${label} is not valid JSON: ${e.message}`);
    }
  }

  async function submit(e) {
    e.preventDefault();
    if (!experiment.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const config = parseJson(configText, "Config");
      const metrics = parseJson(metricsText, "Metrics");
      const data = {
        experiment: experiment.trim(),
        thread: thread.trim() || "default",
        status,
        config,
        metrics,
        rationale: rationale.trim(),
        git_commit: "frontend",
      };
      if (gpuHours.trim() && !Number.isNaN(Number(gpuHours))) data.gpu_hours = Number(gpuHours);
      const res = await rememberRun(data);
      setResult(res);
      onLogged?.(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  const input =
    "w-full bg-paper border border-line rounded-xl px-3 py-2 text-sm text-cocoa placeholder-muted/70 focus:outline-none focus:border-coffee focus:ring-2 focus:ring-coffee/20";
  const mono =
    "w-full bg-paper border border-line rounded-xl px-3 py-2 text-xs font-mono text-cocoa placeholder-muted/70 focus:outline-none focus:border-coffee focus:ring-2 focus:ring-coffee/20";
  const label = "block text-xs font-medium text-cocoa mb-1";

  const wb = result?.wandb;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-espresso/60 p-4 backdrop-blur-sm" onClick={onClose}>
      <div
        className="w-full max-w-lg bg-card border border-line rounded-3xl shadow-lift ring-1 ring-espresso/5 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        {!result ? (
          <form onSubmit={submit} className="p-6 space-y-4">
            <div>
              <h2 className="font-display text-xl font-semibold text-espresso">Log a run</h2>
              <p className="text-xs text-muted mt-0.5">
                Records into this project's memory and mirrors it to W&B if the project has W&B credentials.
              </p>
            </div>

            {!projectId && (
              <div className="text-xs text-ochre bg-ochre/10 border border-ochre/25 rounded-xl p-2">
                No project selected — the run won't be scoped or pushed to W&B. Pick a project first.
              </div>
            )}

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={label}>Experiment / run name *</label>
                <input autoFocus className={input} value={experiment} onChange={(e) => setExperiment(e.target.value)} placeholder="resnet50_baseline" />
              </div>
              <div>
                <label className={label}>Thread</label>
                <input className={input} value={thread} onChange={(e) => setThread(e.target.value)} placeholder="default" />
              </div>
            </div>

            <div>
              <label className={label}>Status</label>
              <select className={input} value={status} onChange={(e) => setStatus(e.target.value)}>
                {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
              </select>
            </div>

            <div>
              <label className={label}>Config (JSON)</label>
              <textarea className={mono} rows={5} value={configText} onChange={(e) => setConfigText(e.target.value)} />
            </div>

            <div>
              <label className={label}>Metrics (JSON)</label>
              <textarea className={mono} rows={3} value={metricsText} onChange={(e) => setMetricsText(e.target.value)} />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className={label}>GPU-hours <span className="text-muted">(optional)</span></label>
                <input className={input} value={gpuHours} onChange={(e) => setGpuHours(e.target.value)} placeholder="2.5" />
              </div>
            </div>

            <div>
              <label className={label}>Notes / rationale <span className="text-muted">(optional)</span></label>
              <textarea className={input} rows={2} value={rationale} onChange={(e) => setRationale(e.target.value)} placeholder="What this run tested and what happened." />
            </div>

            {error && <div className="text-sm text-terracotta bg-terracotta/10 border border-terracotta/25 rounded-xl p-2">{error}</div>}

            <div className="flex gap-2 justify-end pt-2">
              <button type="button" onClick={onClose} className="text-sm text-muted hover:text-cocoa px-3 py-2">Cancel</button>
              <button type="submit" disabled={busy || !experiment.trim()} className="bg-coffee hover:bg-coffee-deep disabled:opacity-40 text-card text-sm font-semibold px-4 py-2 rounded-xl transition-colors">
                {busy ? "Logging…" : "Log run"}
              </button>
            </div>
          </form>
        ) : (
          <div className="p-6 space-y-4">
            <h2 className="font-display text-xl font-semibold text-olive">Run logged</h2>
            <div className="text-sm text-cocoa">
              <div>Run ID: <code className="text-espresso break-all">{result.run_id}</code></div>
              <div className="mt-1">Memory: <span className="text-muted">{result.cognee_status}</span></div>
            </div>

            {wb?.pushed ? (
              <div className="text-sm bg-paper border border-line rounded-xl p-3">
                <div className="text-olive font-semibold">Pushed to W&B</div>
                <div className="text-muted mt-1">
                  {wb.entity ? `${wb.entity}/` : ""}{wb.project} · <code>{wb.wandb_id}</code>
                </div>
                {wb.url && (
                  <a href={wb.url} target="_blank" rel="noreferrer" className="text-coffee hover:text-coffee-deep text-xs">
                    Open in W&B →
                  </a>
                )}
              </div>
            ) : (
              <div className="text-sm bg-paper border border-line rounded-xl p-3 text-muted">
                Not pushed to W&B: {wb?.reason || "no W&B credentials on this project"}
              </div>
            )}

            <div className="flex justify-end pt-2">
              <button onClick={onClose} className="bg-coffee hover:bg-coffee-deep text-card text-sm font-semibold px-4 py-2 rounded-xl transition-colors">Done</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
