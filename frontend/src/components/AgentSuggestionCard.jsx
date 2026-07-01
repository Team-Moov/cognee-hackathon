import React, { useState } from "react";
import { dismissSuggestion } from "../services/api";

const AGENT_META = {
  config_proposer:  { icon: "🧪", label: "Config Proposer",   color: "text-violet-400  border-violet-500/30 bg-violet-500/10" },
  triage:           { icon: "🚨", label: "Triage",            color: "text-red-400     border-red-500/30    bg-red-500/10"    },
  literature:       { icon: "📚", label: "Literature Review", color: "text-blue-400    border-blue-500/30   bg-blue-500/10"   },
  dataset_steward:  { icon: "🗄️", label: "Dataset Steward",   color: "text-amber-400   border-amber-500/30  bg-amber-500/10"  },
  report:           { icon: "📝", label: "Report",            color: "text-zinc-400    border-zinc-500/30   bg-zinc-500/10"   },
};

export default function AgentSuggestionCard({ suggestion, onDismissed }) {
  const [dismissing, setDismissing] = useState(false);
  const meta = AGENT_META[suggestion.agent_type] || {
    icon: "🤖", label: suggestion.agent_type, color: "text-zinc-400 border-zinc-500/30 bg-zinc-500/10",
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
    <div className={`rounded-xl border p-4 ${meta.color.split(" ").slice(1).join(" ")}`}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-lg">{meta.icon}</span>
          <span className={`text-xs font-semibold uppercase tracking-wider ${meta.color.split(" ")[0]}`}>
            {meta.label}
          </span>
          {suggestion.experiment && (
            <span className="text-xs text-zinc-500 font-mono">{suggestion.experiment}</span>
          )}
          {suggestion.severity && (
            <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${
              suggestion.severity === "high" ? "bg-red-500/20 text-red-300" :
              suggestion.severity === "medium" ? "bg-amber-500/20 text-amber-300" :
              "bg-zinc-700 text-zinc-400"
            }`}>{suggestion.severity}</span>
          )}
        </div>
        <button
          onClick={handleDismiss}
          disabled={dismissing}
          className="text-xs text-zinc-600 hover:text-zinc-300 transition-colors shrink-0"
        >
          {dismissing ? "…" : "Dismiss"}
        </button>
      </div>

      {/* Main content */}
      {payload.rationale && (
        <p className="mt-2 text-sm text-zinc-300">{payload.rationale}</p>
      )}
      {payload.message && (
        <p className="mt-2 text-sm text-zinc-300">{payload.message}</p>
      )}
      {payload.recommendation && (
        <p className="mt-2 text-xs text-zinc-400">{payload.recommendation}</p>
      )}

      {/* Config Proposer extras */}
      {payload.suggested_config && (
        <details className="mt-2">
          <summary className="text-xs text-zinc-500 cursor-pointer hover:text-zinc-300">Suggested config</summary>
          <pre className="mt-1 text-xs text-zinc-400 bg-zinc-900 rounded p-2 overflow-x-auto">
            {JSON.stringify(payload.suggested_config, null, 2)}
          </pre>
        </details>
      )}

      {/* Literature extras */}
      {Array.isArray(payload.papers) && payload.papers.length > 0 && (
        <ul className="mt-2 space-y-1">
          {payload.papers.map((p, i) => (
            <li key={i} className="text-xs text-zinc-400">
              <span className="text-zinc-300 font-medium">{p.title}</span>
              {p.venue && <span className="text-zinc-600 ml-1">({p.venue})</span>}
              {p.actionable_suggestion && <span className="ml-1">— {p.actionable_suggestion}</span>}
            </li>
          ))}
        </ul>
      )}

      {/* Dataset Steward extras */}
      {Array.isArray(payload.issues) && payload.issues.length > 0 && (
        <ul className="mt-2 space-y-1">
          {payload.issues.map((issue, i) => (
            <li key={i} className="text-xs text-zinc-400">• {issue.description || issue}</li>
          ))}
        </ul>
      )}

      <div className="mt-2 text-xs text-zinc-700">
        {suggestion.run_id && <span className="font-mono mr-2">{suggestion.run_id}</span>}
        {suggestion.timestamp && new Date(suggestion.timestamp).toLocaleDateString()}
      </div>
    </div>
  );
}
