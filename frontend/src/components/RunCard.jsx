import React from "react";
import { useNavigate } from "react-router-dom";
import StatusBadge from "./StatusBadge";

export default function RunCard({ run }) {
  const nav = useNavigate();
  const primaryMetric = run.metrics?.val_acc ?? run.metrics?.perplexity ?? null;
  const metricLabel   = run.metrics?.val_acc != null ? "val_acc" : run.metrics?.perplexity != null ? "perplexity" : null;

  return (
    <div
      onClick={() => nav(`/lineage/${run.run_id}`)}
      className="bg-zinc-900 border border-zinc-800 rounded-xl p-4 cursor-pointer hover:border-indigo-500/50 hover:bg-zinc-800/60 transition-all group"
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 flex-wrap">
            <code className="text-xs text-indigo-400 font-mono bg-indigo-500/10 px-1.5 py-0.5 rounded">
              {run.run_id}
            </code>
            <StatusBadge status={run.status} />
          </div>
          <div className="mt-1.5 text-sm font-medium text-zinc-100 truncate">{run.experiment}</div>
          <div className="mt-0.5 text-xs text-zinc-500 truncate">{run.rationale}</div>
        </div>

        {primaryMetric != null && (
          <div className="text-right flex-shrink-0">
            <div className="text-lg font-bold text-zinc-100">{primaryMetric.toFixed(3)}</div>
            <div className="text-xs text-zinc-500">{metricLabel}</div>
          </div>
        )}
      </div>

      <div className="mt-3 flex items-center gap-3 text-xs text-zinc-500 flex-wrap">
        <span>⚙️ {Object.entries(run.config).slice(0, 3).map(([k,v]) => `${k}=${v}`).join(", ")}</span>
      </div>

      <div className="mt-2 flex items-center gap-4 text-xs text-zinc-600">
        {run.gpu_hours != null && <span>⚡ {run.gpu_hours}h GPU</span>}
        <span>🕐 {run.timestamp?.slice(0, 10)}</span>
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
