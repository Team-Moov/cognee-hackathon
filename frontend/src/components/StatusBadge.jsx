import React from "react";

const STATUS_STYLES = {
  completed: "bg-olive/12 text-olive border-olive/30",
  failed:    "bg-terracotta/12 text-terracotta border-terracotta/30",
  aborted:   "bg-ochre/12 text-ochre border-ochre/30",
  running:   "bg-coffee/12 text-coffee border-coffee/30",
};

const STATUS_DOT = {
  completed: "bg-olive",
  failed:    "bg-terracotta",
  aborted:   "bg-ochre",
  running:   "bg-coffee",
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
