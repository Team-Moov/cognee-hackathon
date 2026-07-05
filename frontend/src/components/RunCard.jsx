import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import StatusBadge from "./StatusBadge";
import { deleteRun, explainRun } from "../services/api";

// alias-tolerant primary metric (labs disagree on val_acc vs val_accuracy)
function primaryMetric(metrics = {}) {
  const acc = metrics.val_accuracy ?? metrics.val_acc ?? metrics.accuracy;
  if (acc != null) return { value: acc, label: "val_acc" };
  if (metrics.perplexity != null) return { value: metrics.perplexity, label: "perplexity" };
  if (metrics.f1_score != null) return { value: metrics.f1_score, label: "f1" };
  return null;
}

function fmtDuration(sec) {
  if (!sec) return null;
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  return h ? `${h}h ${m}m` : `${m}m`;
}

// Feature 1: colour-coded severity badge for triage findings
const SEVERITY_STYLES = {
  high:   "border-terracotta/30 bg-terracotta/10 text-terracotta",
  medium: "border-amber-400/30 bg-amber-50 text-amber-700",
  low:    "border-coffee/20 bg-coffee/5 text-coffee-deep",
};

export default function RunCard({ run, onDeleted }) {
  const nav = useNavigate();
  const metric = primaryMetric(run.metrics);

  // Feature 7: explain panel state
  const [explaining, setExplaining] = useState(false);
  const [explanation, setExplanation] = useState(null);
  const [explainError, setExplainError] = useState(null);

  async function handleDelete(e) {
    e.stopPropagation();
    if (!window.confirm("Delete this run from memory? This cannot be undone.")) return;
    try {
      await deleteRun(run.run_id);
      onDeleted?.(run.run_id);
    } catch (err) {
      alert("Delete failed: " + err.message);
    }
  }

  // Feature 7: load explanation on demand
  async function handleExplain(e) {
    e.stopPropagation();
    if (explanation) { setExplanation(null); return; } // toggle off
    setExplaining(true);
    setExplainError(null);
    try {
      const data = await explainRun(run.run_id);
      setExplanation(data);
    } catch (err) {
      setExplainError(err.message);
    } finally {
      setExplaining(false);
    }
  }

  const dataset = run.dataset && run.dataset.name && run.dataset.name !== "unknown" ? run.dataset : null;
  const artifacts = Array.isArray(run.artifacts) ? run.artifacts : [];
  const wall = fmtDuration(run.wall_clock_seconds);
  const shortId = (run.run_id || "").slice(0, 12);

  // group artifacts by type for a compact summary
  const artByType = artifacts.reduce((m, a) => {
    const t = a.artifact_type || "other";
    m[t] = (m[t] || 0) + 1;
    return m;
  }, {});

  // Feature 1: always show failure analysis for failed/aborted runs
  // Derived deterministically from the run's own fields — no agent wait needed.
  const isFailed = run.status === "failed" || run.status === "aborted";
  const failureHeadline = isFailed
    ? run.error_message
      ? run.error_message.slice(0, 80)
      : run.status === "aborted"
      ? "Run was aborted before completion"
      : "Run failed — no error message recorded"
    : null;

  // Suggest a fix based on common patterns in the config + metrics
  function inferFix(run) {
    const cfg  = run.config  || {};
    const mets = run.metrics || {};
    const lr   = parseFloat(cfg.lr || cfg.learning_rate || 0);
    const loss = parseFloat(mets.val_loss || mets.loss || 0);
    if (lr > 0.1)      return `lr=${lr} is very high — try cutting it by 10× (e.g. lr=${(lr / 10).toFixed(4)})`;
    if (loss > 2)      return "Loss is very high — check for NaN in gradients; try gradient clipping (max_norm=1.0)";
    if (cfg.batch_size > 128) return `batch_size=${cfg.batch_size} may exceed GPU memory — try 32 or 64`;
    if (run.gpu_hours && run.gpu_hours > 5) return "Long run that failed — add checkpointing to resume from last epoch";
    return "Review the error message above and check your data pipeline for NaN/Inf values";
  }

  const failureFix = isFailed ? inferFix(run) : null;

  return (
    <div
      onClick={() => nav(`/lineage/${run.run_id}`)}
      className="group cursor-pointer rounded-2xl border border-line bg-card p-4 shadow-soft transition-all hover:-translate-y-0.5 hover:border-coffee/40 hover:shadow-lift"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <code className="rounded bg-sand px-1.5 py-0.5 font-mono text-xs text-coffee-deep" title={run.run_id}>
              {shortId}…
            </code>
            <StatusBadge status={run.status} />
          </div>
          <div className="mt-1.5 truncate text-sm font-semibold text-espresso">{run.experiment}</div>
          {run.rationale && <div className="mt-0.5 line-clamp-2 text-xs text-muted">{run.rationale}</div>}
        </div>

        <div className="flex flex-shrink-0 items-start gap-2">
          {metric != null && (
            <div className="text-right">
              <div className="font-display text-lg font-semibold text-espresso">
                {typeof metric.value === "number" ? metric.value.toFixed(3) : metric.value}
              </div>
              <div className="text-xs text-muted">{metric.label}</div>
            </div>
          )}
          {/* Feature 7: Explain button */}
          <button
            onClick={handleExplain}
            title="Explain this run"
            className={`rounded-md px-2 py-0.5 text-xs font-medium transition-all opacity-0 group-hover:opacity-100 ${
              explanation
                ? "bg-coffee text-card"
                : "border border-coffee/30 text-coffee hover:bg-coffee/10"
            }`}
          >
            {explaining ? "…" : explanation ? "Close" : "Explain"}
          </button>
          {onDeleted && (
            <button
              onClick={handleDelete}
              title="Delete run"
              className="rounded-md px-1.5 py-0.5 text-xs text-muted opacity-0 transition-opacity hover:bg-terracotta/10 hover:text-terracotta group-hover:opacity-100"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* hypothesis */}
      {run.hypothesis && (
        <div className="mt-2 rounded-lg border-l-2 border-coffee/40 bg-coffee/5 px-3 py-1.5 text-xs text-coffee-deep">
          <span className="font-semibold uppercase tracking-wide text-coffee/70">Hypothesis · </span>
          {run.hypothesis}
        </div>
      )}

      {/* config */}
      <div className="mt-3 flex flex-wrap items-center gap-3 font-mono text-xs text-muted">
        <span>{Object.entries(run.config || {}).slice(0, 3).map(([k, v]) => `${k}=${v}`).join("  ·  ")}</span>
      </div>

      {/* dataset + artifacts row */}
      {(dataset || artifacts.length > 0) && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          {dataset && (
            <span
              className="rounded border border-coffee/20 bg-coffee/10 px-2 py-0.5 text-xs text-coffee-deep"
              title={[dataset.preprocessing, dataset.split_rationale, dataset.quality_issues].filter(Boolean).join(" · ")}
            >
              {dataset.name}{dataset.version ? ` ${dataset.version}` : ""}
              {dataset.quality_issues ? " (issues)" : ""}
            </span>
          )}
          {Object.entries(artByType).map(([t, n]) => (
            <span key={t} className="rounded border border-line bg-sand px-2 py-0.5 text-xs text-cocoa">
              {n} {t}{n > 1 ? "s" : ""}
            </span>
          ))}
        </div>
      )}

      {/* footer: cost + time */}
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line pt-2 text-xs text-muted">
        {run.gpu_hours != null && <span>{run.gpu_hours}h GPU</span>}
        {wall && <span>{wall} wall</span>}
        {run.timestamp && <span>{run.timestamp.slice(0, 10)}</span>}
        <span className="ml-auto font-medium text-coffee/70 transition-colors group-hover:text-coffee">View lineage →</span>
      </div>

      {/* Feature 1: Plain error message for failed runs (existing) */}
      {run.status === "failed" && run.error_message && !failureHeadline && (
        <div className="mt-2 truncate rounded-lg border border-terracotta/20 bg-terracotta/10 px-2 py-1 font-mono text-xs text-terracotta">
          {run.error_message}
        </div>
      )}

      {/* Feature 1: Structured failure analysis panel (immediate logic) */}
      {isFailed && (
        <div className={`mt-2 rounded-xl border p-3 ${SEVERITY_STYLES.high}`}>
          <div className="mb-1 flex items-center gap-2">
            <span className="text-xs font-bold uppercase tracking-wider opacity-70">
              🔴 Why it failed
            </span>
          </div>
          {failureHeadline && (
            <div className="text-sm font-semibold">{failureHeadline}</div>
          )}
          {run.rationale && (
            <div className="mt-0.5 text-xs opacity-80">Context: {run.rationale}</div>
          )}
          {failureFix && (
            <div className="mt-1.5 rounded-md bg-white/40 px-2 py-1 text-xs font-medium">
              💡 Fix: {failureFix}
            </div>
          )}
        </div>
      )}

      {/* Feature 7: Explain panel (on-demand) */}
      {(explanation || explainError) && (
        <div
          className="mt-3 rounded-xl border border-coffee/20 bg-coffee/5 p-3"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="mb-2 text-xs font-bold uppercase tracking-wider text-coffee/70">
            🔍 Run Explanation
          </div>
          {explainError ? (
            <div className="text-xs text-terracotta">{explainError}</div>
          ) : explanation ? (
            <div className="space-y-2">
              <p className="text-xs leading-relaxed text-cocoa">{explanation.explanation}</p>
              {explanation.best_sibling && (
                <div className="rounded-lg border border-olive/20 bg-olive/5 px-2 py-1.5 text-xs text-olive">
                  <span className="font-semibold">Best sibling: </span>
                  val_acc={explanation.best_sibling.metrics?.val_accuracy ?? "—"} —{" "}
                  {Object.entries(explanation.best_sibling.config || {}).slice(0, 3).map(([k,v]) => `${k}=${v}`).join(", ")}
                </div>
              )}
              {explanation.sibling_count > 0 && (
                <div className="text-xs text-muted">{explanation.sibling_count} other run(s) in this experiment</div>
              )}
            </div>
          ) : null}
        </div>
      )}

      {/* W&B Iframe Embedding */}
      {run.config && run.config._wandb_url && (
        <div className="mt-4 pt-4 border-t border-line" onClick={(e) => e.stopPropagation()}>
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-semibold text-espresso">Weights &amp; Biases Telemetry</span>
            <a href={run.config._wandb_url} target="_blank" rel="noreferrer" className="text-[10px] text-coffee hover:underline">Open in new tab ↗</a>
          </div>
          <div className="h-48 w-full overflow-hidden rounded-xl border border-line bg-white">
            <iframe
              src={run.config._wandb_url}
              className="h-full w-full border-none"
              title="W&B Run Dashboard"
              loading="lazy"
            />
          </div>
        </div>
      )}
    </div>
  );
}
