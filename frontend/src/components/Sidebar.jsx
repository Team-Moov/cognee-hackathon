import React from "react";
import { NavLink, useNavigate } from "react-router-dom";
import ProjectBar from "./ProjectBar";
import Brand from "./Brand";
import Icon from "./Icon";
import { useAuth } from "../auth/AuthContext";

const NAV = [
  { to: "/dashboard", label: "Experiments",     icon: "beaker",   desc: "All runs" },
  { to: "/preflight", label: "Pre-flight Guard", icon: "shield",   desc: "Check before running" },
  { to: "/query",     label: "Ask Memory",       icon: "search",   desc: "Natural-language query" },
  { to: "/files",     label: "File Finder",       icon: "folder",   desc: "Artifacts & orphans" },
  { to: "/agents",    label: "Agents",            icon: "sparkles", desc: "AI suggestions" },
];

function initials(name = "") {
  return name
    .split(" ")
    .map((p) => p[0])
    .filter(Boolean)
    .slice(0, 2)
    .join("")
    .toUpperCase() || "?";
}

export default function Sidebar() {
  const { user, logout } = useAuth();
  const nav = useNavigate();

  function handleLogout() {
    logout();
    nav("/", { replace: true });
  }

  return (
    <aside className="flex w-64 flex-shrink-0 flex-col border-r border-line bg-card">
      <div className="border-b border-line px-5 py-5">
        <NavLink to="/">
          <Brand />
        </NavLink>
      </div>

      <ProjectBar />

      <nav className="flex-1 space-y-1 px-3 py-4">
        {NAV.map(({ to, label, icon, desc }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition-colors ${
                isActive
                  ? "bg-coffee text-card shadow-soft"
                  : "text-cocoa hover:bg-sand"
              }`
            }
          >
            {({ isActive }) => (
              <>
                <Icon name={icon} size={18} className="flex-shrink-0" />
                <div className="min-w-0">
                  <div className="truncate font-semibold">{label}</div>
                  <div className={`truncate text-xs ${isActive ? "text-card/70" : "text-muted"}`}>
                    {desc}
                  </div>
                </div>
              </>
            )}
          </NavLink>
        ))}
      </nav>

      {/* User + logout */}
      <div className="border-t border-line px-4 py-3">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 flex-shrink-0 place-items-center rounded-full bg-sand text-xs font-semibold text-coffee-deep">
            {initials(user?.name)}
          </div>
          <div className="min-w-0 flex-1">
            <div className="truncate text-sm font-semibold text-espresso">{user?.name || "Researcher"}</div>
            <div className="truncate text-xs text-muted">{user?.email}</div>
          </div>
          <button
            onClick={handleLogout}
            title="Sign out"
            className="flex-shrink-0 rounded-lg px-2 py-1 text-xs font-medium text-muted transition-colors hover:bg-sand hover:text-terracotta"
          >
            Sign out
          </button>
        </div>
      </div>
    </aside>
  );
}
