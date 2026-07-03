# Groundhog — ML Experiment Reproducibility & Memory

**Hackathon:** The Hangover Part AI: Where's My Context? (WeMakeDevs x Cognee)
**Dates:** June 29 – July 5, 2026
**Team size:** 4
**Internal project name:** Groundhog

---

## 1. The Problem

ML researchers, model tuners, and anyone doing fine-tuning or data analysis spend enormous time choosing models, parameters, hyperparameters, evaluation metrics, and datasets. Past a certain point, this history becomes unmanageable: there's no unified record of findings, no memory of which parameter choices were already tried, no trail of *why* decisions were made, and result/log files scatter and accumulate with no structure. Tools like Weights & Biases track *what* happened (metrics, configs) extremely well, but none of them answer "have we tried this before, and what happened" or preserve the *reasoning* behind a decision — only the data point.

Groundhog is a memory-graph layer that sits on top of (and integrates with) existing ML workflows and tools, and answers questions no current tool answers well:

1. "Have we tried this config, and what happened?" — before you waste compute rerunning it.
2. "What have we learned, and where should we look next?" — a self-improving research memory, not just a log.
3. "Where is the file I'm looking for?" — a researcher should never have to spelunk through `run_47_v2_final_FINAL/` to find a checkpoint or plot.
4. "Is my coding agent about to repeat a mistake?" — the same memory should be queryable live by agentic coding tools, not just by humans browsing a dashboard.

**Target audience:** ML researchers, ML labs, and individuals doing model tuning, fine-tuning, and data analysis. Designed to integrate with existing environments and popular third-party tools (W&B, Jupyter/Colab, Claude Code) rather than replace them.

---

## 2. Why This Fits the Hackathon

**Theme:** "Build AI that doesn't forget" — Groundhog cures the exact amnesia the hackathon is themed around, both for the human researcher and for any agentic coding tool working alongside them.

**Judging criteria alignment:**

- **Potential Impact** — addresses a universal, daily pain point for any ML practitioner; quantifiable wins (GPU-hours saved, duplicate runs prevented, untracked output files identified, cloud LLM tokens saved via local-first routing).
- **Creativity & Innovation** — "recall before you rerun" and a self-improving research memory is a fresh angle not covered by existing MLOps tooling. Treating Cognee's graph as a shared blackboard for multiple subagents, and exposing it live to Claude Code via MCP, are both genuinely fresh framings most teams won't attempt.
- **Technical Excellence** — full knowledge graph schema, five real data-source connectors, clean separation of ingest / memory / app layers, a small multi-agent system coordinating through shared memory, and a hybrid local/cloud LLM routing layer.
- **Best Use of Cognee** — uses all four lifecycle operations (`remember`, `recall`, `improve`/`memify`, `forget`), plus ontology grounding, `@observe` pipeline tracing, typed `DataPoint` schemas, the graph as inter-agent coordination substrate, and the graph exposed as a live MCP resource for external agents.
- **User Experience** — single consolidated web app rather than scattered files; pre-flight warnings happen at the moment they're useful; one-click file discovery removes the single most common daily friction point; the same memory is reachable from the terminal, the notebook, and any MCP-capable coding agent without context-switching.
- **Presentation Quality** — four concrete, demoable "wow moments" (see Section 11), including a live agent demo.

**Prize track strategy:** Build on open-source Cognee (SQLite + Kuzu locally) to target the **Best Use of Open Source** track. Use **Cognee Cloud's** built-in graph visualization panel purely as a demo/presentation layer for the video — not for the actual judged build.

---

## 3. Architecture Overview

Three tiers:

**Tier 1 — Data source connectors (ingest layer).** Five ways experiment data and reasoning enters or is queried from the system, so Groundhog meets researchers — and their agentic tools — where they already work.

