import React, { useEffect, useRef, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import ForceGraph2D from "react-force-graph-2d";
import { getGraph } from "../services/api";

const TYPE_COLOR = {
  experiment: "#7B5836", // coffee
  run: "#5E7A46",        // olive
  dataset: "#B27C24",    // ochre
  artifact: "#93795C",   // muted
};
const STATUS_COLOR = { completed: "#5E7A46", failed: "#B14A34", aborted: "#B27C24" };

export default function MemoryGraph() {
  const [data, setData] = useState({ nodes: [], links: [] });
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);
  const fgRef = useRef();
  const wrapRef = useRef();
  const [dims, setDims] = useState({ w: 800, h: 560 });
  const nav = useNavigate();

  useEffect(() => {
    getGraph()
      .then((g) => {
        const nodes = (g.nodes || []).map((n) => ({ ...n }));
        const links = (g.edges || []).map((e) => ({ source: e.source, target: e.target, type: e.type }));
        setData({ nodes, links });
      })
      .catch(() => setData({ nodes: [], links: [] }))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    function resize() {
      if (wrapRef.current) setDims({ w: wrapRef.current.clientWidth, h: Math.max(480, window.innerHeight - 220) });
    }
    resize();
    window.addEventListener("resize", resize);
    return () => window.removeEventListener("resize", resize);
  }, []);

  const draw = useCallback((node, ctx, scale) => {
    const label = node.label || node.id;
    const fontSize = 12 / scale;
    const color = node.type === "run" ? (STATUS_COLOR[node.status] || TYPE_COLOR.run) : (TYPE_COLOR[node.type] || "#999");
    const r = node.type === "experiment" ? 9 : node.type === "run" ? 6 : 5;
    ctx.beginPath();
    ctx.arc(node.x, node.y, r, 0, 2 * Math.PI);
    ctx.fillStyle = color;
    ctx.fill();
    if (scale > 1.1 || node.type !== "run") {
      ctx.font = `${fontSize}px Manrope, sans-serif`;
      ctx.fillStyle = "#4E3A2A";
      ctx.textAlign = "center";
      ctx.fillText(String(label).slice(0, 22), node.x, node.y + r + fontSize);
    }
  }, []);

  return (
    <div className="mx-auto max-w-6xl p-6 sm:p-8">
      <div className="mb-4">
        <h1 className="font-display text-3xl font-semibold text-espresso">Memory Graph</h1>
        <p className="mt-1 text-sm text-muted">
          The project's knowledge graph — experiments, runs, datasets, and how they connect. Click a run to inspect; double-click to open its lineage.
        </p>
      </div>

      <div className="mb-3 flex flex-wrap gap-3 text-xs text-muted">
        {Object.entries(TYPE_COLOR).map(([t, c]) => (
          <span key={t} className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: c }} /> {t}
          </span>
        ))}
        <span className="flex items-center gap-1.5"><span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: "#B14A34" }} /> failed run</span>
      </div>

      <div ref={wrapRef} className="relative overflow-hidden rounded-2xl border border-line bg-card shadow-soft">
        {loading ? (
          <div className="py-24 text-center text-sm text-muted">Loading graph…</div>
        ) : data.nodes.length === 0 ? (
          <div className="py-24 text-center text-sm text-muted">No memory in this project yet — record some runs.</div>
        ) : (
          <ForceGraph2D
            ref={fgRef}
            width={dims.w}
            height={dims.h}
            graphData={data}
            backgroundColor="#FDF8EE"
            nodeCanvasObject={draw}
            nodePointerAreaPaint={(node, color, ctx) => {
              ctx.fillStyle = color;
              ctx.beginPath();
              ctx.arc(node.x, node.y, 8, 0, 2 * Math.PI);
              ctx.fill();
            }}
            linkColor={() => "#DECBAA"}
            linkDirectionalArrowLength={3}
            linkDirectionalArrowRelPos={1}
            linkWidth={1}
            onNodeClick={(n) => setSelected(n)}
            onNodeRightClick={(n) => n.type === "run" && nav(`/lineage/${n.id}`)}
            cooldownTicks={80}
          />
        )}

        {selected && (
          <div className="absolute right-3 top-3 w-64 rounded-xl border border-line bg-card p-3 text-xs shadow-lift">
            <div className="mb-1 flex items-center justify-between">
              <span className="font-semibold uppercase tracking-wide text-coffee-deep">{selected.type}</span>
              <button onClick={() => setSelected(null)} className="text-muted hover:text-cocoa">✕</button>
            </div>
            <div className="mb-1 text-sm text-espresso">{selected.label}</div>
            {selected.status && <div className="text-muted">status: {selected.status}</div>}
            {selected.metric != null && <div className="text-muted">metric: {selected.metric}</div>}
            {selected.gpu_hours != null && <div className="text-muted">{selected.gpu_hours}h GPU</div>}
            {selected.config && <code className="mt-1 block break-all text-[10px] text-cocoa">{JSON.stringify(selected.config)}</code>}
            {selected.type === "run" && (
              <button onClick={() => nav(`/lineage/${selected.id}`)} className="mt-2 text-coffee hover:underline">Open lineage →</button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
