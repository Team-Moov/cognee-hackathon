import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listRuns, getAgentSuggestions } from "../services/api";
import RunCard from "../components/RunCard";
import AgentSuggestionCard from "../components/AgentSuggestionCard";
import LogRunModal from "../components/LogRunModal";
import PageHeader from "../components/PageHeader";

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
  const experiments = [
    "all",
    ...Array.from(new Set(runs.map((r) => r.experiment).filter(Boolean))),
  ];

  function loadRuns() {
    setLoading(true);
    listRuns()
      .then((d) => setRuns(d.runs || []))
      .catch(() => setRuns([]))
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    loadRuns();
    getAgentSuggestions()
      .then((d) => setSuggestions((d.suggestions || []).slice(0, 3)))
      .catch(() => {});
  }, []);

  const filtered = runs.filter((r) => {
    if (expFilter !== "all" && r.experiment !== expFilter) return false;
    if (statusFilter !== "all" && r.status !== statusFilter) return false;
    if (search) {
      const s = search.toLowerCase();
      return (
        (r.run_id || "").includes(s) ||
        (r.experiment || "").includes(s) ||
        (r.rationale || "").toLowerCase().includes(s) ||
        JSON.stringify(r.config || {})
          .toLowerCase()
          .includes(s)
      );
    }
    return true;
  });

  const metricAcc = (r) =>
    r.metrics?.val_accuracy ?? r.metrics?.val_acc ?? r.metrics?.accuracy ?? 0;
  const totalGpuH = runs.reduce((s, r) => s + (r.gpu_hours || 0), 0);
  const failedCount = runs.filter(
    (r) => r.status === "failed" || r.status === "aborted",
  ).length;
  const bestAcc = runs.length ? Math.max(...runs.map(metricAcc)) : 0;

  const input =
    "rounded-2xl border border-slate-800 bg-slate-950/70 px-3 py-3 text-sm text-slate-100 placeholder-slate-500 focus:border-blue-400 focus:outline-none focus:ring-2 focus:ring-blue-400/20 transition duration-200";

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-5 sm:px-5 lg:px-6">
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <PageHeader
          title="Experiment Dashboard"
          subtitle="All runs, artifacts, and research history in one place."
        />
        <button
          onClick={() => setShowLog(true)}
          className="shrink-0 rounded-full bg-slate-200/10 px-5 py-2.5 text-sm font-semibold text-slate-100 shadow-sm shadow-slate-950/30 transition duration-200 hover:bg-slate-800/80"
        >
          + Log run
        </button>
      </div>

      {showLog && (
        <LogRunModal onClose={() => setShowLog(false)} onLogged={loadRuns} />
      )}

      {/* Agent suggestions strip */}
      {suggestions.length > 0 && (
        <div className="mb-6 rounded-3xl border border-slate-800/70 bg-slate-900/75 p-5 shadow-xl shadow-slate-950/20 backdrop-blur-xl">
          <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-500">
                Agent insights
              </p>
              <h2 className="mt-2 text-xl font-semibold text-slate-100">
                Recent recommendations
              </h2>
            </div>
            <Link
              to="/agents"
              className="rounded-full border border-slate-700/80 bg-slate-950/70 px-3 py-2 text-xs font-medium text-slate-300 transition hover:border-slate-600 hover:bg-slate-800/80 hover:text-slate-100"
            >
              View all →
            </Link>
          </div>
          <div className="space-y-3">
            {suggestions.map((s) => (
              <AgentSuggestionCard
                key={s.id}
                suggestion={s}
                onDismissed={(id) =>
                  setSuggestions((prev) => prev.filter((x) => x.id !== id))
                }
              />
            ))}
          </div>
        </div>
      )}

      {/* Stats row */}
      <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[
          {
            label: "Total runs",
            value: runs.length,
            sub: `across ${experiments.length - 1} experiments`,
          },
          {
            label: "GPU-hours",
            value: totalGpuH.toFixed(1) + "h",
            sub: "total compute",
          },
          {
            label: "Best val_acc",
            value: bestAcc > 0 ? bestAcc.toFixed(3) : "—",
            sub: "highest accuracy",
            accent: "text-emerald-300",
          },
          {
            label: "Failures",
            value: failedCount,
            sub: "failed or aborted",
            accent: "text-rose-300",
          },
        ].map(({ label, value, sub, accent }) => (
          <div
            key={label}
            className="rounded-3xl border border-slate-800/70 bg-slate-900/80 p-5 shadow-sm shadow-slate-950/30"
          >
            <div className="text-[10px] uppercase tracking-[0.25em] text-slate-500">
              {label}
            </div>
            <div className={`mt-3 text-3xl font-semibold ${accent || "text-slate-100"}`}>
              {value}
            </div>
            <div className="mt-2 text-xs tracking-[0.18em] text-slate-500 uppercase">
              {sub}
            </div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="mb-4 rounded-3xl border border-slate-800/70 bg-slate-900/80 p-4 shadow-sm shadow-slate-950/20">
        <div className="grid gap-3 md:grid-cols-[1.5fr_1fr_1fr]">
          <input
            type="text"
            placeholder="Search runs, configs, rationale…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className={`min-w-48 flex-1 placeholder-slate-500/70 ${input}`}
          />
          <select
            value={expFilter}
            onChange={(e) => setExpFilter(e.target.value)}
            className={input}
          >
          {experiments.map((e) => (
            <option key={e} value={e}>
              {e === "all" ? "All experiments" : e}
            </option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className={input}
        >
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s === "all" ? "All statuses" : s}
            </option>
          ))}
        </select>
      </div>
    </div>

      {/* Run list */}
      {loading ? (
        <div className="py-12 text-center text-sm text-muted">
          Loading runs…
        </div>
      ) : filtered.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-line bg-card/50 py-16 text-center text-sm text-muted">
          No runs match your filters.
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map((run) => (
            <RunCard
              key={run.run_id}
              run={run}
              onDeleted={(id) =>
                setRuns((prev) => prev.filter((r) => r.run_id !== id))
              }
            />
          ))}
        </div>
      )}
    </div>
  );
}
