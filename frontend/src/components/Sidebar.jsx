import React from "react";
import { NavLink, useLocation } from "react-router-dom";

const NAV = [
  { to: "/dashboard", label: "Experiments",    icon: "⚗️", desc: "All runs" },
  { to: "/preflight", label: "Pre-flight Guard", icon: "🛡️", desc: "Check before running" },
  { to: "/query",     label: "Ask Memory",     icon: "🔍", desc: "NL query" },
  { to: "/files",     label: "File Finder",    icon: "📁", desc: "Artifacts & orphans" },
  { to: "/agents",    label: "Agents",         icon: "🤖", desc: "AI suggestions" },
];

export default function Sidebar() {
  return (
    <aside className="w-56 flex-shrink-0 bg-zinc-900 border-r border-zinc-800 flex flex-col">
      <div className="px-4 py-5 border-b border-zinc-800">
        <div className="flex items-center gap-2">
          <span className="text-2xl">🦫</span>
          <div>
            <div className="font-bold text-zinc-100 text-sm leading-tight">Groundhog</div>
            <div className="text-zinc-500 text-xs">ML Memory</div>
          </div>
        </div>
      </div>

      <nav className="flex-1 py-3 px-2 space-y-1">
        {NAV.map(({ to, label, icon, desc }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
                isActive
                  ? "bg-indigo-600/20 text-indigo-300 border border-indigo-500/30"
                  : "text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100"
              }`
            }
          >
            <span className="text-base w-5 text-center">{icon}</span>
            <div className="min-w-0">
              <div className="font-medium truncate">{label}</div>
              <div className="text-xs text-zinc-500 truncate">{desc}</div>
            </div>
          </NavLink>
        ))}
      </nav>

      <div className="px-4 py-3 border-t border-zinc-800">
        <div className="text-xs text-zinc-600 space-y-1">
          <div className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-500 inline-block"></span>
            Live — Firebase + Groq
          </div>
          <div className="text-zinc-700">Run backend: uvicorn app.main:app</div>
        </div>
      </div>
    </aside>
  );
}
