import React from "react";
import { Link } from "react-router-dom";
import Brand from "../components/Brand";
import Icon from "../components/Icon";
import { useAuth } from "../auth/AuthContext";

const FEATURES = [
  {
    icon: "shield",
    title: "Pre-flight Guard",
    body: "Check a config against everything you've already run — never burn GPU-hours on a repeat experiment again.",
  },
  {
    icon: "search",
    title: "Ask your history",
    body: "Natural-language questions across every run, including the failures. Answers come with citations you can trace.",
  },
  {
    icon: "lineage",
    title: "Full lineage",
    body: "Walk the chain from hypothesis to decision to config to result for any run — the reasoning, not just the numbers.",
  },
  {
    icon: "folder",
    title: "Find any artifact",
    body: "Locate checkpoints, plots and reports by description, and surface orphaned files eating your disk.",
  },
];

export default function Home() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-paper text-cocoa">
      {/* Nav */}
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <Brand />
        <nav className="flex items-center gap-2 sm:gap-3">
          {user ? (
            <Link
              to="/dashboard"
              className="rounded-full bg-coffee px-5 py-2 text-sm font-semibold text-card shadow-soft transition-colors hover:bg-coffee-deep"
            >
              Open dashboard →
            </Link>
          ) : (
            <>
              <Link
                to="/login"
                className="rounded-full px-4 py-2 text-sm font-medium text-cocoa transition-colors hover:bg-sand"
              >
                Log in
              </Link>
              <Link
                to="/signup"
                className="rounded-full bg-coffee px-5 py-2 text-sm font-semibold text-card shadow-soft transition-colors hover:bg-coffee-deep"
              >
                Get started
              </Link>
            </>
          )}
        </nav>
      </header>

      {/* Hero */}
      <section className="mx-auto max-w-6xl px-6 pb-8 pt-10 sm:pt-20">
        <div className="rise mx-auto max-w-3xl text-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-line bg-card px-4 py-1.5 text-xs font-medium text-muted shadow-soft">
            <span className="h-1.5 w-1.5 rounded-full bg-olive" />
            Memory for machine-learning research
          </span>
          <h1 className="mt-6 font-display text-5xl font-semibold leading-[1.05] tracking-tight text-espresso sm:text-6xl">
            Every experiment you've
            <br />
            ever run, <span className="italic text-coffee">remembered.</span>
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-muted">
            Groundhog keeps the reasoning behind your research — hypotheses, decisions,
            configs and results — so you stop re-running what you already know.
          </p>
          <div className="mt-9 flex flex-wrap items-center justify-center gap-3">
            <Link
              to={user ? "/dashboard" : "/signup"}
              className="rounded-full bg-coffee px-7 py-3 text-sm font-semibold text-card shadow-lift transition-colors hover:bg-coffee-deep"
            >
              {user ? "Go to dashboard" : "Create your workspace"}
            </Link>
            <Link
              to={user ? "/preflight" : "/login"}
              className="rounded-full border border-line bg-card px-7 py-3 text-sm font-semibold text-cocoa shadow-soft transition-colors hover:bg-hover"
            >
              {user ? "Try pre-flight guard" : "I already have an account"}
            </Link>
          </div>
        </div>

        {/* Feature grid */}
        <div className="mt-20 grid gap-5 sm:grid-cols-2">
          {FEATURES.map((f) => (
            <div
              key={f.title}
              className="rounded-2xl border border-line bg-card p-6 shadow-soft transition-shadow hover:shadow-lift"
            >
              <div className="grid h-11 w-11 place-items-center rounded-xl bg-sand text-coffee">
                <Icon name={f.icon} size={22} />
              </div>
              <h3 className="mt-4 font-display text-xl font-semibold text-espresso">{f.title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-muted">{f.body}</p>
            </div>
          ))}
        </div>

        {/* Closing band */}
        <div className="mt-16 overflow-hidden rounded-3xl border border-line bg-coffee px-8 py-12 text-center shadow-lift">
          <h2 className="font-display text-3xl font-semibold text-card sm:text-4xl">
            Stop asking "did we try this already?"
          </h2>
          <p className="mx-auto mt-3 max-w-lg text-sm leading-relaxed text-card/80">
            Set up a workspace in seconds and give your team a shared memory of every run.
          </p>
          <Link
            to={user ? "/dashboard" : "/signup"}
            className="mt-7 inline-block rounded-full bg-card px-7 py-3 text-sm font-semibold text-coffee-deep shadow-soft transition-transform hover:-translate-y-0.5"
          >
            {user ? "Open dashboard →" : "Get started free →"}
          </Link>
        </div>
      </section>

      <footer className="mx-auto max-w-6xl px-6 py-10 text-center text-xs text-muted">
        Groundhog · Research memory for ML teams
      </footer>
    </div>
  );
}
