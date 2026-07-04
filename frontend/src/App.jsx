import React from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  Outlet,
} from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import PreflightGuard from "./pages/PreflightGuard";
import LineageExplorer from "./pages/LineageExplorer";
import QueryPage from "./pages/QueryPage";
import FilesPage from "./pages/FilesPage";
import AgentsPage from "./pages/AgentsPage";

/** App shell: sidebar + scrollable content area. */
function AppLayout() {
  return (
    <div className="flex h-screen overflow-hidden bg-paper">
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
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
