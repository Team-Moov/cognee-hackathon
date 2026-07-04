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
    <div className="mx-auto max-w-2xl p-6 sm:p-8">
      <div className="mb-6">
        <h1 className="font-display text-3xl font-semibold text-espresso">Pre-flight Guard</h1>
        <p className="mt-1 text-sm text-muted">Check if a config has been tried before — save GPU-hours before you waste them.</p>
      </div>

      {/* Presets */}
      <div className="mb-5">
        <div className="mb-2 text-xs uppercase tracking-wide text-muted">Quick presets</div>
        <div className="flex flex-wrap gap-2">
          {PRESETS.map(p => (
            <button
              key={p.label}
              onClick={() => applyPreset(p.config)}
              className="rounded-full border border-line bg-card px-3 py-1.5 text-xs text-cocoa transition-colors hover:bg-sand"
            >
              {p.label}
            </button>
          ))}
        </div>
      </div>

      {/* Config form */}
      <form onSubmit={handleCheck} className="space-y-4 rounded-2xl border border-line bg-card p-5 shadow-soft">
        <div className="grid grid-cols-2 gap-4">
          {CONFIG_FIELDS.map(({ key, label, placeholder }) => (
            <div key={key}>
              <label className="mb-1 block text-xs text-cocoa">{label}</label>
              <input
                type="text"
                value={fields[key]}
                onChange={e => setField(key, e.target.value)}
                placeholder={placeholder}
                className="w-full rounded-xl border border-line bg-paper px-3 py-2 font-mono text-sm text-cocoa placeholder-muted/60 focus:border-coffee focus:outline-none focus:ring-2 focus:ring-coffee/20"
              />
            </div>
          ))}
        </div>

        <button
          type="submit"
          disabled={loading}
          className="w-full rounded-xl bg-coffee py-2.5 text-sm font-semibold text-card shadow-soft transition-colors hover:bg-coffee-deep disabled:opacity-50"
        >
          {loading ? "Checking memory…" : "Check Config →"}
        </button>
      </form>

      {/* Error */}
      {error && (
        <div className="mt-4 rounded-xl border border-terracotta/25 bg-terracotta/10 p-3 text-sm text-terracotta">{error}</div>
      )}

      {/* Result — ALREADY TRIED (exact) */}
      {result && matchType === "exact" && (
        <div className="fade-in mt-5">
          <div className="pulse-danger rounded-2xl border-2 border-terracotta/50 bg-terracotta/8 p-5">
            <div className="mb-3 flex items-center gap-3">
              <span className="h-9 w-1.5 flex-shrink-0 rounded-full bg-terracotta" />
              <div>
                <div className="font-display text-lg font-semibold text-terracotta">ALREADY TRIED</div>
                <div className="text-sm text-cocoa">Exact config match found — do not waste compute.</div>
              </div>
            </div>

            {result.matching_runs.map(run => (
              <PriorRunCard key={run.run_id} run={run} nav={nav} />
            ))}

            <div className="mt-3 rounded-xl border border-terracotta/25 bg-terracotta/10 p-3 text-sm text-cocoa">
              <span className="font-semibold text-terracotta">Recommendation · </span>{result.recommendation}
            </div>
          </div>
        </div>
      )}

      {/* Result — SIMILAR */}
      {result && matchType === "similar" && (
        <div className="fade-in mt-5">
          <div className="rounded-2xl border-2 border-ochre/45 bg-ochre/8 p-5">
            <div className="mb-3 flex items-center gap-3">
              <span className="h-9 w-1.5 flex-shrink-0 rounded-full bg-ochre" />
              <div>
                <div className="font-display text-lg font-semibold text-ochre">SIMILAR CONFIG FOUND</div>
                <div className="text-sm text-cocoa">{(result.similarity_score * 100).toFixed(0)}% match — review before running.</div>
              </div>
            </div>

            {result.matching_runs.map(run => (
              <PriorRunCard key={run.run_id} run={run} nav={nav} />
            ))}

            <div className="mt-3 rounded-xl border border-ochre/25 bg-ochre/10 p-3 text-sm text-cocoa">
              <span className="font-semibold text-ochre">Recommendation · </span>{result.recommendation}
            </div>
          </div>
        </div>
      )}

      {/* Result — SAFE */}
      {result && matchType === "none" && (
        <div className="fade-in mt-5">
          <div className="rounded-2xl border-2 border-olive/40 bg-olive/8 p-5">
            <div className="flex items-center gap-3">
              <span className="h-9 w-1.5 flex-shrink-0 rounded-full bg-olive" />
              <div>
                <div className="font-display text-lg font-semibold text-olive">SAFE TO RUN</div>
                <div className="text-sm text-cocoa">No matching or similar config in memory. Proceed.</div>
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
      className="cursor-pointer rounded-xl border border-line bg-card p-3 transition-colors hover:border-coffee/40"
    >
      <div className="mb-2 flex items-center justify-between">
        <code className="font-mono text-xs text-coffee-deep">{run.run_id}</code>
        <StatusBadge status={run.status} />
      </div>
      <div className="flex flex-wrap gap-4 text-xs text-cocoa">
        {mainMetric != null && <span><span className="text-muted">{metricLabel}: </span><span className="font-mono text-espresso">{mainMetric.toFixed ? mainMetric.toFixed(3) : mainMetric}</span></span>}
        {run.gpu_hours != null && <span><span className="text-muted">GPU: </span><span className="font-mono text-espresso">{run.gpu_hours}h</span></span>}
        {run.date && <span><span className="text-muted">Date: </span>{run.date.slice(0, 10)}</span>}
      </div>
      {run.rationale && (
        <div className="mt-1.5 truncate text-xs italic text-muted">"{run.rationale}"</div>
      )}
      <div className="mt-1 text-xs text-coffee/70 hover:text-coffee">View full lineage →</div>
    </div>
  );
}
