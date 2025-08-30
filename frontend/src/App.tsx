import { useState } from "react";
import { AdminView } from "./components/AdminView";
import { UserView } from "./components/UserView";
import { Input, Pill } from "./components/ui";

export default function App() {
  const [userId, setUserId] = useState("demo-user@example.com");
  const [view, setView] = useState<"admin" | "user">("user");

  return (
    <div className="min-h-screen bg-slate-50 font-sans">
      {/* Header */}
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/80 backdrop-blur">
        <div className="mx-auto flex max-w-7xl items-center justify-between p-4">
          <div className="flex items-center gap-6">
            <h1 className="text-xl font-bold tracking-tight text-slate-900">Geo-Governance Compliance</h1>
            <nav className="flex items-center gap-2 rounded-full bg-slate-100 p-1">
              <button
                onClick={() => setView("user")}
                className={`rounded-full px-3 py-1 text-sm font-medium transition-colors ${
                  view === "user" ? "bg-white text-indigo-600 shadow" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Compliance Check
              </button>
              <button
                onClick={() => setView("admin")}
                className={`rounded-full px-3 py-1 text-sm font-medium transition-colors ${
                  view === "admin" ? "bg-white text-indigo-600 shadow" : "text-slate-600 hover:text-slate-900"
                }`}
              >
                Admin Ingestion
              </button>
            </nav>
          </div>
          <div className="flex items-center gap-2">
            <Input
              placeholder="Your User ID (email or handle)"
              value={userId}
              onChange={(e) => setUserId(e.target.value)}
              className="w-72"
              aria-label="User ID"
            />
            <Pill tone="primary">User: {userId || "..."}</Pill>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="mx-auto max-w-7xl p-4">
        {view === "admin" ? <AdminView /> : <UserView userId={userId} />}
      </main>

      <footer className="mx-auto max-w-7xl p-6 text-center text-xs text-slate-500">
        API backend expected at <code>{import.meta.env.VITE_API_BASE || "http://localhost:8000"}</code>
      </footer>
    </div>
  );
}