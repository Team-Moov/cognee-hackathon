import React, { useState, useEffect } from "react";
import { findFile, getOrphans } from "../services/api";
import PageHeader from "../components/PageHeader";

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

  const FIND_EXAMPLES = [
    "best checkpoint",
    "bert model",
    "loss curve plot",
    "cifar eval report",
    "gpt2 perplexity",
  ];

  return (
    <div className="mx-auto w-full max-w-5xl p-6 sm:p-8 lg:px-10">
      <PageHeader
        title="File Finder"
        subtitle="Locate any artifact by description — no more spelunking through run_47_v2_final_FINAL/."
      />

      {/* Find file */}
      <div className="mb-6 rounded-2xl border border-line bg-card p-5 shadow-soft">
        <div className="mb-3 text-sm font-semibold text-espresso">
          Find Artifact
        </div>
        <form onSubmit={handleFind} className="flex gap-2">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="e.g. best checkpoint, loss curve plot…"
            className="flex-1 rounded-xl border border-line bg-paper px-3 py-2 text-sm text-cocoa placeholder-muted/70 focus:border-coffee focus:outline-none focus:ring-2 focus:ring-coffee/20"
          />
          <button
            type="submit"
            disabled={findLoading || !query.trim()}
            className="rounded-xl bg-coffee px-4 py-2 text-sm font-semibold text-card transition-colors hover:bg-coffee-deep disabled:opacity-40"
          >
            {findLoading ? "…" : "Find"}
          </button>
        </form>
        <div className="mt-2 flex flex-wrap gap-2">
          {FIND_EXAMPLES.map((ex) => (
            <button
              key={ex}
              onClick={() => {
                setQuery(ex);
              }}
              className="rounded border border-line bg-sand px-2 py-1 text-xs text-cocoa transition-colors hover:bg-hover"
            >
              {ex}
            </button>
          ))}
        </div>

        {findResult && (
          <div className="fade-in mt-4 rounded-xl border border-olive/30 bg-olive/8 p-4">
            <div className="mb-2 flex items-center gap-2">
              <span className="text-sm font-semibold text-olive">Found</span>
              <span className="text-xs text-muted">
                {findResult.artifact_type}
              </span>
            </div>
            <code className="block break-all font-mono text-xs text-cocoa">
              {findResult.path}
            </code>
            <div className="mt-1.5 flex gap-4 text-xs text-muted">
              <span>
                Run:{" "}
                <code className="text-coffee-deep">{findResult.run_id}</code>
              </span>
              <span
                className={
                  findResult.exists_on_disk ? "text-olive" : "text-ochre"
                }
              >
                {findResult.exists_on_disk
                  ? "exists on disk"
                  : "not on this machine (remote path)"}
              </span>
            </div>
          </div>
        )}

        {findError && (
          <div className="mt-4 rounded-xl border border-ochre/25 bg-ochre/10 p-3 text-sm text-ochre">
            {findError}
          </div>
        )}
      </div>

      {/* Orphans */}
      <div className="rounded-2xl border border-line bg-card p-5 shadow-soft">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <div className="text-sm font-semibold text-espresso">
              Orphan Detection
            </div>
            <div className="mt-0.5 text-xs text-muted">
              Files with no graph node, and graph nodes whose file is missing.
            </div>
          </div>
          {orphans && (
            <div className="text-right">
              <div className="font-display text-lg font-semibold text-ochre">
                {orphans.untracked_size_gb} GB
              </div>
              <div className="text-xs text-muted">untracked</div>
            </div>
          )}
        </div>

        {orphansLoading && (
          <div className="py-4 text-center text-sm text-muted">Scanning…</div>
        )}

        {orphans && (
          <div className="space-y-4">
            <div>
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-ochre">
                Untracked Files ({orphans.untracked_files.length})
              </div>
              <div className="space-y-1">
                {orphans.untracked_files.map((f) => (
                  <div
                    key={f}
                    className="break-all rounded-lg border border-line bg-paper px-3 py-1.5 font-mono text-xs text-cocoa"
                  >
                    {f}
                  </div>
                ))}
              </div>
            </div>

            <div>
              <div className="mb-2 text-xs font-semibold uppercase tracking-wide text-terracotta">
                Broken References ({orphans.broken_nodes.length})
              </div>
              <div className="space-y-1">
                {orphans.broken_nodes.map((n) => (
                  <div
                    key={n.missing_path}
                    className="rounded-lg border border-terracotta/25 bg-terracotta/8 px-3 py-1.5 text-xs"
                  >
                    <code className="block break-all font-mono text-terracotta">
                      {n.missing_path}
                    </code>
                    <span className="text-muted">run: {n.run_id}</span>
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
