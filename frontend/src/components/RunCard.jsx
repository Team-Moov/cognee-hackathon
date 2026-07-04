import React from "react";
import { useNavigate } from "react-router-dom";
import StatusBadge from "./StatusBadge";

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

export default function RunCard({ run }) {
  const nav = useNavigate();
  const metric = primaryMetric(run.metrics);
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

        {metric != null && (
          <div className="flex-shrink-0 text-right">
            <div className="font-display text-lg font-semibold text-espresso">
              {typeof metric.value === "number" ? metric.value.toFixed(3) : metric.value}
            </div>
            <div className="text-xs text-muted">{metric.label}</div>
          </div>
        )}
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

      {run.status === "failed" && run.error_message && (
        <div className="mt-2 truncate rounded-lg border border-terracotta/20 bg-terracotta/10 px-2 py-1 font-mono text-xs text-terracotta">
          {run.error_message}
        </div>
      )}
    </div>
  );
}
