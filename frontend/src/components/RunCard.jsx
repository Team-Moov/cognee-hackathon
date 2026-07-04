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

const ARTIFACT_ICON = {
  checkpoint: "💾", plot: "📈", log: "📄", eval_report: "📊", other: "📎",
};

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
      className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 cursor-pointer hover:border-indigo-500/50 hover:bg-zinc-800/60 transition-all group"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <code className="text-xs text-indigo-400 font-mono bg-indigo-500/10 px-1.5 py-0.5 rounded" title={run.run_id}>
              {shortId}…
            </code>
            <StatusBadge status={run.status} />
          </div>
          <div className="mt-1.5 text-sm font-medium text-zinc-100 truncate">{run.experiment}</div>
          {run.rationale && <div className="mt-0.5 text-xs text-zinc-500 line-clamp-2">{run.rationale}</div>}
        </div>

        {metric != null && (
          <div className="text-right flex-shrink-0">
            <div className="text-lg font-bold text-zinc-100">
              {typeof metric.value === "number" ? metric.value.toFixed(3) : metric.value}
            </div>
            <div className="text-xs text-zinc-500">{metric.label}</div>
          </div>
        )}
      </div>

      {/* hypothesis */}
      {run.hypothesis && (
        <div className="mt-2 text-xs text-indigo-300/80 bg-indigo-500/5 border border-indigo-500/15 rounded px-2 py-1">
          💡 {run.hypothesis}
        </div>
      )}

      {/* config */}
      <div className="mt-3 flex items-center gap-3 text-xs text-zinc-500 flex-wrap">
        <span>⚙️ {Object.entries(run.config || {}).slice(0, 3).map(([k, v]) => `${k}=${v}`).join(", ")}</span>
      </div>

      {/* dataset + artifacts row */}
      {(dataset || artifacts.length > 0) && (
        <div className="mt-2 flex items-center gap-2 flex-wrap">
          {dataset && (
            <span
              className="text-xs bg-blue-500/10 text-blue-300 border border-blue-500/20 rounded px-2 py-0.5"
              title={[dataset.preprocessing, dataset.split_rationale, dataset.quality_issues].filter(Boolean).join(" · ")}
            >
              📊 {dataset.name}{dataset.version ? ` ${dataset.version}` : ""}
              {dataset.quality_issues ? " ⚠" : ""}
            </span>
          )}
          {Object.entries(artByType).map(([t, n]) => (
            <span key={t} className="text-xs bg-zinc-800 text-zinc-400 border border-zinc-700 rounded px-2 py-0.5">
              {ARTIFACT_ICON[t] || "📎"} {n} {t}{n > 1 ? "s" : ""}
            </span>
          ))}
        </div>
      )}

      {/* footer: cost + time */}
      <div className="mt-2 flex items-center gap-4 text-xs text-zinc-600 flex-wrap">
        {run.gpu_hours != null && <span>⚡ {run.gpu_hours}h GPU</span>}
        {wall && <span>⏱ {wall} wall</span>}
        {run.timestamp && <span>🕐 {run.timestamp.slice(0, 10)}</span>}
        <span className="text-zinc-700 group-hover:text-indigo-400 transition-colors ml-auto">View lineage →</span>
      </div>

      {run.status === "failed" && run.error_message && (
        <div className="mt-2 text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded px-2 py-1 font-mono truncate">
          {run.error_message}
        </div>
      )}
    </div>
  );
}
