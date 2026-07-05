import React, { useState } from "react";
import { queryMemory } from "../services/api";
import { useNavigate } from "react-router-dom";
import PageHeader from "../components/PageHeader";

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
  return lines
    .map((line, i) => {
      if (line.startsWith("|")) {
        // Table row
        const cells = line.split("|").filter((c) => c.trim());
        const isSep = cells.every((c) => /^[-:]+$/.test(c.trim()));
        if (isSep) return null;
        return (
          <tr key={i} className="border-b border-line">
            {cells.map((c, j) => (
              <td
                key={j}
                className="px-3 py-1.5 text-xs text-cocoa font-mono"
                dangerouslySetInnerHTML={{ __html: mdInline(c.trim()) }}
              />
            ))}
          </tr>
        );
      }
      if (line === "") return <br key={i} />;
      return (
        <p
          key={i}
          className="text-sm text-cocoa leading-relaxed"
          dangerouslySetInnerHTML={{ __html: mdInline(line) }}
        />
      );
    })
    .filter(Boolean);
}

function mdInline(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-espresso">$1</strong>')
    .replace(
      /`(.+?)`/g,
      '<code class="font-mono text-coffee-deep bg-sand px-1 rounded">$1</code>',
    )
    .replace(/✓/g, '<span class="text-olive">✓</span>')
    .replace(/✗/g, '<span class="text-terracotta">✗</span>')
    .replace(/→/g, '<span class="text-muted">→</span>');
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
    <div className="mx-auto w-full max-w-5xl p-6 sm:p-8 lg:px-10">
      <PageHeader
        title="Ask Memory"
        subtitle="Natural language queries across all experiment history — including failures."
      />

      {/* Input */}
      <div className="flex gap-2">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleQuery(question)}
          placeholder="Ask about your experiments…"
          className="flex-1 rounded-2xl border border-line bg-card px-4 py-3 text-sm text-cocoa placeholder-muted/70 focus:border-coffee focus:outline-none focus:ring-2 focus:ring-coffee/20"
        />
        <button
          onClick={() => handleQuery(question)}
          disabled={loading || !question.trim()}
          className="rounded-2xl bg-coffee px-5 py-3 text-sm font-semibold text-card shadow-soft transition-colors hover:bg-coffee-deep disabled:opacity-40"
        >
          {loading ? "…" : "Ask"}
        </button>
      </div>

      {/* Example chips */}
      <div className="mt-3 flex flex-wrap gap-2">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            onClick={() => {
              setQuestion(ex);
              handleQuery(ex);
            }}
            className="rounded-full border border-line bg-card px-3 py-1.5 text-xs text-cocoa transition-colors hover:bg-sand"
          >
            {ex}
          </button>
        ))}
      </div>

      {error && (
        <div className="mt-4 rounded-xl border border-terracotta/25 bg-terracotta/10 p-3 text-sm text-terracotta">
          {error}
        </div>
      )}

      {/* Answer */}
      {result && (
        <div className="fade-in mt-5">
          <div className="mb-2 text-xs text-muted">
            Query:{" "}
            <span className="italic text-cocoa">"{result.question}"</span>
          </div>

          <div className="rounded-2xl border border-line bg-card p-5 shadow-soft">
            <div className="mb-3 text-xs font-bold uppercase tracking-wide text-coffee">
              Memory says:
            </div>
            {hasTable ? (
              <div className="overflow-x-auto">
                <table className="w-full text-left">
                  {renderMarkdown(result.answer)}
                </table>
              </div>
            ) : (
              <div className="space-y-2">{renderMarkdown(result.answer)}</div>
            )}
          </div>

          {result.citations?.length > 0 && (
            <div className="mt-3">
              <div className="mb-2 text-xs text-muted">Sources</div>
              <div className="flex flex-wrap gap-2">
                {result.citations.map((c) => (
                  <button
                    key={c}
                    onClick={() => nav(`/lineage/${c}`)}
                    className="rounded-lg border border-coffee/25 bg-coffee/8 px-2.5 py-1 font-mono text-xs text-coffee-deep transition-colors hover:border-coffee/50"
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
