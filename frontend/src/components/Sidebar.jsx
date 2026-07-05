import React from "react";
import { NavLink } from "react-router-dom";
import ProjectBar from "./ProjectBar";
import Brand from "./Brand";
import Icon from "./Icon";

const NAV = [
  { to: "/dashboard", label: "Experiments" },
  { to: "/insights", label: "Insights" },
  { to: "/graph", label: "Memory Graph" },
  { to: "/preflight", label: "Pre-Flight Guard" },
  { to: "/query", label: "Ask Memory" },
  { to: "/files", label: "File Finder" },
  { to: "/agents", label: "Agents" },
];

export default function Sidebar({
  collapsed = false,
  mobileOpen = false,
  onToggle,
  onClose,
}) {
  const abbrev = (label) =>
    label
      .split(" ")
      .map((word) => word[0])
      .join("")
      .slice(0, 2)
      .toUpperCase();

  return (
    <aside
      className={`fixed inset-y-0 z-30 flex h-screen flex-col border-r border-slate-800/70 bg-slate-950 transition-all duration-300 ease-out lg:static ${mobileOpen ? "left-0" : "-left-full"} ${collapsed ? "w-20 items-center" : "w-72"}`}
    >
      <div className={`flex items-center border-b border-slate-800/70 ${collapsed ? "justify-center px-2 py-3" : "justify-between px-4 py-3"}`}>
        {collapsed ? (
          <button
            type="button"
            onClick={onToggle}
            className="inline-flex h-11 w-11 items-center justify-center text-espresso transition hover:text-coffee"
            title="Open navigation"
          >
            <Icon name="menu" size={18} />
          </button>
        ) : (
          <>
            <NavLink to="/dashboard" onClick={onClose} className="min-w-0">
              <Brand size="sm" tagline={false} />
            </NavLink>

          <button
            type="button"
            onClick={onToggle}
            className="flex h-9 w-9 items-center justify-center text-espresso transition hover:text-coffee"
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <Icon name={collapsed ? "arrowRight" : "arrowLeft"} size={16} />
          </button>
          </>
        )}
      </div>

      <ProjectBar collapsed={collapsed} />

      {!collapsed && (
        <nav className="flex-1 space-y-1 overflow-y-auto px-2 py-3">
          {NAV.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              onClick={onClose}
              title={label}
              className={({ isActive }) =>
                `flex items-center px-3 py-2 rounded-xl text-sm transition-all duration-200 ${collapsed ? "justify-center" : ""} ${
                  isActive ? "bg-slate-800/50 border-l-2 border-blue-400 text-white" : "hover:bg-slate-800/60 text-slate-300"
                }`
              }
            >
              <div className="flex w-full items-center justify-center gap-3">
                {collapsed ? (
                  <span className="inline-flex h-9 w-9 items-center justify-center rounded-2xl bg-[var(--sidebar-hover)] text-[0.75rem] font-semibold text-[var(--sidebar-text)]">
                    {abbrev(label)}
                  </span>
                ) : null}

                <div className={`min-w-0 ${collapsed ? "hidden" : "flex-1"}`}>
                  <div
                    className="truncate font-semibold uppercase tracking-[0.1em] text-[0.78rem]"
                    style={{ color: "var(--sidebar-text)", opacity: 0.92 }}
                  >
                    {label}
                  </div>
                </div>
              </div>
            </NavLink>
          ))}
        </nav>
      )}
    </aside>
  );
}
