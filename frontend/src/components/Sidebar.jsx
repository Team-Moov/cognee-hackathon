import React from "react";
import { NavLink } from "react-router-dom";
import ProjectBar from "./ProjectBar";
import Brand from "./Brand";
import Icon from "./Icon";

const NAV = [
  { to: "/dashboard", label: "Experiments", icon: "beaker" },
  { to: "/insights", label: "Insights", icon: "chart" },
  { to: "/graph", label: "Memory Graph", icon: "graph" },
  { to: "/preflight", label: "Pre-Flight Guard", icon: "shield" },
  { to: "/query", label: "Ask Memory", icon: "search" },
  { to: "/files", label: "File Finder", icon: "folder" },
  { to: "/agents", label: "Agents", icon: "sparkles" },
];

export default function Sidebar({
  collapsed = false,
  mobileOpen = false,
  onToggle,
  onClose,
}) {
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

      <nav className="flex-1 space-y-1 overflow-y-auto px-2 py-3">
        {NAV.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            onClick={onClose}
            title={label}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-all duration-200 ${collapsed ? "justify-center" : ""} ${
                isActive ? "bg-slate-800/50 text-white" : "text-slate-300 hover:bg-slate-800/60"
              }`
            }
          >
            <Icon name={icon} size={20} className="flex-shrink-0" />
            {!collapsed && (
              <span className="truncate font-semibold text-[0.82rem]">{label}</span>
            )}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
