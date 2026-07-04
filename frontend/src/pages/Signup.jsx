import React, { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import Brand from "../components/Brand";
import { useAuth } from "../auth/AuthContext";

export default function Signup() {
  const { signup } = useAuth();
  const nav = useNavigate();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  function submit(e) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      signup({ name, email, password });
      nav("/dashboard", { replace: true });
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
          <h1 className="font-display text-2xl font-semibold text-espresso">Create your workspace</h1>
          <p className="mt-1 text-sm text-muted">Start remembering every experiment you run.</p>

          <form onSubmit={submit} className="mt-6 space-y-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-cocoa">Name</label>
              <input
                autoFocus
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Ada Lovelace"
                className={input}
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-cocoa">Email</label>
              <input
                type="email"
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
                placeholder="At least 6 characters"
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
              {busy ? "Creating…" : "Create account"}
            </button>
          </form>

          <p className="mt-6 text-center text-sm text-muted">
            Already have an account?{" "}
            <Link to="/login" className="font-semibold text-coffee hover:text-coffee-deep">
              Sign in
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
