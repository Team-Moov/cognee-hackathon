import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Sidebar from "./components/Sidebar";
import Dashboard from "./pages/Dashboard";
import PreflightGuard from "./pages/PreflightGuard";
import LineageExplorer from "./pages/LineageExplorer";
import QueryPage from "./pages/QueryPage";
import FilesPage from "./pages/FilesPage";
import AgentsPage from "./pages/AgentsPage";

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen overflow-hidden bg-zinc-950">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/preflight" element={<PreflightGuard />} />
            <Route path="/lineage/:runId" element={<LineageExplorer />} />
            <Route path="/query" element={<QueryPage />} />
            <Route path="/files" element={<FilesPage />} />
            <Route path="/agents" element={<AgentsPage />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
