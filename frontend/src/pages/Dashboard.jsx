import React, { useEffect, useState } from "react";
import { listRuns, getAgentSuggestions } from "../services/api";
import RunCard from "../components/RunCard";
import AgentSuggestionCard from "../components/AgentSuggestionCard";

const STATUSES = ["all", "completed", "failed", "aborted"];

export default function Dashboard() {
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [expFilter, setExpFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [suggestions, setSuggestions] = useState([]);

  // Derive experiment list dynamically from loaded runs
  const experiments = ["all", ...Array.from(new Set(runs.map(r => r.experiment).filter(Boolean)))];

  useEffect(() => {
    listRuns()
      .then(d => setRuns(d.runs || []))
      .finally(() => setLoading(false));
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
  const totalArtifacts = runs.reduce((s, r) => s + (r.artifacts?.length || 0), 0);
  const bestAcc = runs.length ? Math.max(...runs.map(metricAcc)) : 0;

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">Experiment Dashboard</h1>
        <p className="text-zinc-500 text-sm mt-1">All runs, artifacts, and research history in one place.</p>
      </div>

      {/* Agent suggestions strip */}
      {suggestions.length > 0 && (
        <div className="mb-6">
          <div className="flex items-center justify-between mb-2">
            <span className="text-xs font-semibold text-zinc-500 uppercase tracking-wider">Agent Insights</span>
            <a href="/agents" className="text-xs text-indigo-400 hover:text-indigo-300">View all →</a>
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
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        {[
          { label: "Total Runs",  value: runs.length,          sub: `across ${experiments.length - 1} experiments`, color: "text-zinc-100"   },
          { label: "GPU-Hours",   value: totalGpuH.toFixed(1) + "h", sub: "total compute",     color: "text-blue-400"   },
          { label: "Best val_acc", value: bestAcc > 0 ? bestAcc.toFixed(3) : "—", sub: "highest accuracy", color: "text-emerald-400" },
          { label: "Failures",    value: failedCount,          sub: "failed or aborted",        color: "text-red-400"    },
        ].map(({ label, value, sub, color }) => (
          <div key={label} className="bg-zinc-900 border border-zinc-800 rounded-xl p-4">
            <div className="text-xs text-zinc-500 mb-1">{label}</div>
            <div className={`text-2xl font-bold ${color}`}>{value}</div>
            <div className="text-xs text-zinc-600 mt-0.5">{sub}</div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-3 mb-4 flex-wrap">
        <input
          type="text"
          placeholder="Search runs, configs, rationale…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="flex-1 min-w-48 bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
        />
        <select
          value={expFilter}
          onChange={e => setExpFilter(e.target.value)}
          className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-300 focus:outline-none focus:border-indigo-500"
        >
          {experiments.map(e => <option key={e} value={e}>{e === "all" ? "All experiments" : e}</option>)}
        </select>
        <select
          value={statusFilter}
          onChange={e => setStatusFilter(e.target.value)}
          className="bg-zinc-900 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-300 focus:outline-none focus:border-indigo-500"
        >
          {STATUSES.map(s => <option key={s} value={s}>{s === "all" ? "All statuses" : s}</option>)}
        </select>
      </div>

      {/* Run list */}
      {loading ? (
        <div className="text-zinc-500 text-sm py-12 text-center">Loading runs…</div>
      ) : filtered.length === 0 ? (
        <div className="text-zinc-500 text-sm py-12 text-center">No runs match your filters.</div>
      ) : (
        <div className="space-y-3">
          {filtered.map(run => <RunCard key={run.run_id} run={run} />)}
        </div>
      )}
    </div>
  );
}