1. **Jupyter/Colab magic command** — a `%groundhog watch` style hook using IPython's execution events to capture run events directly from notebooks: cell source (rationale in the researcher's own words), final metrics, elapsed time, git commit hash.
2. **W&B Bridge** — polls completed runs via the W&B API, pulling `run.config`, `run.summary`, tags, and notes. Highest-leverage connector given W&B's existing adoption — augments rather than competes with the tool researchers already use.
3. **File watcher** — uses the `watchdog` Python library to monitor YAML/JSON result and log files on disk. Zero-friction onramp for researchers who don't use W&B.
4. **agents.md append-only log** — a structured Markdown log capturing LLM agent actions or human researcher decisions with a strict schema: timestamp, action type (decided / abandoned / promoted / noted), parameters as JSON, rationale. Captures the *why*, not just the *what*, and unifies human and AI-agent decision trails into one lineage.
5. **Claude Code / MCP connector** — exposes Groundhog as an MCP server so any MCP-capable agent can query the graph live, mid-task, and write back to it. Unlike connectors 1–4, this one is bidirectional and real-time rather than passive ingestion. Detailed fully in Section 6.

**Tier 2 — Cognee memory layer (the core).** All five connectors read from and write into Cognee's knowledge graph + vector store. This tier is described fully in Section 4. It also doubles as the coordination substrate for a small set of subagents (Section 7).

**Tier 3 — Groundhog web app (consumption layer).** The single consolidated interface researchers use day to day. Described fully in Section 8.

---

## 4. Cognee Integration — Knowledge Graph Schema & API Mapping

### 4.1 Node types

- `Experiment` — a research effort/project, the top-level container.
- `Config` — a specific hyperparameter/parameter set.
- `Dataset` — first-class node capturing preprocessing decisions, split rationale, and discovered quality issues.
- `Result` — outcome of a run: metrics, cost (GPU-hours/wall-clock), artifacts.
- `Artifact` — a produced file (checkpoint, plot, eval report, log) with its on-disk path, linked to the `Result` that produced it. Powers one-click file discovery (Section 5).
- `Hypothesis` — the idea or question motivating a run or direction.
- `Decision` — a choice made along the way.
- `ResearchThread` — a directional thread of related runs pursuing one hypothesis or idea.
- `AgentAction` — an entry from the agents.md log, or a write from the MCP connector, capturing a human or AI agent's action with rationale.

### 4.2 Edge types

- `belongs_to` — links runs/configs to their parent Experiment or ResearchThread.
- `produced` — links a Config + run to its Result, and a Result to its Artifacts.
- `derived_from` — links a Config to the prior Config it was adapted from; also extended to link model checkpoints to the checkpoint a fine-tune started from (Section 10).
- `followed_by` — sequences Decisions and AgentActions chronologically within a thread.

### 4.3 Cognee API → feature mapping

- **`remember()`** — fires once per run completion. The full run document is enriched (rationale, diff from prior run) before ingestion. Also the write path used by the MCP connector's `groundhog_remember` tool.
- **`recall(type="GRAPH")`** — powers Pre-flight Guard, Lineage Explorer, and the MCP connector's `groundhog_check_config` tool.
- **`recall(type="CHUNKS")`** — powers config similarity search and the natural-language query bar.
- **`recall(type="COMPLETION")`** — powers the NL query bar's synthesized answers, the "Catch me up" narrative feature, and the MCP connector's `groundhog_query` tool.
- **`improve()` / `memify()`** — runs every 10 completed runs, producing retrospective summaries, direction-level findings, and parameter sensitivity rankings.
- **`forget()`** — prunes dead-end config families and abandoned threads from active retrieval without deleting historical data; also used proactively as automatic noise reduction (Section 4.5).

### 4.4 Ontology grounding

A lightweight ML domain ontology inside Cognee: optimizer IS-A {Adam, AdamW, SGD, ...}, architecture IS-A {CNN, Transformer, ResNet, ...}, with known relationships (e.g. "AdamW extends Adam with decoupled weight decay"). Moves recall from pure text-similarity to hierarchical reasoning — likely the single highest-leverage feature for the "Best Use of Cognee" criterion, since it's depth most teams won't attempt.

