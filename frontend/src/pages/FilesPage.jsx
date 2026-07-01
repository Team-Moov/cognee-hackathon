import React, { useState, useEffect } from "react";
import { findFile, getOrphans } from "../services/api";

export default function FilesPage() {
  const [query, setQuery] = useState("");
  const [findResult, setFindResult] = useState(null);
  const [findError, setFindError] = useState(null);
  const [findLoading, setFindLoading] = useState(false);
  const [orphans, setOrphans] = useState(null);
  const [orphansLoading, setOrphansLoading] = useState(true);

  useEffect(() => {
    getOrphans()
      .then(setOrphans)
      .catch(() => setOrphans(null))
      .finally(() => setOrphansLoading(false));
  }, []);

  async function handleFind(e) {
    e.preventDefault();
    if (!query.trim()) return;
    setFindLoading(true);
    setFindResult(null);
    setFindError(null);
    try {
      const res = await findFile(query);
      setFindResult(res);
    } catch (err) {
      setFindError(`No artifact matching "${query}"`);
    } finally {
      setFindLoading(false);
    }
  }

  const FIND_EXAMPLES = ["best checkpoint", "bert model", "loss curve plot", "cifar eval report", "gpt2 perplexity"];

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">📁 File Finder</h1>
        <p className="text-zinc-500 text-sm mt-1">Locate any artifact by description — no more spelunking through run_47_v2_final_FINAL/.</p>
      </div>

      {/* Find file */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5 mb-6">
        <div className="text-sm font-semibold text-zinc-200 mb-3">Find Artifact</div>
        <form onSubmit={handleFind} className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="e.g. best checkpoint, loss curve plot…"
            className="flex-1 bg-zinc-800 border border-zinc-700 rounded-lg px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
          />
          <button
            type="submit"
            disabled={findLoading || !query.trim()}
            className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
          >
            {findLoading ? "…" : "Find"}
          </button>
        </form>
        <div className="mt-2 flex gap-2 flex-wrap">
          {FIND_EXAMPLES.map(ex => (
            <button
              key={ex}
              onClick={() => { setQuery(ex); }}
              className="text-xs text-zinc-500 hover:text-zinc-300 bg-zinc-800 border border-zinc-700 px-2 py-1 rounded transition-colors"
            >{ex}</button>
          ))}
        </div>

        {findResult && (
          <div className="mt-4 fade-in bg-emerald-950/40 border border-emerald-500/30 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-emerald-400 font-semibold text-sm">Found</span>
              <span className="text-xs text-zinc-500">{findResult.artifact_type}</span>
            </div>
            <code className="text-xs text-zinc-200 font-mono block break-all">{findResult.path}</code>
            <div className="mt-1.5 flex gap-4 text-xs text-zinc-500">
              <span>Run: <code className="text-indigo-400">{findResult.run_id}</code></span>
              <span className={findResult.exists_on_disk ? "text-emerald-400" : "text-amber-400"}>
                {findResult.exists_on_disk ? "✓ exists on disk" : "⚠ not on this machine (remote path)"}
              </span>
            </div>
          </div>
        )}

        {findError && (
          <div className="mt-4 text-amber-400 text-sm bg-amber-950/30 border border-amber-500/20 rounded-lg p-3">{findError}</div>
        )}
      </div>

      {/* Orphans */}
      <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <div>
            <div className="text-sm font-semibold text-zinc-200">Orphan Detection</div>
            <div className="text-xs text-zinc-500 mt-0.5">Files with no graph node, and graph nodes whose file is missing.</div>
          </div>
          {orphans && (
            <div className="text-right">
              <div className="text-lg font-bold text-amber-400">{orphans.untracked_size_gb} GB</div>
              <div className="text-xs text-zinc-500">untracked</div>
            </div>
          )}
        </div>

        {orphansLoading && <div className="text-zinc-500 text-sm text-center py-4">Scanning…</div>}

        {orphans && (
          <div className="space-y-4">
            <div>
              <div className="text-xs font-semibold text-amber-400 uppercase tracking-wide mb-2">
                Untracked Files ({orphans.untracked_files.length})
              </div>
              <div className="space-y-1">
                {orphans.untracked_files.map(f => (
                  <div key={f} className="text-xs font-mono text-zinc-400 bg-zinc-800 px-3 py-1.5 rounded border border-zinc-700 break-all">{f}</div>
                ))}
              </div>
            </div>

            <div>
              <div className="text-xs font-semibold text-red-400 uppercase tracking-wide mb-2">
                Broken References ({orphans.broken_nodes.length})
              </div>
              <div className="space-y-1">
                {orphans.broken_nodes.map(n => (
                  <div key={n.missing_path} className="text-xs bg-red-950/30 border border-red-500/20 rounded px-3 py-1.5">
                    <code className="text-red-400 font-mono block break-all">{n.missing_path}</code>
                    <span className="text-zinc-500">run: {n.run_id}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
