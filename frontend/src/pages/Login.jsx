import React, { useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import Brand from "../components/Brand";
import { useAuth } from "../auth/AuthContext";

export default function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const location = useLocation();
  const from = location.state?.from || "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  function submit(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      login({ email, password });
      nav(from, { replace: true });
    } catch (err) {
      setError(err.message);
      setBusy(false);
    }
  }

  const input =
    "w-full rounded-xl border border-line bg-paper px-4 py-2.5 text-sm text-cocoa placeholder-muted/70 focus:border-coffee focus:outline-none focus:ring-2 focus:ring-coffee/20";

  return (
    <div className="flex min-h-screen items-center justify-center bg-paper px-6 py-12">
      <div className="rise w-full max-w-md">
        <div className="mb-8 flex justify-center">
          <Link to="/">
            <Brand size="lg" />
          </Link>
        </div>

        <div className="rounded-3xl border border-line bg-card p-8 shadow-lift">
          <h1 className="font-display text-2xl font-semibold text-espresso">Welcome back</h1>
          <p className="mt-1 text-sm text-muted">Sign in to your research memory.</p>

          <form onSubmit={submit} className="mt-6 space-y-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-cocoa">Email</label>
              <input
                type="email"
                autoFocus
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@lab.edu"
                className={input}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-cocoa">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                className={input}
              />
            </div>

            {error && (
              <div className="rounded-xl border border-terracotta/30 bg-terracotta/10 px-3 py-2 text-sm text-terracotta">
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={busy}
              className="w-full rounded-xl bg-coffee py-2.5 text-sm font-semibold text-card shadow-soft transition-colors hover:bg-coffee-deep disabled:opacity-50"
            >
              {busy ? "Signing in…" : "Sign in"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-muted">
            New here?{" "}
            <Link to="/signup" className="font-semibold text-coffee hover:text-coffee-deep">
              Create an account
            </Link>
          </p>
        </div>

        <p className="mt-6 text-center text-xs text-muted">
          <Link to="/" className="hover:text-cocoa">
            ← Back to home
          </Link>
        </p>
      </div>
    </div>
  );
}
