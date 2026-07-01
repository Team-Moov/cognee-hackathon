import React, { useEffect, useState, useCallback } from "react";
import { getAgentSuggestions, generateReport } from "../services/api";
import AgentSuggestionCard from "../components/AgentSuggestionCard";

export default function AgentsPage() {
  const [suggestions, setSuggestions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [experiment, setExperiment] = useState("");
  const [report, setReport] = useState(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState(null);

  const fetchSuggestions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = {};
      if (experiment) params.experiment = experiment;
      const data = await getAgentSuggestions(params);
      setSuggestions(data.suggestions || []);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }, [experiment]);

  useEffect(() => { fetchSuggestions(); }, [fetchSuggestions]);

  function handleDismissed(id) {
    setSuggestions(prev => prev.filter(s => s.id !== id));
  }

  async function handleReport() {
    if (!experiment) return;
    setGenerating(true);
    setReport(null);
    try {
      const data = await generateReport(experiment);
      setReport(data.report);
    } catch (e) {
      setError(e.message);
    } finally {
      setGenerating(false);
    }
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">Agent Suggestions</h1>
        <p className="text-zinc-500 text-sm mt-1">
          Insights from Triage, Config Proposer, Literature Review, and Dataset Steward agents.
        </p>
      </div>

      {/* Controls */}
      <div className="flex gap-3 mb-6 flex-wrap">
        <input
          type="text"
          placeholder="Filter by experiment name…"
          value={experiment}
          onChange={e => setExperiment(e.target.value)}
          className="flex-1 min-w-48 bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
        />
        <button
          onClick={fetchSuggestions}
          className="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-colors"
        >
          Refresh
        </button>
        <button
          onClick={handleReport}
          disabled={!experiment || generating}
          className="px-4 py-2 rounded-lg bg-emerald-700 hover:bg-emerald-600 disabled:opacity-40 text-white text-sm font-medium transition-colors"
        >
          {generating ? "Generating…" : "Generate Report"}
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-500/10 border border-red-500/30 text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* Report */}
      {report && (
        <div className="mb-6 p-4 rounded-xl border border-zinc-700 bg-zinc-900">
          <div className="flex justify-between items-center mb-3">
            <h2 className="text-sm font-semibold text-zinc-300">Generated Report</h2>
            <button
              onClick={() => setReport(null)}
              className="text-xs text-zinc-600 hover:text-zinc-300"
            >
              Close
            </button>
          </div>
          <pre className="text-xs text-zinc-400 whitespace-pre-wrap font-mono leading-relaxed">{report}</pre>
        </div>
      )}

      {/* Suggestions list */}
      {loading ? (
        <div className="text-zinc-500 text-sm py-12 text-center">Loading suggestions…</div>
      ) : suggestions.length === 0 ? (
        <div className="text-zinc-500 text-sm py-12 text-center">
          No active suggestions.
          {!experiment && " Run some experiments to get agent insights."}
        </div>
      ) : (
        <div className="space-y-3">
          {suggestions.map(s => (
            <AgentSuggestionCard
              key={s.id}
              suggestion={s}
              onDismissed={handleDismissed}
            />
          ))}
        </div>
      )}
    </div>
  );
}
