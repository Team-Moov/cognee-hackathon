import React, { useEffect, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
  LineChart, Line, CartesianGrid, ScatterChart, Scatter,
} from "recharts";
import { getInsights, listRuns } from "../services/api";

const COFFEE = "#7B5836";
const OLIVE = "#5E7A46";
const TERRA = "#B14A34";
const LINE = "#DECBAA";

function acc(m = {}) {
  return m.val_accuracy ?? m.val_acc ?? m.accuracy ?? null;
}

export default function InsightsPage() {
  const [insights, setInsights] = useState(null);
  const [runs, setRuns] = useState([]);
  const [loading, setLoading] = useState(true);
  const [param, setParam] = useState("");

  useEffect(() => {
    Promise.all([getInsights().catch(() => null), listRuns().then((d) => d.runs || []).catch(() => [])])
      .then(([ins, rs]) => { setInsights(ins); setRuns(rs); })
      .finally(() => setLoading(false));
  }, []);

  const sensitivity = insights?.parameter_sensitivity || [];
  const bestPerDs = insights?.best_per_dataset || [];

  // metric-over-time
  const trend = [...runs]
    .filter((r) => acc(r.metrics) != null)
    .sort((a, b) => (a.timestamp || "").localeCompare(b.timestamp || ""))
    .map((r, i) => ({ i: i + 1, value: acc(r.metrics), status: r.status, run: (r.run_id || "").slice(0, 8) }));

  // parameter-vs-result scatter (for the chosen / top param)
  const activeParam = param || sensitivity[0]?.parameter;
  const scatter = runs
    .filter((r) => activeParam && (r.config || {})[activeParam] != null && acc(r.metrics) != null)
    .map((r) => ({ x: Number(r.config[activeParam]) || r.config[activeParam], y: acc(r.metrics), run: (r.run_id || "").slice(0, 8) }));
  const numericScatter = scatter.every((p) => typeof p.x === "number");

  if (loading) return <div className="p-8 text-center text-sm text-muted">Loading insights…</div>;

  const empty = sensitivity.length === 0 && trend.length === 0;

  return (
    <div className="mx-auto max-w-4xl p-6 sm:p-8">
      <div className="mb-6">
        <h1 className="font-display text-3xl font-semibold text-espresso">Insights</h1>
        <p className="mt-1 text-sm text-muted">What the memory has learned across this project's runs.</p>
      </div>

      {empty ? (
        <div className="rounded-2xl border border-dashed border-line bg-card/50 py-16 text-center text-sm text-muted">
          Not enough runs yet — record at least 2 completed runs to derive insights.
        </div>
      ) : (
        <div className="space-y-6">
          {insights?.summary && (
            <div className="rounded-2xl border border-coffee/20 bg-coffee/5 p-4 text-sm text-cocoa">
              <span className="font-semibold text-coffee-deep">Summary · </span>{insights.summary}
            </div>
          )}

          {/* Parameter sensitivity */}
          {sensitivity.length > 0 && (
            <Card title="Parameter sensitivity" subtitle="How much each hyperparameter moves the metric (bigger = more impact)">
              <ResponsiveContainer width="100%" height={Math.max(120, sensitivity.length * 44)}>
                <BarChart data={sensitivity} layout="vertical" margin={{ left: 20, right: 30 }}>
                  <XAxis type="number" tick={{ fontSize: 11, fill: "#93795C" }} />
                  <YAxis type="category" dataKey="parameter" width={110} tick={{ fontSize: 12, fill: "#4E3A2A" }} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: `1px solid ${LINE}` }}
                    formatter={(v, _n, p) => [`${v}  (best: ${p.payload.best_value})`, "impact"]} />
                  <Bar dataKey="sensitivity" radius={[0, 6, 6, 0]}>
                    {sensitivity.map((_, i) => <Cell key={i} fill={i === 0 ? COFFEE : "#A07C55"} />)}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </Card>
          )}

          {/* Metric over time */}
          {trend.length > 1 && (
            <Card title="Metric over time" subtitle="Primary metric across runs in chronological order">
              <ResponsiveContainer width="100%" height={220}>
                <LineChart data={trend} margin={{ left: 0, right: 20, top: 10 }}>
                  <CartesianGrid stroke={LINE} strokeDasharray="3 3" />
                  <XAxis dataKey="i" tick={{ fontSize: 11, fill: "#93795C" }} label={{ value: "run #", position: "insideBottom", offset: -2, fontSize: 11, fill: "#93795C" }} />
                  <YAxis tick={{ fontSize: 11, fill: "#93795C" }} domain={["auto", "auto"]} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: `1px solid ${LINE}` }}
                    formatter={(v, _n, p) => [`${v} (${p.payload.run}, ${p.payload.status})`, "metric"]} />
                  <Line type="monotone" dataKey="value" stroke={COFFEE} strokeWidth={2} dot={{ r: 3, fill: COFFEE }} />
                </LineChart>
              </ResponsiveContainer>
            </Card>
          )}

          {/* Parameter vs result */}
          {sensitivity.length > 0 && numericScatter && scatter.length > 1 && (
            <Card title="Parameter vs. result" subtitle="See the sweet spot — and where it breaks">
              <div className="mb-2 flex flex-wrap gap-2">
                {sensitivity.slice(0, 6).map((s) => (
                  <button key={s.parameter} onClick={() => setParam(s.parameter)}
                    className={`rounded-full border px-2.5 py-1 text-xs transition-colors ${activeParam === s.parameter ? "border-coffee bg-coffee text-card" : "border-line bg-card text-cocoa hover:bg-sand"}`}>
                    {s.parameter}
                  </button>
                ))}
              </div>
              <ResponsiveContainer width="100%" height={220}>
                <ScatterChart margin={{ left: 0, right: 20, top: 10 }}>
                  <CartesianGrid stroke={LINE} strokeDasharray="3 3" />
                  <XAxis type="number" dataKey="x" name={activeParam} tick={{ fontSize: 11, fill: "#93795C" }}
                    label={{ value: activeParam, position: "insideBottom", offset: -2, fontSize: 11, fill: "#93795C" }} />
                  <YAxis type="number" dataKey="y" name="metric" tick={{ fontSize: 11, fill: "#93795C" }} />
                  <Tooltip contentStyle={{ fontSize: 12, borderRadius: 8, border: `1px solid ${LINE}` }} cursor={{ strokeDasharray: "3 3" }} />
                  <Scatter data={scatter} fill={OLIVE} />
                </ScatterChart>
              </ResponsiveContainer>
            </Card>
          )}

          {/* Best per dataset */}
          {bestPerDs.length > 0 && (
            <Card title="Best config per dataset" subtitle="What worked best on each dataset">
              <div className="space-y-2">
                {bestPerDs.map((d) => (
                  <div key={d.dataset} className="rounded-xl border border-line bg-sand/60 p-3">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold text-espresso">{d.dataset}</span>
                      <span className="font-mono text-sm text-olive">{d.metric}={d.metric_value}</span>
                    </div>
                    <code className="mt-1 block break-all text-xs text-cocoa">{JSON.stringify(d.best_config)}</code>
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
