import React, { useEffect, useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  LineChart,
  Line,
  CartesianGrid,
  ScatterChart,
  Scatter,
  LabelList,
} from "recharts";
import { getInsights, listRuns } from "../services/api";
import PageHeader from "../components/PageHeader";

const COFFEE = "#818CF8";
const OLIVE = "#34D399";
const TERRA = "#F87171";
const LINE = "#27272A";
const AMBER = "#FBBF24";

function acc(m = {}) {
  return m.val_accuracy ?? m.val_acc ?? m.accuracy ?? null;
}

// Feature 8: Derive failure stats from run list
function computeFailureStats(runs) {
  const byExperiment = {};
  for (const r of runs) {
    const exp = r.experiment || "unknown";
    if (!byExperiment[exp])
      byExperiment[exp] = { completed: 0, failed: 0, aborted: 0 };
    const s = r.status || "unknown";
    if (s === "completed") byExperiment[exp].completed++;
    else if (s === "failed") byExperiment[exp].failed++;
    else if (s === "aborted") byExperiment[exp].aborted++;
  }
  return Object.entries(byExperiment)
    .map(([exp, counts]) => ({
      experiment: exp.length > 18 ? exp.slice(0, 16) + "…" : exp,
      experimentFull: exp,
      ...counts,
      total: counts.completed + counts.failed + counts.aborted,
      failRate:
        counts.completed + counts.failed + counts.aborted > 0
          ? Math.round(
              ((counts.failed + counts.aborted) /
                (counts.completed + counts.failed + counts.aborted)) *
                100,
            )
          : 0,
    }))
    .filter((d) => d.total > 0)
    .sort((a, b) => b.failRate - a.failRate);
}

