import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getLineage } from "../services/api";
import PageHeader from "../components/PageHeader";

const NODE_STYLES = {
  hypothesis: { bg: "bg-coffee/8 border-coffee/30", accent: "bg-coffee",     label: "HYPOTHESIS", text: "text-coffee-deep" },
  decision:   { bg: "bg-ochre/8 border-ochre/30",   accent: "bg-ochre",      label: "DECISION",   text: "text-ochre"      },
  config:     { bg: "bg-sand border-line",          accent: "bg-muted",      label: "CONFIG",     text: "text-cocoa"      },
  result:     { bg: "bg-olive/8 border-olive/30",   accent: "bg-olive",      label: "RESULT",     text: "text-olive"      },
  artifact:   { bg: "bg-card border-line",          accent: "bg-muted",      label: "ARTIFACT",   text: "text-muted"      },
};

const STATUS_COLORS = {
  supported: "text-olive",
  refuted:   "text-terracotta",
  open:      "text-muted",
  completed: "text-olive",
  aborted:   "text-ochre",
  failed:    "text-terracotta",
};

const EDGE_LABELS = {
  produced:     "produced →",
  followed_by:  "led to →",
  derived_from: "derived from →",
  belongs_to:   "belongs to →",
};

function NodeCard({ node }) {
  const [expanded, setExpanded] = useState(false);
  const style = NODE_STYLES[node.type] || NODE_STYLES.artifact;
  const d = node.data;

  const title =
    d.statement || d.description || d.model ||
    (d.run_id ? `Run ${d.run_id}` : node.id);

  const statusKey = d.status;
  const statusColor = STATUS_COLORS[statusKey] || "text-muted";

  return (
    <div
      onClick={() => setExpanded(x => !x)}
      className={`cursor-pointer rounded-xl border p-3 shadow-soft transition-all hover:shadow-lift ${style.bg}`}
    >
      <div className="flex items-start gap-3">
        <span className={`mt-0.5 h-8 w-1 flex-shrink-0 rounded-full ${style.accent}`} />
        <div className="min-w-0 flex-1">
          <div className={`mb-1 text-xs font-bold uppercase tracking-wider ${style.text}`}>{style.label}</div>
          <div className="text-sm leading-snug text-espresso">{title}</div>

          {d.rationale && (
            <div className="mt-1 text-xs italic text-muted">{expanded ? d.rationale : `${d.rationale.slice(0,80)}${d.rationale.length > 80 ? "…" : ""}`}</div>
          )}

          {statusKey && (
            <div className={`mt-1 text-xs font-medium ${statusColor}`}>{statusKey}</div>
          )}

          {expanded && (
            <div className="mt-2 space-y-1">
              {Object.entries(d).filter(([k]) => !["statement","description","rationale","status","run_id","made_by","timestamp","file_path","artifact_type"].includes(k)).map(([k, v]) => (
                <div key={k} className="text-xs font-mono">
                  <span className="text-muted">{k}: </span>
                  <span className="text-cocoa">{JSON.stringify(v)}</span>
                </div>
              ))}
              {d.timestamp && <div className="text-xs text-muted/70">{d.timestamp?.slice?.(0,16)}</div>}
              {d.made_by   && <div className="text-xs text-muted">by {d.made_by}</div>}
              {d.gpu_hours && <div className="text-xs text-muted">{d.gpu_hours}h GPU</div>}
            </div>
          )}
        </div>
        <span className="text-xs text-muted">{expanded ? "▲" : "▼"}</span>
      </div>
    </div>
  );
}

export default function LineageExplorer() {
  const { runId } = useParams();
  const nav = useNavigate();
  const [lineage, setLineage] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    setLoading(true);
    setError(null);
    getLineage(runId)
      .then(setLineage)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [runId]);

  // Build ordered chain from edges
  function buildChain(nodes, edges) {
    if (!nodes || !edges) return nodes || [];
    const nodeMap = Object.fromEntries(nodes.map(n => [n.id, n]));
    const indegree = {};
    nodes.forEach(n => { indegree[n.id] = 0; });
    edges.forEach(e => { if (indegree[e.target] != null) indegree[e.target]++; });
    const roots = nodes.filter(n => indegree[n.id] === 0);
    const visited = new Set();
    const chain = [];
    const queue = [...roots];
    while (queue.length) {
      const node = queue.shift();
      if (visited.has(node.id)) continue;
      visited.add(node.id);
      chain.push({ node, edge: edges.find(e => e.target === node.id) });
      const nexts = edges.filter(e => e.source === node.id).map(e => nodeMap[e.target]).filter(Boolean);
      queue.push(...nexts);
    }
    return chain;
  }

  return (
    <div className="mx-auto w-full max-w-5xl p-6 sm:p-8 lg:px-10">
      <button
        onClick={() => nav("/dashboard")}
        className="mb-4 flex items-center gap-1 text-sm text-stone-600 transition-colors hover:text-stone-900"
      >
        ← Back to Dashboard
      </button>

      <PageHeader
        title="Lineage Explorer"
        subtitle={runId}
      />

      {loading && <div className="py-12 text-center text-sm text-muted">Loading lineage…</div>}
      {error   && <div className="py-12 text-center text-sm text-terracotta">Error: {error}</div>}

      {lineage && (
        <div className="space-y-1">
          {buildChain(lineage.nodes, lineage.edges).map(({ node, edge }, i) => (
            <React.Fragment key={node.id}>
              {edge && (
                <div className="flex items-center justify-center py-1">
                  <div className="rounded-full border border-line bg-card px-3 py-1 text-xs text-muted">
                    {EDGE_LABELS[edge.type] || edge.type}
                  </div>
                </div>
              )}
              <NodeCard node={node} />
            </React.Fragment>
          ))}
        </div>
      )}

      {lineage && (
        <div className="mt-6 text-center text-xs text-muted">
          {lineage.nodes.length} nodes · {lineage.edges.length} edges · Click any card to expand
        </div>
      )}
    </div>
  );
}
