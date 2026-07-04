import React from "react";

/** Groundhog wordmark — reused across landing, auth, and the app shell. */
export default function Brand({ size = "md", tagline = true }) {
  const dims = {
    sm: { mark: "h-8 w-8 text-lg", name: "text-base", tag: "text-[11px]" },
    md: { mark: "h-10 w-10 text-xl", name: "text-lg", tag: "text-xs" },
    lg: { mark: "h-12 w-12 text-2xl", name: "text-2xl", tag: "text-sm" },
  }[size];

  return (
    <div className="flex items-center gap-3">
      <div
        className={`${dims.mark} grid place-items-center rounded-2xl bg-coffee text-card shadow-soft`}
      >
        🦫
      </div>
      <div className="leading-tight">
        <div className={`font-display font-semibold text-espresso ${dims.name}`}>Groundhog</div>
        {tagline && <div className={`text-muted ${dims.tag}`}>Research Memory</div>}
      </div>
    </div>
  );
}
