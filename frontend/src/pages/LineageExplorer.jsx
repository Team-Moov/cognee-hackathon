import React, { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getLineage } from "../services/api";

const NODE_STYLES = {
  hypothesis: { bg: "bg-violet-950/60 border-violet-500/40", label: "HYPOTHESIS", icon: "💡", text: "text-violet-300" },
  decision:   { bg: "bg-amber-950/60 border-amber-500/40",  label: "DECISION",   icon: "🧭", text: "text-amber-300"  },
  config:     { bg: "bg-blue-950/60 border-blue-500/40",    label: "CONFIG",     icon: "⚙️", text: "text-blue-300"   },
  result:     { bg: "bg-emerald-950/60 border-emerald-500/40", label: "RESULT",  icon: "📊", text: "text-emerald-300" },
  artifact:   { bg: "bg-zinc-800/60 border-zinc-600/40",    label: "ARTIFACT",  icon: "💾", text: "text-zinc-300"    },
};

const STATUS_COLORS = {
  supported: "text-emerald-400",
  refuted:   "text-red-400",
  open:      "text-zinc-400",
  completed: "text-emerald-400",
  aborted:   "text-amber-400",
  failed:    "text-red-400",
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
  const statusColor = STATUS_COLORS[statusKey] || "text-zinc-400";

  return (
    <div
      onClick={() => setExpanded(x => !x)}
      className={`border rounded-xl p-3 cursor-pointer transition-all ${style.bg} hover:opacity-90`}
    >
      <div className="flex items-start gap-2">
        <span>{style.icon}</span>
        <div className="min-w-0 flex-1">
          <div className={`text-xs font-bold uppercase tracking-wider mb-1 ${style.text}`}>{style.label}</div>
          <div className="text-sm text-zinc-100 leading-snug">{title}</div>

          {d.rationale && (
            <div className="mt-1 text-xs text-zinc-400 italic">{expanded ? d.rationale : `${d.rationale.slice(0,80)}${d.rationale.length > 80 ? "…" : ""}`}</div>
          )}

          {statusKey && (
            <div className={`mt-1 text-xs font-medium ${statusColor}`}>{statusKey}</div>
          )}

          {expanded && (
            <div className="mt-2 space-y-1">
              {Object.entries(d).filter(([k]) => !["statement","description","rationale","status","run_id","made_by","timestamp","file_path","artifact_type"].includes(k)).map(([k, v]) => (
                <div key={k} className="text-xs font-mono">
                  <span className="text-zinc-500">{k}: </span>
                  <span className="text-zinc-300">{JSON.stringify(v)}</span>
                </div>
              ))}
              {d.timestamp && <div className="text-xs text-zinc-600">{d.timestamp?.slice?.(0,16)}</div>}
              {d.made_by   && <div className="text-xs text-zinc-500">by {d.made_by}</div>}
              {d.gpu_hours && <div className="text-xs text-zinc-500">⚡ {d.gpu_hours}h GPU</div>}
            </div>
          )}
        </div>
        <span className="text-zinc-600 text-xs">{expanded ? "▲" : "▼"}</span>
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
    <div className="p-6 max-w-2xl mx-auto">
      <button
        onClick={() => nav("/dashboard")}
        className="text-sm text-zinc-500 hover:text-zinc-300 mb-4 flex items-center gap-1 transition-colors"
      >
        ← Back to Dashboard
      </button>

      <div className="mb-5">
        <h1 className="text-2xl font-bold text-zinc-100">Lineage Explorer</h1>
        <code className="text-sm text-indigo-400 mt-1 block">{runId}</code>
      </div>

      {loading && <div className="text-zinc-500 text-sm py-12 text-center">Loading lineage…</div>}
      {error   && <div className="text-red-400 text-sm py-12 text-center">Error: {error}</div>}

      {lineage && (
        <div className="space-y-1">
          {buildChain(lineage.nodes, lineage.edges).map(({ node, edge }, i) => (
            <React.Fragment key={node.id}>
              {edge && (
                <div className="flex items-center justify-center py-1">
                  <div className="text-xs text-zinc-600 bg-zinc-900 border border-zinc-800 px-3 py-1 rounded-full">
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
        <div className="mt-6 text-xs text-zinc-600 text-center">
          {lineage.nodes.length} nodes · {lineage.edges.length} edges · Click any card to expand
        </div>
      )}
    </div>
  );
}
