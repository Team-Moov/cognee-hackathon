import React from "react";

const STATUS_STYLES = {
  completed: "bg-emerald-500/15 text-emerald-400 border-emerald-500/30",
  failed:    "bg-red-500/15 text-red-400 border-red-500/30",
  aborted:   "bg-amber-500/15 text-amber-400 border-amber-500/30",
  running:   "bg-blue-500/15 text-blue-400 border-blue-500/30",
};

const STATUS_DOT = {
  completed: "bg-emerald-500",
  failed:    "bg-red-500",
  aborted:   "bg-amber-500",
  running:   "bg-blue-500",
};

export default function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || "bg-zinc-700 text-zinc-300 border-zinc-600";
  const dot   = STATUS_DOT[status]   || "bg-zinc-400";
  return (
    <span className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full border text-xs font-medium ${style}`}>
      <span className={`w-1.5 h-1.5 rounded-full ${dot}`} />
      {status}
    </span>
  );
}
