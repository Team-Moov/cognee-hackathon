import React, { useState } from "react";
import { queryMemory } from "../services/api";
import { useNavigate } from "react-router-dom";

const EXAMPLES = [
  "Which runs failed or were aborted?",
  "What is the best val_acc achieved?",
  "What learning rate works best for BERT?",
  "Show me the CIFAR-10 ResNet sweep results",
  "How much GPU compute did we waste?",
  "What are the negative results in memory?",
];

function renderMarkdown(text) {
  // Very lightweight markdown: bold, code, newlines, tables
  const lines = text.split("\n");
  return lines.map((line, i) => {
    if (line.startsWith("|")) {
      // Table row
      const cells = line.split("|").filter(c => c.trim());
      const isSep = cells.every(c => /^[-:]+$/.test(c.trim()));
      if (isSep) return null;
      return (
        <tr key={i} className="border-b border-zinc-800">
          {cells.map((c, j) => (
            <td key={j} className="px-3 py-1.5 text-xs text-zinc-300 font-mono" dangerouslySetInnerHTML={{ __html: mdInline(c.trim()) }} />
          ))}
        </tr>
      );
    }
    if (line === "") return <br key={i} />;
    return <p key={i} className="text-sm text-zinc-300 leading-relaxed" dangerouslySetInnerHTML={{ __html: mdInline(line) }} />;
  }).filter(Boolean);
}

function mdInline(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-zinc-100">$1</strong>')
    .replace(/`(.+?)`/g, '<code class="font-mono text-indigo-400 bg-indigo-500/10 px-1 rounded">$1</code>')
    .replace(/✓/g, '<span class="text-emerald-400">✓</span>')
    .replace(/✗/g, '<span class="text-red-400">✗</span>')
    .replace(/→/g, '<span class="text-zinc-500">→</span>');
}

export default function QueryPage() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const nav = useNavigate();

  async function handleQuery(q) {
    const question = q || "";
    if (!question.trim()) return;
    setLoading(true);
    setResult(null);
    setError(null);
    try {
      const res = await queryMemory(question);
      setResult({ question, ...res });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  const hasTable = result?.answer?.includes("|");

  return (
    <div className="p-6 max-w-2xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-zinc-100">🔍 Ask Memory</h1>
        <p className="text-zinc-500 text-sm mt-1">Natural language queries across all experiment history — including failures.</p>
      </div>

      {/* Input */}
      <div className="flex gap-2">
        <input
          type="text"
          value={question}
          onChange={e => setQuestion(e.target.value)}
          onKeyDown={e => e.key === "Enter" && handleQuery(question)}
          placeholder="Ask about your experiments…"
          className="flex-1 bg-zinc-900 border border-zinc-700 rounded-xl px-4 py-3 text-sm text-zinc-100 placeholder-zinc-500 focus:outline-none focus:border-indigo-500"
        />
        <button
          onClick={() => handleQuery(question)}
          disabled={loading || !question.trim()}
          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white px-5 py-3 rounded-xl font-semibold text-sm transition-colors"
        >
          {loading ? "…" : "Ask"}
        </button>
      </div>

      {/* Example chips */}
      <div className="mt-3 flex flex-wrap gap-2">
        {EXAMPLES.map(ex => (
          <button
            key={ex}
            onClick={() => { setQuestion(ex); handleQuery(ex); }}
            className="text-xs text-zinc-400 hover:text-zinc-100 bg-zinc-800 hover:bg-zinc-700 border border-zinc-700 px-3 py-1.5 rounded-full transition-colors"
          >
            {ex}
          </button>
        ))}
      </div>

      {error && (
        <div className="mt-4 text-red-400 text-sm bg-red-500/10 border border-red-500/20 rounded-lg p-3">{error}</div>
      )}

      {/* Answer */}
      {result && (
        <div className="mt-5 fade-in">
          <div className="text-xs text-zinc-500 mb-2">Query: <span className="text-zinc-300 italic">"{result.question}"</span></div>

          <div className="bg-zinc-900 border border-zinc-800 rounded-xl p-5">
            <div className="text-xs font-bold text-indigo-400 uppercase tracking-wide mb-3">Memory says:</div>
            {hasTable ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left">{renderMarkdown(result.answer)}</table>
              </div>
            ) : (
              <div className="space-y-2">{renderMarkdown(result.answer)}</div>
            )}
          </div>

          {result.citations?.length > 0 && (
            <div className="mt-3">
              <div className="text-xs text-zinc-500 mb-2">Sources</div>
              <div className="flex flex-wrap gap-2">
                {result.citations.map(c => (
                  <button
                    key={c}
                    onClick={() => nav(`/lineage/${c}`)}
                    className="text-xs font-mono text-indigo-400 bg-indigo-500/10 border border-indigo-500/20 hover:border-indigo-400/50 px-2.5 py-1 rounded-lg transition-colors"
                  >
                    {c}
                  </button>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
