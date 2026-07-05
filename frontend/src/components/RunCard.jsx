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
      className="group cursor-pointer overflow-hidden rounded-3xl border border-slate-800/80 bg-slate-900/85 p-5 shadow-xl shadow-slate-950/20 transition duration-200 hover:border-slate-700/80 hover:bg-slate-900/95"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <div className="rounded-full border border-slate-700 bg-slate-950/70 px-2 py-1 text-xs font-mono text-slate-400">
              {shortId}…
            </div>
            <StatusBadge status={run.status} />
          </div>
          <div className="mt-1.5 truncate text-sm font-semibold text-slate-100">{run.experiment}</div>
          {run.rationale && <div className="mt-0.5 line-clamp-2 text-xs text-slate-400">{run.rationale}</div>}
        </div>

        <div className="flex flex-shrink-0 items-start gap-2">
          {metric != null && (
            <div className="text-right">
              <div className="font-mono text-2xl font-semibold text-emerald-400 tracking-tight">
                {typeof metric.value === "number" ? metric.value.toFixed(3) : metric.value}
              </div>
              <div className="text-xs uppercase tracking-[0.18em] text-slate-500">{metric.label}</div>
            </div>
          )}
          {/* Feature 7: Explain button */}
          <button
            onClick={handleExplain}
            title="Explain this run"
            className={`rounded-md px-3 py-1 text-xs font-medium transition-all duration-200 opacity-0 group-hover:opacity-100 ${
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
              className="rounded-md px-3 py-1 text-xs text-slate-400 opacity-0 transition duration-200 hover:bg-slate-800 hover:text-rose-300 group-hover:opacity-100"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* hypothesis */}
      {run.hypothesis && (
        <div className="mt-2 rounded-r-lg border-l-2 border-indigo-500/40 bg-indigo-950/10 px-3 py-2 text-sm text-slate-300">
          <span className="font-semibold uppercase tracking-wide text-slate-300/80">Hypothesis</span>
          <div className="mt-1 leading-relaxed text-slate-300">{run.hypothesis}</div>
        </div>
      )}

      {/* config */}
          <div className="mt-3 flex flex-wrap items-center gap-2 text-xs font-mono text-slate-400">
            {Object.entries(run.config || {})
              .slice(0, 4)
              .map(([k, v]) => (
                <span key={k} className="rounded border border-slate-700/80 bg-slate-950/70 px-2 py-1 text-[11px] text-indigo-300">
                  {k}={v}
                </span>
              ))}
          </div>

      {/* dataset + artifacts row */}
      {(dataset || artifacts.length > 0) && (
        <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-muted">
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
            <span key={t} className="rounded border border-line bg-sand px-2 py-0.5 text-xs text-muted/90">
              {n} {t}{n > 1 ? "s" : ""}
            </span>
          ))}
        </div>
      )}

      {/* footer: cost + time */}
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 border-t border-line pt-2 text-xs text-muted/80">
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
        <div className="mt-4 rounded-3xl border border-slate-800/70 bg-slate-950/90 shadow-xl shadow-slate-950/20">
          <div className="flex items-center justify-between border-b border-slate-800/70 bg-slate-900/80 px-4 py-3">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-slate-800/80 text-xs font-semibold text-slate-100">
                W&B
              </div>
              <div>
                <div className="text-sm font-semibold text-slate-100">Weights &amp; Biases</div>
                <div className="text-xs text-slate-500">Telemetry snapshot</div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <a
                href={run.config._wandb_url}
                target="_blank"
                rel="noreferrer"
                className="rounded-full px-2 py-1 text-[11px] font-medium text-slate-400 transition hover:bg-slate-800 hover:text-slate-100"
              >
                Open in new tab
              </a>
              <button
                type="button"
                className="rounded-full px-2 py-1 text-[11px] font-medium text-slate-400 transition hover:bg-slate-800 hover:text-slate-100"
              >
                View full lineage
              </button>
            </div>
          </div>
          <div className="h-60 overflow-hidden bg-slate-950">
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