### 4.5 Beyond the four lifecycle calls

- **`@observe` pipeline tracing** — wraps Groundhog's own ingestion pipeline, giving observability into how Groundhog's own memory was built. A self-referential demo beat for a memory-themed hackathon.
- **Typed `DataPoint` schemas** — every node type defined as a proper `DataPoint` subclass rather than a loose dict, enforcing the schema at the Cognee layer.
- **`forget()` as active noise reduction** — beyond pruning dead-end threads, used automatically on low-signal data (aborted debug runs, partial runs below a signal threshold) so the graph stays high-value.
- **Private vs. shared memory with an explicit promote action** — exploratory memory and team memory as separate Cognee datasets, with an explicit "promote" action moving a Decision or Result into the shared graph. Lets junior researchers experiment freely without polluting collective memory.

---

## 5. Seamless Developer Experience — One-Click Everything

The biggest daily friction for researchers usually isn't choosing parameters — it's hunting for files afterward. Since every connector already writes into the graph, every artifact a run produces is indexed as an `Artifact` node tied to its `Result`, not just the metrics.

This turns file-hunting into a single query. A `groundhog find <natural language>` CLI command wraps `recall()` and returns a path directly — copyable or openable with one keystroke. In the web app, every Result card gets a "locate file" action that resolves the same way.

Because the graph knows what *should* exist, it can also flag orphans in both directions: files on disk with no matching graph node (junk worth cleaning up), and graph nodes whose referenced file no longer exists (a broken reproducibility chain). Orphan detection also produces a clean, quantifiable demo metric — "X GB of untracked output files identified."

---

## 6. Live Agent Connector — Claude Code via MCP

The MCP server is a thin layer over the same internal functions every other surface uses (Section 4.3), exposed as four tools:

- `groundhog_check_config(config)` — mirrors the Pre-flight Guard's `recall(type="GRAPH")` call.
- `groundhog_remember(run_summary)` — mirrors the standard run-ingestion path used by every connector.
- `groundhog_query(question)` — mirrors the dashboard's NL query bar, via `recall(type="COMPLETION")`.
- `groundhog_find(description)` — mirrors the Artifact lookup from Section 5.

None of this is new logic — it's the existing recall/remember functions with an MCP wrapper, on the order of a few hours of work once the underlying functions exist. What it buys is disproportionate to that effort: instead of only showing a human being protected from rerunning a wasted config, the demo can show Claude Code itself — mid agentic coding session, asked to sweep a few learning rates — querying Groundhog before writing the training script, discovering one of those learning rates already failed, and adjusting its plan live, with no human in the loop. For a hackathon literally themed around AI losing context, an agent visibly not repeating a past mistake in front of the judges is one of the most direct demos of the theme possible.

It complements rather than competes with the agents.md connector: agents.md stays the universal passive fallback (works for any tool, any human note, zero integration required), while the MCP server is the active counterpart specifically for agents that can make tool calls. Because MCP is a standard rather than a Claude-Code-specific protocol, the same server works unmodified for Cursor or any other MCP client later, with no extra engineering.

**Explicitly out of scope:** a custom IDE extension (its own UI, webviews, packaging, marketplace listing). That's a different engineering surface that doesn't reuse anything else being built this week — called out in the README as a deliberate scoping decision, not a miss.

---

## 7. Subagent Orchestration — Blackboard Architecture

Rather than one monolithic app, Groundhog's intelligence is split into narrow subagents that all read and write the *same* Cognee graph instead of messaging each other directly. The graph itself is the coordination layer — a blackboard architecture, where Cognee is the substrate multiple agents coordinate through, not just storage one app queries.

**Flow:** pipeline events (a run completes, a new file appears, a sweep is about to launch) are routed by a thin orchestrator to whichever subagent cares. No subagent talks to another directly — every read and write goes through the shared graph.

