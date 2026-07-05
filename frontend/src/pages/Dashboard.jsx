import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listRuns, getAgentSuggestions } from "../services/api";
import RunCard from "../components/RunCard";
import AgentSuggestionCard from "../components/AgentSuggestionCard";
import LogRunModal from "../components/LogRunModal";

const STATUSES = ["all", "completed", "failed", "aborted"];

export default function Dashboard() {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [expFilter, setExpFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [suggestions, setSuggestions] = useState([]);
  const [showLog, setShowLog] = useState(false);

  // Derive experiment list dynamically from loaded runs
  const experiments = ["all", ...Array.from(new Set(runs.map(r => r.experiment).filter(Boolean)))];

  function loadRuns() {
    setLoading(true);
    listRuns()
      .then(d => setRuns(d.runs || []))
      .catch(() => setRuns([]))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadRuns();
    getAgentSuggestions()
      .then(d => setSuggestions((d.suggestions || []).slice(0, 3)))
      .catch(() => {});
  }, []);

  const filtered = runs.filter(r => {
    if (expFilter !== "all" && r.experiment !== expFilter) return false;
    if (statusFilter !== "all" && r.status !== statusFilter) return false;
    if (search) {
      const s = search.toLowerCase();
      return (
        (r.run_id || "").includes(s) ||
        (r.experiment || "").includes(s) ||
        (r.rationale || "").toLowerCase().includes(s) ||
        JSON.stringify(r.config || {}).toLowerCase().includes(s)
      );
    }
    return true;
  });

  const metricAcc = (r) => r.metrics?.val_accuracy ?? r.metrics?.val_acc ?? r.metrics?.accuracy ?? 0;
  const totalGpuH = runs.reduce((s, r) => s + (r.gpu_hours || 0), 0);
  const failedCount = runs.filter(r => r.status === "failed" || r.status === "aborted").length;
  const bestAcc = runs.length ? Math.max(...runs.map(metricAcc)) : 0;

  const input =
    "rounded-xl border border-line bg-card px-3 py-2 text-sm text-cocoa focus:border-coffee focus:outline-none focus:ring-2 focus:ring-coffee/20";

  return (
    <div className="mx-auto max-w-5xl p-6 sm:p-8">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-semibold text-espresso">Experiment Dashboard</h1>
          <p className="mt-1 text-sm text-muted">All runs, artifacts, and research history in one place.</p>
        </div>
        <button
          onClick={() => setShowLog(true)}
          className="shrink-0 rounded-full bg-coffee px-5 py-2.5 text-sm font-semibold text-card shadow-soft transition-colors hover:bg-coffee-deep"
        >
          + Log run
        </button>
      </div>

      {showLog && (
        <LogRunModal onClose={() => setShowLog(false)} onLogged={loadRuns} />
      )}

      {/* Agent suggestions strip */}
      {suggestions.length > 0 && (
        <div className="mb-6">
          <div className="mb-2 flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-muted">Agent Insights</span>
            <Link to="/agents" className="text-xs font-medium text-coffee hover:text-coffee-deep">View all →</Link>
          </div>
          <div className="space-y-2">
            {suggestions.map(s => (
              <AgentSuggestionCard
                key={s.id}
                suggestion={s}
                onDismissed={id => setSuggestions(prev => prev.filter(x => x.id !== id))}
              />
            ))}
          </div>
        </div>
      )}

      {/* Stats row */}
      <div className="mb-6 grid grid-cols-2 gap-4 sm:grid-cols-4">
        {[
          { label: "Total Runs",   value: runs.length,               sub: `across ${experiments.length - 1} experiments` },
          { label: "GPU-Hours",    value: totalGpuH.toFixed(1) + "h", sub: "total compute" },
          { label: "Best val_acc", value: bestAcc > 0 ? bestAcc.toFixed(3) : "—", sub: "highest accuracy", accent: "text-olive" },
          { label: "Failures",     value: failedCount,               sub: "failed or aborted", accent: "text-terracotta" },
        ].map(({ label, value, sub, accent }) => (
          <div key={label} className="rounded-2xl border border-line bg-card p-4 shadow-soft">
            <div className="mb-1 text-xs text-muted">{label}</div>
            <div className={`font-display text-2xl font-semibold ${accent || "text-espresso"}`}>{value}</div>
            <div className="mt-0.5 text-xs text-muted">{sub}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap gap-3">
        <input
          type="text"
          placeholder="Search runs, configs, rationale…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className={`min-w-48 flex-1 placeholder-muted/70 ${input}`}
        />
        <select value={expFilter} onChange={e => setExpFilter(e.target.value)} className={input}>
          {experiments.map(e => <option key={e} value={e}>{e === "all" ? "All experiments" : e}</option>)}
        </select>
        <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className={input}>
          {STATUSES.map(s => <option key={s} value={s}>{s === "all" ? "All statuses" : s}</option>)}
        </select>
      </div>

      {/* Run list */}
      {loading ? (
        <div className="py-12 text-center text-sm text-muted">Loading runs…</div>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-line bg-card/50 py-16 text-center text-sm text-muted">
          No runs match your filters.
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map(run => (
            <RunCard
              key={run.run_id}
              run={run}
              onDeleted={(id) => setRuns(prev => prev.filter(r => r.run_id !== id))}
            />
          ))}
        </div>
      )}
    </div>
  );
}
