import React, { useState } from "react";
import { checkConfig } from "../services/api";
import StatusBadge from "../components/StatusBadge";
import { useNavigate } from "react-router-dom";

const PRESETS = [
  { label: "ResNet50 + Adam (already tried!)", config: { model: "ResNet50", optimizer: "Adam", lr: 0.001, batch_size: 64, epochs: 50 } },
  { label: "VGG16 + Adam (failed run)", config: { model: "VGG16", optimizer: "Adam", lr: 0.001, batch_size: 128, epochs: 30 } },
  { label: "BERT + AdamW (best run!)", config: { model: "bert-base-uncased", optimizer: "AdamW", lr: 2e-5, batch_size: 16, epochs: 3, max_seq_len: 512 } },
  { label: "New config (safe to run)", config: { model: "EfficientNetB0", optimizer: "AdamW", lr: 0.0003, batch_size: 64, epochs: 30 } },
];

const CONFIG_FIELDS = [
  { key: "model",      label: "Model",      placeholder: "ResNet50" },
  { key: "optimizer",  label: "Optimizer",  placeholder: "Adam" },
  { key: "lr",         label: "Learn. Rate",placeholder: "0.001" },
  { key: "batch_size", label: "Batch Size", placeholder: "64" },
  { key: "epochs",     label: "Epochs",     placeholder: "50" },
];

export default function PreflightGuard() {
  const [fields, setFields] = useState({ model: "", optimizer: "", lr: "", batch_size: "", epochs: "" });
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const nav = useNavigate();

  function setField(key, val) {
    setFields(f => ({ ...f, [key]: val }));
    setResult(null);
  }

  function applyPreset(cfg) {
    setFields({
      model: String(cfg.model || ""),
      optimizer: String(cfg.optimizer || ""),
      lr: String(cfg.lr || ""),
      batch_size: String(cfg.batch_size || ""),
      epochs: String(cfg.epochs || ""),
    });
    setResult(null);
    setError(null);
  }

  async function handleCheck(e) {
    e.preventDefault();
    setLoading(true);
    setResult(null);
    setError(null);
    const config = {};
    for (const { key } of CONFIG_FIELDS) {
      const v = fields[key];
      if (!v) continue;
      const n = Number(v);
      config[key] = isNaN(n) ? v : n;
    }
    try {
      const res = await checkConfig(config);
      setResult(res);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const matchType = result?.match_type;

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">🛡️ Pre-flight Guard</h1>
        <p className="text-zinc-500 text-sm mt-1">Check if a config has been tried before — save GPU-hours before you waste them.</p>
      </div>

      {/* Presets */}
      <div className="mb-5">
        <div className="text-xs text-zinc-500 mb-2 uppercase tracking-wide">Quick presets</div>
        <div className="flex gap-2 flex-wrap">
          {PRESETS.map(p => (
            <button
              key={p.label}
              onClick={() => applyPreset(p.config)}
              className="text-xs bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 text-zinc-300 px-3 py-1.5 rounded-lg transition-colors"
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Config form */}
      <form onSubmit={handleCheck} className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          {CONFIG_FIELDS.map(({ key, label, placeholder }) => (
            <div key={key}>
              <label className="block text-xs text-zinc-400 mb-1">{label}</label>
              <input
                type="text"
                value={fields[key]}
                onChange={e => setField(key, e.target.value)}
                placeholder={placeholder}
                className="w-full bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm font-mono text-zinc-100 placeholder-zinc-600 focus:outline-none focus:border-indigo-500"
              />
            </div>
          ))}
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white font-semibold py-2.5 rounded-lg transition-colors text-sm"
        >
          {loading ? "Checking memory…" : "Check Config →"}
        </button>
      </form>

      {/* Error */}
      {error && (
        <div className="mt-4 text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg p-3">{error}</div>
      )}

      {/* Result — ALREADY TRIED (exact) */}
      {result && matchType === "exact" && (
        <div className="mt-5 fade-in">
          <div className="bg-red-950/60 border-2 border-red-500/60 rounded-xl p-5 pulse-danger">
            <div className="flex items-center gap-3 mb-3">
              <span className="text-3xl">⚠️</span>
              <div>
                <div className="text-red-400 font-bold text-lg">ALREADY TRIED</div>
                <div className="text-red-300 text-sm">Exact config match found — do not waste compute.</div>
              </div>
            </div>

            {result.matching_runs.map(run => (
              <PriorRunCard key={run.run_id} run={run} nav={nav} />
            ))}

            <div className="mt-3 text-sm text-red-300 bg-red-900/30 rounded-lg p-3 border border-red-500/20">
              💡 {result.recommendation}
            </div>
          </div>
        </div>
      )}

      {/* Result — SIMILAR */}
      {result && matchType === "similar" && (
        <div className="mt-5 fade-in">
          <div className="bg-amber-950/60 border-2 border-amber-500/50 rounded-xl p-5">
            <div className="flex items-center gap-3 mb-3">
              <span className="text-3xl">🔶</span>
              <div>
                <div className="text-amber-400 font-bold text-lg">SIMILAR CONFIG FOUND</div>
                <div className="text-amber-300 text-sm">{(result.similarity_score * 100).toFixed(0)}% match — review before running.</div>
              </div>
            </div>

            {result.matching_runs.map(run => (
              <PriorRunCard key={run.run_id} run={run} nav={nav} />
            ))}

            <div className="mt-3 text-sm text-amber-300 bg-amber-900/20 rounded-lg p-3 border border-amber-500/20">
              💡 {result.recommendation}
            </div>
          </div>
        </div>
      )}

      {/* Result — SAFE */}
      {result && matchType === "none" && (
        <div className="mt-5 fade-in">
          <div className="bg-emerald-950/60 border-2 border-emerald-500/40 rounded-xl p-5">
            <div className="flex items-center gap-3">
              <span className="text-3xl">✅</span>
              <div>
                <div className="text-emerald-400 font-bold text-lg">SAFE TO RUN</div>
                <div className="text-emerald-300 text-sm">No matching or similar config in memory. Proceed.</div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function PriorRunCard({ run, nav }) {
  const mainMetric = run.metrics?.val_acc ?? run.metrics?.perplexity;
  const metricLabel = run.metrics?.val_acc != null ? "val_acc" : "perplexity";
  return (
    <div
      onClick={() => nav(`/lineage/${run.run_id}`)}
      className="bg-zinc-900/80 rounded-lg p-3 border border-zinc-700/50 cursor-pointer hover:border-zinc-600 transition-colors"
    >
      <div className="flex items-center justify-between mb-2">
        <code className="text-xs text-indigo-400 font-mono">{run.run_id}</code>
        <StatusBadge status={run.status} />
      </div>
      <div className="flex gap-4 text-xs text-zinc-400 flex-wrap">
        {mainMetric != null && <span><span className="text-zinc-500">{metricLabel}: </span><span className="text-zinc-200 font-mono">{mainMetric.toFixed ? mainMetric.toFixed(3) : mainMetric}</span></span>}
        {run.gpu_hours != null && <span><span className="text-zinc-500">GPU: </span><span className="text-zinc-200 font-mono">{run.gpu_hours}h</span></span>}
        {run.date && <span><span className="text-zinc-500">Date: </span>{run.date.slice(0, 10)}</span>}
      </div>
      {run.rationale && (
        <div className="mt-1.5 text-xs text-zinc-500 italic truncate">"{run.rationale}"</div>
      )}
      <div className="mt-1 text-xs text-indigo-400/60 hover:text-indigo-400">View full lineage →</div>
    </div>
  );
}