**The subagents:**

- **Config proposer** — reads parameter sensitivity rankings and unexplored sweep zones and suggests the next run, surfaced as a dismissible card, never auto-executed.
- **Triage agent** — watches incoming results and flags anomalies using graph context (e.g. a suspiciously good result gets flagged as a possible data leak rather than celebrated).
- **Literature agent** — periodically pulls papers matching the active research thread's ontology tags and proposes them as support for a Hypothesis node.
- **Dataset steward** — watches Dataset nodes for drift or quality issues, using patterns learned from similar datasets elsewhere in the graph.
- **Report agent** — assembles retrospectives and auto-generated model cards on demand by traversing lineage.

Because each agent's job is narrow and coordination happens through shared memory, this stays simple to build even with limited time — each subagent can be little more than a scheduled or event-triggered `recall()` + `remember()` pair, with the orchestrator just routing event types to the right function.

---

## 8. Web App — Core Features (must-build)

1. **Pre-flight Guard** — intercepts before a researcher reruns a config, surfacing the prior result before compute is spent. The single most demoable "wow moment."
2. **Lineage Explorer** — traces the full decision chain for any run, using Cognee Cloud's graph visualization for the demo.
3. **Recall Engine** — deliberately surfaces negative results and dead ends, not just successes.
4. **Natural language query bar** — free-form questions across experiment history, answered via `recall(type="COMPLETION")` with citations.

---

## 9. Web App — Stretch & Differentiating Features (ranked by leverage)

1. **Retrospective summaries** — every 10 runs, `improve()` produces a short "lab meeting" style summary.
2. **Direction Scorer** — extracts direction-level conclusions from the graph, ranked by confidence/recency.
3. **Config Similarity Radar** — shows which parts of the parameter space are explored vs. unexplored before a sweep.
4. **Parameter sensitivity ranking** — ranks which parameters actually move the needle for a given architecture/dataset pair; feeds the Config Proposer subagent.
5. **Cost-aware recall** — every Result tagged with GPU-hours/wall-clock cost, so Pre-flight Guard can quantify wasted compute.
6. **Auto-generated model cards / repro bundles** — full provenance chain compiled into a one-click downloadable artifact; what the Report Agent automates.
7. **Cross-project knowledge transfer** — querying across synthetic "projects" for institutional-memory framing.
8. **Literature grounding** — Hypothesis nodes linked to the literature claim behind them; what the Literature Agent automates on an ongoing basis.
9. **One-click file discovery** — Section 5 in full.
10. **"Catch me up" narrative query** — a synthesized narrative paragraph on returning to a project, built on `recall(type="COMPLETION")`. The strongest one-line pitch for the presentation since it mirrors the hackathon's own theme, applied to a human.

---

## 10. Dataset & Model Lineage — Deep Dive

**Dataset side.** Transformations as a real chain — raw → cleaned → augmented → split — each step its own Decision node. Column-level stats tracked across versions so drift is queryable. Label corrections tracked with who/why. New datasets checked against past ones for "what worked on something like this before." This is the data the Dataset Steward subagent operates on.

**Model side.** `derived_from` edges extended into an actual model family tree — which checkpoint a fine-tune started from, which architecture-level choices were varied. Eval memory across multiple benchmarks per model version, since "best model" depends on the deployment target's metric. Failure-mode memory — specific hard examples a model gets wrong, tied to model version — turns into a lightweight regression test for every new fine-tune.

---

## 11. The Four Demo Moments

1. **Pre-flight déjà vu** — a run with a config already tried six days ago gets blocked, surfacing the prior result before any compute is spent.
2. **Lineage trace** — clicking into any run reveals the full chain of hypotheses, decisions, and prior configs that led to it.
3. **Negative-result recall / NL query** — a free-form question across history returns a synthesized, cited answer that includes a failed run most dashboards would have buried.
4. **Live agent memory** — Claude Code, mid-task, queries Groundhog via MCP before writing a training script, discovers a planned learning rate already failed, and adjusts its plan live, on screen, with no human prompting it to check.

