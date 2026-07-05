import React from "react";

const STATUS_STYLES = {
  completed: "inline-flex items-center gap-1.5 rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-0.5 text-xs font-medium text-emerald-400",
  failed:    "inline-flex items-center gap-1.5 rounded-full border border-rose-500/20 bg-rose-500/10 px-2.5 py-0.5 text-xs font-medium text-rose-300",
  aborted:   "inline-flex items-center gap-1.5 rounded-full border border-amber-500/20 bg-amber-500/10 px-2.5 py-0.5 text-xs font-medium text-amber-300",
  running:   "inline-flex items-center gap-1.5 rounded-full border border-sky-500/20 bg-sky-500/10 px-2.5 py-0.5 text-xs font-medium text-sky-300",
};

const STATUS_DOT = {
  completed: "bg-emerald-300 motion-safe:animate-pulse",
  failed:    "bg-rose-300",
  aborted:   "bg-amber-300",
  running:   "bg-sky-300",
};

export default function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || "bg-sand text-cocoa border-line";
  const dot   = STATUS_DOT[status]   || "bg-muted";
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 text-xs font-medium ${style}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${dot}`} />
      {status}
    </span>
  );
}
