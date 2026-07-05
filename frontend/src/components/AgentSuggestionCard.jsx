import React, { useState } from "react";
import { dismissSuggestion } from "../services/api";

const AGENT_META = {
  config_proposer:  { label: "Config Proposer",   color: "text-sky-300 border-sky-500/20 bg-slate-900" },
  triage:           { label: "Triage",            color: "text-rose-300 border-rose-500/20 bg-slate-900" },
  literature:       { label: "Literature Review", color: "text-slate-200 border-slate-700/30 bg-slate-900" },
  dataset_steward:  { label: "Dataset Steward",   color: "text-emerald-300 border-emerald-500/20 bg-slate-900" },
  report:           { label: "Report",            color: "text-slate-300 border-slate-700/30 bg-slate-900" },
};

export default function AgentSuggestionCard({ suggestion, onDismissed }) {
  const [dismissing, setDismissing] = useState(false);
  const meta = AGENT_META[suggestion.agent_type] || {
    label: suggestion.agent_type, color: "text-cocoa border-line bg-sand",
  };

  async function handleDismiss() {
    setDismissing(true);
    try {
      await dismissSuggestion(suggestion.id);
      onDismissed?.(suggestion.id);
    } catch {
      setDismissing(false);
    }
  }

  const payload = suggestion.payload || {};

  return (
    <div className="rounded-2xl border border-line bg-card p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-xs font-semibold tracking-normal ${meta.color.split(" ")[0]}`}>
            {meta.label}
          </span>
          {suggestion.experiment && (
            <span className="text-xs text-muted font-mono">{suggestion.experiment}</span>
          )}
          {suggestion.severity && (
            <span className={`text-xs px-2 py-0.5 rounded-full font-semibold ${
              suggestion.severity === "high" ? "bg-rose-500/10 text-rose-200 border border-rose-400/20" :
              suggestion.severity === "medium" ? "bg-amber-500/10 text-amber-200 border border-amber-400/20" :
              "bg-slate-800 text-slate-300"
            }`}>{suggestion.severity}</span>
          )}
        </div>
        <button
          onClick={handleDismiss}
          disabled={dismissing}
          className="rounded-full border border-line bg-sand px-2.5 py-1 text-[11px] font-medium text-cocoa transition hover:bg-hover hover:text-espresso shrink-0"
        >
          {dismissing ? "…" : "Dismiss"}
        </button>
      </div>

      {/* Main content — the finding text lives on `content`; payload extras
          (metadata) are optional and only present for some agents. */}
      {suggestion.content && !payload.rationale && !payload.message && !payload.papers && !payload.issues && (
        <p className="mt-2 text-sm text-slate-100 leading-relaxed">{suggestion.content}</p>
      )}
      {payload.rationale && (
        <p className="mt-2 text-sm text-slate-100 leading-relaxed">{payload.rationale}</p>
      )}
      {payload.message && (
        <p className="mt-2 text-sm text-slate-100 leading-relaxed">{payload.message}</p>
      )}
      {payload.recommendation && (
        <p className="mt-2 text-xs text-slate-400">{payload.recommendation}</p>
      )}

      {/* Config Proposer extras */}
      {payload.suggested_config && (
        <details className="mt-2">
          <summary className="text-xs text-muted cursor-pointer hover:text-cocoa">Suggested config</summary>
          <pre className="mt-1 text-xs text-cocoa bg-paper border border-line rounded-lg p-2 overflow-x-auto">
            {JSON.stringify(payload.suggested_config, null, 2)}
          </pre>
        </details>
      )}

      {/* Literature extras */}
      {Array.isArray(payload.papers) && payload.papers.length > 0 && (
        <ul className="mt-2 space-y-1">
          {payload.papers.map((p, i) => (
            <li key={i} className="text-xs text-muted">
              <span className="text-cocoa font-medium">{p.title}</span>
              {p.venue && <span className="text-muted ml-1">({p.venue})</span>}
              {p.actionable_suggestion && <span className="ml-1">— {p.actionable_suggestion}</span>}
            </li>
          ))}
        </ul>
      )}

      {/* Dataset Steward extras */}
      {Array.isArray(payload.issues) && payload.issues.length > 0 && (
        <ul className="mt-2 space-y-1">
          {payload.issues.map((issue, i) => (
            <li key={i} className="text-xs text-muted">• {issue.description || issue}</li>
          ))}
        </ul>
      )}

      <div className="mt-2 text-xs text-muted/70 font-mono">
        {suggestion.timestamp && new Date(suggestion.timestamp).toLocaleDateString()}
      </div>
    </div>
  );
}
