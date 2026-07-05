import React, { useEffect, useState } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  Outlet,
} from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import Sidebar from "./components/Sidebar";
import Icon from "./components/Icon";
import Dashboard from "./pages/Dashboard";
import PreflightGuard from "./pages/PreflightGuard";
import LineageExplorer from "./pages/LineageExplorer";
import QueryPage from "./pages/QueryPage";
import FilesPage from "./pages/FilesPage";
import AgentsPage from "./pages/AgentsPage";
import InsightsPage from "./pages/InsightsPage";
import MemoryGraph from "./pages/MemoryGraph";

/** App shell: sidebar + scrollable content area. */
function AppLayout() {
  const [isCollapsed, setIsCollapsed] = useState(false);
  const [isMobileOpen, setIsMobileOpen] = useState(false);
  const [isDesktop, setIsDesktop] = useState(() => window.innerWidth >= 1024);
  const [theme, setTheme] = useState(() => {
    if (typeof window === "undefined") return "light";
    const stored = window.localStorage.getItem("groundhog-theme");
    if (stored === "light" || stored === "dark") return stored;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  });

  useEffect(() => {
    function onResize() {
      const desktop = window.innerWidth >= 1024;
      setIsDesktop(desktop);
      if (desktop) {
        setIsMobileOpen(false);
      }
    }

    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.style.colorScheme = theme;
    window.localStorage.setItem("groundhog-theme", theme);
  }, [theme]);

  function toggleSidebar() {
    if (isDesktop) {
      setIsCollapsed((value) => !value);
    } else {
      setIsMobileOpen((value) => !value);
    }
  }

  function closeMobileSidebar() {
    setIsMobileOpen(false);
  }

  function toggleTheme() {
    setTheme((value) => (value === "dark" ? "light" : "dark"));
  }

  return (
    <div className="flex h-screen overflow-hidden bg-paper text-cocoa">
      <Sidebar
        collapsed={isCollapsed}
        mobileOpen={isMobileOpen}
        onToggle={toggleSidebar}
        onClose={closeMobileSidebar}
        theme={theme}
        onToggleTheme={toggleTheme}
      />

      {isMobileOpen && (
        <button
          type="button"
          aria-label="Close navigation"
          className="fixed inset-0 z-20 bg-stone-900/30 lg:hidden"
          onClick={closeMobileSidebar}
        />
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="border-b border-line/70 bg-paper/90 px-4 py-3 backdrop-blur sm:px-6 lg:hidden">
          <button
            type="button"
            onClick={toggleSidebar}
            className="inline-flex items-center gap-2 rounded-full border border-line bg-card px-3 py-2 text-sm font-medium text-cocoa shadow-sm"
          >
            <Icon name="menu" size={16} />
            <span>Menu</span>
          </button>
        </header>

        <main className="flex-1 overflow-y-auto">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />

          <Route element={<AppLayout />}>
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/insights" element={<InsightsPage />} />
            <Route path="/graph" element={<MemoryGraph />} />
            <Route path="/preflight" element={<PreflightGuard />} />
            <Route path="/lineage/:runId" element={<LineageExplorer />} />
            <Route path="/query" element={<QueryPage />} />
            <Route path="/files" element={<FilesPage />} />
            <Route path="/agents" element={<AgentsPage />} />
          </Route>

          <Route path="*" element={<Navigate to="/dashboard" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