---

## 12. Build Strategy: Open Source vs. Cloud

- **Local development stack:** open-source Cognee, self-hosted, SQLite + Kuzu. What's actually judged and what targets the Best Use of Open Source track.
- **Cognee Cloud:** used only as a visualization layer for the demo video. Free Developer plan available via the hackathon's `COGNEE-35` code.
- **Local Ollama:** used as the low-cost path in the hybrid LLM routing strategy (Section 14, Person 4) for high-volume, lower-stakes operations.
- **Deployment (optional):** Railway or Fly.io if a hosted demo is wanted beyond the local/video walkthrough.

---

## 13. Pre-Hackathon Deliverable (Day 0)

Three contracts must be locked and reviewed by all four people before parallel work begins, since they're what let everyone except Person 1 build against mocks instead of waiting on the real backend:

1. **Graph schema (`schema.py`)** — the node/edge types from Section 4.1–4.2.
2. **API contract** — exact request/response JSON shapes for every endpoint the dashboard and MCP server will call (`/check-config`, `/remember`, `/query`, `/find-file`, `/lineage/{run_id}`).
3. **MCP tool contract** — the four tool names, parameters, and response shapes from Section 6.

Once these are locked, the mocking strategy in Section 14 is what makes the rest of the week genuinely parallel.

---

## 14. Team Roles & 4-Person Parallel Build Plan

**The core idea:** Person 1 builds the real Cognee backend; everyone else builds against mocked responses that exactly match the Day-0 contracts (generated via the Gemini API so the fake data still looks ML-plausible, not just placeholder text), then swaps to real calls as Person 1's pieces land mid-week. Each person's first 1–2 days are deliberately the part of their work least dependent on anyone else, so the start of the week has zero cross-blocking by construction.

### Person 1 — Data Layer (Cognee core)
Owns the graph schema, the `cognee.add()`/`cognify()` pipeline, the raw `remember()`/`recall()`/`improve()`/`forget()` wrapper functions, the file watcher connector, `Artifact` node indexing, typed `DataPoint` classes, and `@observe` tracing. This is the role everyone else depends on, so the first two days focus purely on getting a single run fully ingestable.

- Day 1: Finalize `schema.py`. Stand up local Cognee (SQLite + Kuzu). Get `cognee.add()` + `cognify()` working for one hardcoded run document.
- Day 2: Implement the `remember()` wrapper (enriched-document ingestion path). Implement the file watcher connector. Define `DataPoint` subclasses for all node types.
- Day 3: Implement `recall(type="GRAPH")` for Pre-flight Guard matching. Implement Artifact node creation and linking.
- Day 4: Implement `recall(type="CHUNKS")` for config similarity. Implement `forget()` for dead-end pruning and automatic noise reduction.
- Day 5: Implement the `improve()`/`memify()` scheduled job. Wrap the pipeline in `@observe`.
- Day 6: Implement the private/shared dataset split and `promote()` action. Integration-test with Person 2's API layer.
- Day 7: Buffer, bug fixes, freeze backend for demo.

### Person 2 — App Layer (full-stack: frontend + backend)
Owns the REST API wrapping Person 1's functions and the entire dashboard. Locks the API contract with Person 1 on Day 0, then builds against mocked responses until real calls are ready.

- Day 1: Lock the API contract. Scaffold the API server with stub endpoints returning mock data. Build the dashboard shell (sidebar + run detail panel) against the mock.
- Day 2: Build the Pre-flight Guard UI fully against mocked `/check-config` responses (Gemini-generated match/no-match JSON in the contract shape).
- Day 3: Build the Lineage Explorer view against mocked lineage data.
- Day 4: Build the NL query bar UI against mocked `/query` responses.
- Day 5: Swap mocked endpoints for Person 1's real backend as pieces land; begin integration testing.
- Day 6: Add "locate file" actions, the research findings feed, and retrospective summary cards.
- Day 7: Polish, responsive layout, final integration pass across all four people's pieces.