export default function InsightsPage() {
  const [insights, setInsights] = useState(null);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [param, setParam] = useState("");

  useEffect(() => {
    Promise.all([
      getInsights().catch(() => null),
      listRuns()
        .then((d) => d.runs || [])
        .catch(() => []),
    ])
      .then(([ins, rs]) => {
        setInsights(ins);
        setRuns(rs);
      })
      .finally(() => setLoading(false));
  }, []);

  const sensitivity = insights?.parameter_sensitivity || [];
  const bestPerDs = insights?.best_per_dataset || [];

  // metric-over-time
  const trend = [...runs]
    .filter((r) => acc(r.metrics) != null)
    .sort((a, b) => (a.timestamp || "").localeCompare(b.timestamp || ""))
    .map((r, i) => ({
      i: i + 1,
      value: acc(r.metrics),
      status: r.status,
      run: (r.run_id || "").slice(0, 8),
    }));

  // parameter-vs-result scatter
  const activeParam = param || sensitivity[0]?.parameter;
  const scatter = runs
    .filter(
      (r) =>
        activeParam &&
        (r.config || {})[activeParam] != null &&
        acc(r.metrics) != null,
    )
    .map((r) => ({
      x: Number(r.config[activeParam]) || r.config[activeParam],
      y: acc(r.metrics),
      run: (r.run_id || "").slice(0, 8),
    }));
  const numericScatter = scatter.every((p) => typeof p.x === "number");

  // Feature 8: failure stats
  const failureStats = computeFailureStats(runs);
  const totalFailed = runs.filter(
    (r) => r.status === "failed" || r.status === "aborted",
  ).length;
  const totalRuns = runs.length;
  const overallFailRate =
    totalRuns > 0 ? Math.round((totalFailed / totalRuns) * 100) : 0;
  const recentFailed = [...runs]
    .filter((r) => r.status === "failed" || r.status === "aborted")
    .sort((a, b) => (b.timestamp || "").localeCompare(a.timestamp || ""))
    .slice(0, 4);

  if (loading)
    return (
      <div className="p-8 text-center text-sm text-muted">
        Loading insights…
      </div>
    );

  const empty = sensitivity.length === 0 && trend.length === 0;

  return (
    <div className="mx-auto w-full max-w-6xl p-6 sm:p-8 lg:px-10">
      <PageHeader
        title="Insights"
        subtitle="What the memory has learned across this project's runs."
      />

      {empty && totalRuns === 0 ? (
        <div className="rounded-2xl border border-dashed border-line bg-card/50 py-16 text-center text-sm text-muted">
          Not enough runs yet — record at least 2 completed runs to derive
          insights.
        </div>
      ) : (
        <div className="space-y-6">
          {insights?.summary && (
            <div className="rounded-2xl border border-coffee/20 bg-coffee/5 p-4 text-sm text-cocoa">
              <span className="font-semibold text-coffee-deep">Summary · </span>
              {insights.summary}
            </div>
          )}

          {/* ── Parameter sensitivity ── */}
          {sensitivity.length > 0 && (
            <Card
              title="Parameter sensitivity"
              subtitle="How much each hyperparameter moves the metric (bigger = more impact)"
            >
              <ResponsiveContainer
                width="100%"
                height={Math.max(120, sensitivity.length * 44)}
              >
                <BarChart
                  data={sensitivity}
                  layout="vertical"
                  margin={{ left: 20, right: 30 }}
                >
                  <XAxis
                    type="number"
                    tick={{ fontSize: 11, fill: "#71717A" }}
                    axisLine={{ stroke: LINE }}
                    tickLine={{ stroke: LINE }}
                    stroke={LINE}
                  />
                  <YAxis
                    type="category"
                    dataKey="parameter"
                    width={110}
                    tick={{ fontSize: 12, fill: "#A1A1AA" }}
                    axisLine={{ stroke: LINE }}
                    tickLine={{ stroke: LINE }}
                    stroke={LINE}
                  />
                  <Tooltip
                    contentStyle={{
                      fontSize: 12,
                      borderRadius: 8,
                      border: `1px solid ${LINE}`,
                      backgroundColor: "#111113",
                    }}
                    formatter={(v, _n, p) => [
                      `${v}  (best: ${p.payload.best_value})`,
                      "impact",
                    ]}
                  />
                  <Bar dataKey="sensitivity" radius={[0, 6, 6, 0]}>
                    {sensitivity.map((_, i) => (
                      <Cell key={i} fill={i === 0 ? COFFEE : "#4F46E5"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}

          {/* ── Metric over time ── */}
          {trend.length > 1 && (
            <Card
              title="Metric over time"
              subtitle="Primary metric across runs in chronological order"
            >
              <ResponsiveContainer width="100%" height={220}>
                <LineChart
                  data={trend}
                  margin={{ left: 0, right: 20, top: 10 }}
                >
                  <CartesianGrid stroke={LINE} strokeDasharray="3 3" />
                  <XAxis
                    dataKey="i"
                    tick={{ fontSize: 11, fill: "#71717A" }}
                    axisLine={{ stroke: LINE }}
                    tickLine={{ stroke: LINE }}
                    stroke={LINE}
                    label={{
                      value: "run #",
                      position: "insideBottom",
                      offset: -2,
                      fontSize: 11,
                      fill: "#71717A",
                    }}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "#71717A" }}
                    axisLine={{ stroke: LINE }}
                    tickLine={{ stroke: LINE }}
                    stroke={LINE}
                    domain={["auto", "auto"]}
                  />
                  <Tooltip
                    contentStyle={{
                      fontSize: 12,
                      borderRadius: 8,
                      border: `1px solid ${LINE}`,
                      backgroundColor: "#111113",
                    }}
                    formatter={(v, _n, p) => [
                      `${v} (${p.payload.run}, ${p.payload.status})`,
                      "metric",
                    ]}
                  />
                  <Line
                    type="monotone"
                    dataKey="value"
                    stroke={COFFEE}
                    strokeWidth={2}
                    dot={{ r: 3, fill: COFFEE }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          )}

          {/* ── Parameter vs result scatter ── */}
          {sensitivity.length > 0 && numericScatter && scatter.length > 1 && (
            <Card
              title="Parameter vs. result"
              subtitle="See the sweet spot — and where it breaks"
            >
              <div className="mb-2 flex flex-wrap gap-2">
                {sensitivity.slice(0, 6).map((s) => (
                  <button
                    key={s.parameter}
                    onClick={() => setParam(s.parameter)}
                    className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${
                      activeParam === s.parameter
                        ? "border-coffee bg-coffee text-card"
                        : "border-line bg-card text-cocoa hover:bg-sand"
                    }`}
                  >
                    {s.parameter}
                  </button>
                ))}
              </div>
              <ResponsiveContainer width="100%" height={220}>
                <ScatterChart margin={{ left: 0, right: 20, top: 10 }}>
                  <CartesianGrid stroke={LINE} strokeDasharray="3 3" />
                  <XAxis
                    type="number"
                    dataKey="x"
                    name={activeParam}
                    tick={{ fontSize: 11, fill: "#71717A" }}
                    axisLine={{ stroke: LINE }}
                    tickLine={{ stroke: LINE }}
                    stroke={LINE}
                    label={{
                      value: activeParam,
                      position: "insideBottom",
                      offset: -2,
                      fontSize: 11,
                      fill: "#71717A",
                    }}
                  />
                  <YAxis
                    type="number"
                    dataKey="y"
                    name="metric"
                    tick={{ fontSize: 11, fill: "#71717A" }}
                    axisLine={{ stroke: LINE }}
                    tickLine={{ stroke: LINE }}
                    stroke={LINE}
                  />
                  <Tooltip
                    contentStyle={{
                      fontSize: 12,
                      borderRadius: 8,
                      border: `1px solid ${LINE}`,
                      backgroundColor: "#111113",
                    }}
                    cursor={{ strokeDasharray: "3 3" }}
                  />
                  <Scatter data={scatter} fill={OLIVE} />
                </ScatterChart>
              </ResponsiveContainer>
            </Card>
          )}

          {/* ── Feature 8: Failed Runs Analysis ── */}
          {totalRuns > 0 && (
            <Card
              title="Failed runs analysis"
              subtitle={`${totalFailed} of ${totalRuns} runs failed or were aborted (${overallFailRate}% failure rate)`}
            >
              {/* Stat strip */}
              <div className="mb-4 grid grid-cols-3 gap-3">
                {[
                  {
                    label: "Total runs",
                    value: totalRuns,
                    color: "text-espresso",
                  },
                  {
                    label: "Failed / Aborted",
                    value: totalFailed,
                    color: "text-terracotta",
                  },
                  {
                    label: "Failure rate",
                    value: `${overallFailRate}%`,
                    color:
                      overallFailRate > 30
                        ? "text-terracotta"
                        : overallFailRate > 10
                          ? "text-amber-600"
                          : "text-olive",
                  },
                ].map(({ label, value, color }) => (
                  <div
                    key={label}
                    className="rounded-xl border border-line bg-sand/50 p-3 text-center"
                  >
                    <div
                      className={`font-display text-2xl font-semibold ${color}`}
                    >
                      {value}
                    </div>
                    <div className="mt-0.5 text-xs text-muted">{label}</div>
                  </div>
                ))}
              </div>

              {/* Failure rate per experiment */}
              {failureStats.length > 0 && (
                <>
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
                    Failure rate by experiment
                  </div>
                  <ResponsiveContainer
                    width="100%"
                    height={Math.max(80, failureStats.length * 40)}
                  >
                    <BarChart
                      data={failureStats}
                      layout="vertical"
                      margin={{ left: 10, right: 50 }}
                    >
                      <XAxis
                        type="number"
                        domain={[0, 100]}
                        unit="%"
                        tick={{ fontSize: 10, fill: "#71717A" }}
                        axisLine={{ stroke: LINE }}
                        tickLine={{ stroke: LINE }}
                        stroke={LINE}
                      />
                      <YAxis
                        type="category"
                        dataKey="experiment"
                        width={120}
                        tick={{ fontSize: 11, fill: "#A1A1AA" }}
                        axisLine={{ stroke: LINE }}
                        tickLine={{ stroke: LINE }}
                        stroke={LINE}
                      />
                      <Tooltip
                        contentStyle={{
                          fontSize: 12,
                          borderRadius: 8,
                          border: `1px solid ${LINE}`,
                        }}
                        formatter={(v, _name, p) => [
                          `${v}% (${p.payload.failed + p.payload.aborted} of ${p.payload.total} runs)`,
                          p.payload.experimentFull,
                        ]}
                      />
                      <Bar
                        dataKey="failRate"
                        radius={[0, 6, 6, 0]}
                        maxBarSize={24}
                      >
                        {failureStats.map((d, i) => (
                          <Cell
                            key={i}
                            fill={
                              d.failRate > 50
                                ? TERRA
                                : d.failRate > 25
                                  ? AMBER
                                  : OLIVE
                            }
                          />
                        ))}
                        <LabelList
                          dataKey="failRate"
                          position="right"
                          formatter={(v) => `${v}%`}
                          style={{
                            fontSize: 11,
                            fill: "#6366F1",
                          }}
                        />
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </>
              )}

              {/* Recent failed runs list */}
              {recentFailed.length > 0 && (
                <div className="mt-4">
                  <div className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">
                    Recent failures
                  </div>
                  <div className="space-y-2">
                    {recentFailed.map((r) => {
                      const m = r.metrics || {};
                      const a = m.val_accuracy ?? m.val_acc ?? null;
                      return (
                        <div
                          key={r.run_id}
                          className="rounded-xl border border-terracotta/20 bg-terracotta/5 p-3"
                        >
                          <div className="flex items-start justify-between gap-2">
                            <div className="min-w-0">
                              <div className="flex items-center gap-2">
                                <code className="rounded bg-terracotta/10 px-1.5 py-0.5 font-mono text-xs text-terracotta">
                                  {(r.run_id || "").slice(0, 10)}…
                                </code>
                                <span className="text-xs text-muted">
                                  {r.experiment}
                                </span>
                              </div>
                              {r.error_message && (
                                <div className="mt-1 truncate font-mono text-xs text-terracotta/80">
                                  {r.error_message}
                                </div>
                              )}
                              {r.rationale && (
                                <div className="mt-0.5 line-clamp-1 text-xs text-muted">
                                  {r.rationale}
                                </div>
                              )}
                            </div>
                            <div className="shrink-0 text-right">
                              <div className="text-xs font-semibold uppercase text-terracotta">
                                {r.status}
                              </div>
                              {a != null && (
                                <div className="text-xs text-muted">
                                  acc={a}
                                </div>
                              )}
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {totalFailed === 0 && (
                <div className="py-6 text-center text-sm text-olive">
                  ✅ No failed or aborted runs — great experiment hygiene!
                </div>
              )}
            </Card>
          )}

          {/* ── Best per dataset ── */}
          {bestPerDs.length > 0 && (
            <Card
              title="Best config per dataset"
              subtitle="What worked best on each dataset"
            >
              <div className="space-y-2">
                {bestPerDs.map((d) => (
                  <div
                    key={d.dataset}
                    className="rounded-xl border border-line bg-sand/60 p-3"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold text-espresso">
                        {d.dataset}
                      </span>
                      <span className="font-mono text-sm text-olive">
                        {d.metric}={d.metric_value}
                      </span>
                    </div>
                    <code className="mt-1 block break-all text-xs text-cocoa">
                      {JSON.stringify(d.best_config)}
                    </code>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}

function Card({ title, subtitle, children }) {
  return (
    <div className="rounded-2xl border border-line bg-card p-5 shadow-soft">
      <div className="mb-3">
        <div className="text-sm font-semibold text-espresso">{title}</div>
        {subtitle && <div className="text-xs text-muted">{subtitle}</div>}
      </div>
      {children}
    </div>
  );
}
