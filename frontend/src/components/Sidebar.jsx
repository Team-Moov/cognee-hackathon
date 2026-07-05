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

export default function Sidebar({ collapsed = false, mobileOpen = false, onToggle, onClose, theme = "light", onToggleTheme }) {
  const abbrev = (label) => label
    .split(" ")
    .map((word) => word[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();

  return (
    <aside
      className={`fixed inset-y-0 z-30 flex h-screen flex-col border-r shadow-[8px_0_30px_rgba(78,58,42,0.08)] transition-all duration-300 ease-out lg:static ${mobileOpen ? "left-0" : "-left-full"} ${collapsed ? "w-20 items-center" : "w-72"}`}
      style={{ backgroundColor: "var(--sidebar-bg)", borderColor: "var(--sidebar-border)" }}
    >
      <div className={`flex items-center border-b ${collapsed ? "justify-center px-2 py-3" : "justify-between px-4 py-3"}`} style={{ borderColor: "var(--sidebar-border)" }}>
        {collapsed ? (
          <button
            type="button"
            onClick={onToggle}
            className="inline-flex h-11 w-11 items-center justify-center rounded-2xl border border-line bg-card text-cocoa shadow-sm transition hover:bg-hover"
            title="Open navigation"
          >
            <Icon name="menu" size={18} />
          </button>
        ) : (
          <>
            <NavLink to="/dashboard" onClick={onClose} className="min-w-0">
              <Brand size="sm" tagline={false} />
            </NavLink>

            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={onToggleTheme}
                className="flex h-9 w-9 items-center justify-center rounded-full border bg-card text-cocoa shadow-sm transition-colors hover:bg-hover"
                title={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
                style={{ borderColor: "var(--sidebar-border)" }}
              >
                {theme === "dark" ? "☀︎" : "☾"}
              </button>
              <button
                type="button"
                onClick={onToggle}
                className="flex h-9 w-9 items-center justify-center rounded-full border bg-card text-cocoa shadow-sm transition-colors hover:bg-hover"
                title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
                style={{ borderColor: "var(--sidebar-border)" }}
              >
                <Icon name={collapsed ? "arrowRight" : "arrowLeft"} size={16} />
              </button>
            </div>
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
              `flex items-center rounded-xl px-3 py-2.5 text-sm transition-all ${collapsed ? "justify-center" : ""} ${
                isActive
                  ? "shadow-sm"
                  : "hover:bg-[var(--sidebar-hover)]"
              }`
            }
            style={({ isActive }) => ({
              backgroundColor: isActive ? "var(--sidebar-active-bg)" : undefined,
              color: isActive ? "var(--sidebar-active-text)" : "var(--sidebar-text)",
            })}
          >
            <div className="flex w-full items-center justify-center gap-3">
              {collapsed ? (
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-2xl bg-[var(--sidebar-hover)] text-[0.75rem] font-semibold text-[var(--sidebar-text)]">
                  {abbrev(label)}
                </span>
              ) : null}

              <div className={`min-w-0 ${collapsed ? "hidden" : "flex-1"}`}>
                <div className="truncate font-semibold uppercase tracking-[0.16em] text-[0.78rem]">{label}</div>
              </div>
            </div>
          </NavLink>
        ))}
      </nav>
      )}
    </aside>
  );
}