### Person 3 — Domain Layer (ML research specialist)
Owns the W&B Bridge connector, the Jupyter/Colab magic command, the ontology grounding, and dataset/model lineage correctness. Day 1's work needs nothing from anyone else.

- Day 1: Define the ML ontology (optimizer IS-A, architecture IS-A, relationships) as a Cognee ontology file.
- Day 2: Build the W&B Bridge connector against a real or sandbox W&B project. Until Person 1's `remember()` exists, write to a local staging file in the agreed schema shape so it can be plugged in later without blocking.
- Day 3: Build the Jupyter/Colab magic command.
- Day 4: Define dataset lineage details (raw→cleaned→augmented→split) and model lineage (`derived_from` extension for checkpoints and architecture choices).
- Day 5: Build the Dataset Steward and Literature Agent subagent logic, supplying ML correctness while Person 4 supplies the LLM call plumbing.
- Day 6: Validate end-to-end ML correctness of Direction Scorer and sensitivity outputs against realistic synthetic run data; prep demo datasets.
- Day 7: Demo data prep, README ML-domain sections, buffer.

### Person 4 — Intelligence Layer (LLM orchestration & agentic features)
Owns the hybrid local-Ollama/cloud-API routing strategy, every LLM-powered feature, and the Claude Code MCP connector. Day 1's infra work needs nothing from anyone else.

- Day 1: Design the hybrid routing strategy — local Ollama for high-volume operations (cognify entity extraction, embeddings), cloud API for low-volume higher-capability operations (final `recall(type="COMPLETION")` synthesis, Direction Scorer claim extraction). Stand up local Ollama and configure Cognee's LLM provider settings for both paths.
- Day 2: Build the routing/fallback layer (local-first, escalate to cloud when needed, configurable per operation type) as a wrapper Person 1's `recall()`/`improve()` calls will use.
- Day 3: Build the MCP server scaffold and the four tools, wired against mocked backend responses (matching Person 2's API contract shapes) until Person 1's real functions are ready.
- Day 4: Implement the orchestrator (event router) plus the Config Proposer and Triage Agent.
- Day 5: Implement the Literature Agent and Report Agent (model card generation), with Person 3 for ML correctness.
- Day 6: Swap the MCP server and subagents over to real backend calls as they land; run the live Claude Code demo end-to-end.
- Day 7: Measure and report token spend savings from local-first routing (concrete README number), buffer, demo rehearsal.

### Keeping the parallelism real
A short end-of-day sync to flag any contract drift (e.g. Person 1 needing to add a schema field) so nobody's mock silently goes stale, plus a mid-week (Day 5) checkpoint where every mocked integration point gets swapped for its real counterpart in one pass, rather than each person discovering integration issues independently late in the week.

---

## 15. Key Principles to Hold Onto

- **Rationale over metrics.** The W&B connector and the agents.md log must always capture *why*, not just *what*.
- **agents.md as structured, append-only.** The strict schema is what makes unified human-and-agent lineage traversal possible.
- **Open source locally, cloud for visualization only.** Cognee Cloud is a presentation aid, not infrastructure.
- **The graph is the coordination layer, not just storage.** Subagents — and now Claude Code via MCP — read and write the same Cognee graph rather than messaging each other.
- **Contracts before code.** The Day-0 schema, API, and MCP contracts are what let four people build genuinely in parallel without interfering with each other.
- **Scope to what four people can ship in a week.** Core features (Section 8) are the floor; stretch features (Section 9), subagents (Section 7), and the MCP connector (Section 6) are ranked by leverage so the team can stop wherever time runs out.
- **Negative results are a feature, not an edge case.** The Recall Engine treats failed runs as first-class memory.
