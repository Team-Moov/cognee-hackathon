import React, { useState } from "react";
import { dismissSuggestion } from "../services/api";

const AGENT_META = {
  config_proposer:  { label: "Config Proposer",   color: "text-coffee     border-coffee/30     bg-coffee/8"     },
  triage:           { label: "Triage",            color: "text-terracotta border-terracotta/30 bg-terracotta/10" },
  literature:       { label: "Literature Review", color: "text-coffee-deep border-coffee/25    bg-sand"          },
  dataset_steward:  { label: "Dataset Steward",   color: "text-ochre      border-ochre/30      bg-ochre/10"     },
  report:           { label: "Report",            color: "text-cocoa      border-line          bg-sand"          },
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
    <div className={`rounded-2xl border p-4 shadow-soft ${meta.color.split(" ").slice(1).join(" ")}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`h-4 w-1 rounded-full ${meta.color.split(" ")[0].replace("text-", "bg-")}`} />
          <span className={`text-xs font-semibold uppercase tracking-wider ${meta.color.split(" ")[0]}`}>
            {meta.label}
          </span>
          {suggestion.experiment && (
            <span className="text-xs text-muted font-mono">{suggestion.experiment}</span>
          )}
          {suggestion.severity && (
            <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
              suggestion.severity === "high" ? "bg-terracotta/15 text-terracotta" :
              suggestion.severity === "medium" ? "bg-ochre/15 text-ochre" :
              "bg-sand text-muted"
            }`}>{suggestion.severity}</span>
          )}
        </div>
        <button
          onClick={handleDismiss}
          disabled={dismissing}
          className="text-xs text-muted hover:text-cocoa transition-colors shrink-0"
        >
          {dismissing ? "…" : "Dismiss"}
        </button>
      </div>

      {/* Main content */}
      {payload.rationale && (
        <p className="mt-2 text-sm text-cocoa">{payload.rationale}</p>
      )}
      {payload.message && (
        <p className="mt-2 text-sm text-cocoa">{payload.message}</p>
      )}
      {payload.recommendation && (
        <p className="mt-2 text-xs text-muted">{payload.recommendation}</p>
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

      <div className="mt-2 text-xs text-muted/70">
        {suggestion.run_id && <span className="font-mono mr-2">{suggestion.run_id}</span>}
        {suggestion.timestamp && new Date(suggestion.timestamp).toLocaleDateString()}
      </div>
    </div>
  );
}
