import React, { useEffect, useState, useCallback } from "react";
import { getAgentSuggestions, generateReport } from "../services/api";
import AgentSuggestionCard from "../components/AgentSuggestionCard";
import PageHeader from "../components/PageHeader";

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
    <div className="mx-auto w-full max-w-6xl p-6 sm:p-8 lg:px-10">
      <PageHeader
        title="Agent Suggestions"
        subtitle="Insights from Triage, Config Proposer, Literature Review, and Dataset Steward agents."
      />

      {/* Controls */}
      <div className="mb-6 flex flex-wrap gap-3">
        <input
          type="text"
          placeholder="Filter by experiment name…"
          value={experiment}
          onChange={e => setExperiment(e.target.value)}
          className="min-w-48 flex-1 rounded-xl border border-line bg-card px-3 py-2 text-sm text-cocoa placeholder-muted/70 focus:border-coffee focus:outline-none focus:ring-2 focus:ring-coffee/20"
        />
        <button
          onClick={fetchSuggestions}
          className="rounded-xl bg-coffee px-4 py-2 text-sm font-semibold text-card transition-colors hover:bg-coffee-deep"
        >
          Refresh
        </button>
        <button
          onClick={handleReport}
          disabled={!experiment || generating}
          className="rounded-xl border border-olive/40 bg-olive/10 px-4 py-2 text-sm font-semibold text-olive transition-colors hover:bg-olive/20 disabled:opacity-40"
        >
          {generating ? "Generating…" : "Generate Report"}
        </button>
      </div>

      {error && (
        <div className="mb-4 rounded-xl border border-terracotta/30 bg-terracotta/10 p-3 text-sm text-terracotta">
          {error}
        </div>
      )}

      {/* Report */}
      {report && (
        <div className="mb-6 rounded-2xl border border-line bg-card p-4 shadow-soft">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-semibold text-espresso">Generated Report</h2>
            <button
              onClick={() => setReport(null)}
              className="text-xs text-muted hover:text-cocoa"
            >
              Close
            </button>
          </div>
          <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-cocoa">{report}</pre>
        </div>
      )}

      {/* Suggestions list */}
      {loading ? (
        <div className="py-12 text-center text-sm text-muted">Loading suggestions…</div>
      ) : suggestions.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-line bg-card/50 py-16 text-center text-sm text-muted">
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
