# Groundhog — ML Experiment Reproducibility & Memory

Groundhog is a **memory-graph layer for ML experiments**, built on open-source
[Cognee](https://github.com/topoteretes/cognee). It sits on top of a
researcher's existing workflow and answers the questions their tools don't:

- **"Have we tried this config, and what happened?"** — Pre-flight Guard blocks wasted compute.
- **"What have we learned, and where next?"** — a self-improving research memory, not just a log.
- **"Where's my checkpoint / plot / log file?"** — one-click artifact discovery.
- **"Is my coding agent about to repeat a mistake?"** — the same memory is queryable live over MCP.

Everything runs **locally** and open-source. No Cognee Cloud, no Postgres.

---

## What's new (current architecture)

This differs substantially from the earliest scaffold — key changes:

- **Postgres is gone.** The backend is a thin gateway over the Cognee memory
  server. Structured, restart-safe listings (runs, agent findings, artifacts,
  projects) live in small JSON indexes, not a relational DB.
- **Multi-provider LLM, one key.** Chat/extraction runs on **Groq, Gemini, or
  AI/ML API** — pick one with `GROUNDHOG_LLM_PROVIDER`. Embeddings default to a
  **local fastembed** model (no key, offline), so a single provider key powers
  the whole system. (See `llm_setup.py`.)
- **Projects.** Create a project → get a `project_id` (which *is* a Cognee
  dataset) → paste it into your notebook or `.py` repo via the SDK, or point the
  W&B daemon at it. Memory is isolated per project.
- **A Python SDK** (`sdk/groundhog.py`) — `init / remember / check / query`,
  zero-dependency, with automatic git-commit rationale harvesting.
- **Rich capture** — a run records config, metrics, **the dataset used**
  (name/version/preprocessing/split/quality), **output files** (scanned into
  typed `Artifact` nodes), **cost** (GPU-hours + wall-clock), **hypothesis**,
  and **`derived_from` lineage** — not just config + metrics.
- **Canonical config hashing** — the Pre-flight Guard ignores noise fields
  (`seed`, `output_dir`, `gpu_id`, …) and key aliases (`lr` ↔ `learning_rate`),
  so it matches the messy configs researchers actually run.
- **Typed graph, real edges.** `schema.py`'s DataPoints are written as real
  nodes with `belongs_to` / `produced_by` / `used_dataset` edges via
  `add_data_points`, not just a text blob.
- **In-process embedded DBs** — Kuzu/LanceDB run in-process (not subprocess),
  which removes the Windows lock contention that broke recall.
- **A W&B sync daemon** (`connectors/wandb_sync.py`) — incremental, `--watch`,
  creds pulled from the project (no hardcoded project name).

---

## Architecture

```
   Notebook / .py repo (SDK) ─┐
   Dashboard (React :5173) ───┼─► Backend gateway :8000 ─► Cognee memory :8010 ─► Cognee
   MCP client (Claude/Cursor) ┘        (thin, stateless)      (single gatekeeper)   ├─ Kuzu (graph)
   W&B daemon ────────────────────────────────────────────►                          ├─ LanceDB (vectors)
                                                                                      └─ SQLite (relational)
```

- **Single gatekeeper:** only the Cognee server (root `main.py`, port **8010**)
  opens Cognee's local DB files. Everything else reaches memory over HTTP through
  it. Run exactly **one** Cognee server at a time.
- **Backend gateway** (`backend/app`, port **8000**): projects, run listing,
  agent findings, and proxying `/remember` `/check-config` `/query` to :8010.
- **Frontend** (`frontend`, Vite, port **5173**): the dashboard.
- **MCP server** (`mcp_server`, port **8002**, optional): 4 tools for coding agents.

---

## Setup

```bash
python -m venv venv
# Windows: venv\Scripts\activate   |   *nix: source venv/bin/activate
pip install -r requirements.txt        # includes fastembed + litellm
cp .env.example .env                    # then edit — see below
```

### Choose a provider in `.env`

```env
GROUNDHOG_LLM_PROVIDER=groq        # groq | gemini | aimlapi
GROQ_API_KEY="..."                 # set the key for your chosen provider
# GEMINI_API_KEY / AIMLAPI_API_KEY as needed
```

Embeddings default to local fastembed (`BAAI/bge-small-en-v1.5`, 384-dim) — no
key needed. To use cloud embeddings (e.g. with AI/ML API), set
`EMBEDDING_PROVIDER=openai_compatible`, `EMBEDDING_MODEL=text-embedding-3-small`,
`EMBEDDING_ENDPOINT=https://api.aimlapi.com/v1`, `EMBEDDING_DIMENSIONS=1536`.

> **Note:** Cognee force-loads `.env` with `override=True`, so **`.env` is the
> source of truth** — switch providers there, not via shell env.

---

## Run it (4 processes)

```bash
# 1. Cognee memory server (single gatekeeper)
python main.py                                   # → :8010

# 2. Backend gateway
cd backend && python -m uvicorn app.main:app --port 8000    # → :8000

# 3. Frontend dashboard
cd frontend && npm install && npm run dev        # → http://localhost:5173

# 4. (optional) MCP server for coding agents
python -m uvicorn mcp_server.main:app --port 8002
```

Open **http://localhost:5173** → create a project in the sidebar → start recording.

> **Shut down with Ctrl+C**, not a force-kill — embedded Kuzu releases its lock
> cleanly on graceful stop. If you ever hit a stale lock, delete
> `…/site-packages/cognee/.cognee_system` (the JSON indexes keep your run list).

---

## Using the SDK (notebook or any `.py` project)

```python
import groundhog                       # from sdk/ (or pip-install once packaged)
groundhog.init(project_id="proj_...")  # project_id from the dashboard

# pre-flight — skip a config you already ran (noise/alias tolerant)
if groundhog.check(config)["already_tried"]:
    print("already ran this — skipping")

# record the FULL picture (rationale auto-harvested from your git commit)
groundhog.remember(
    config=config,
    metrics={"val_accuracy": 0.91},
    dataset={"name": "CIFAR-10", "version": "v2",
             "preprocessing": "random crop + flip", "quality_issues": "~2% mislabeled"},
    output_dir="./outputs",            # scanned into Artifact nodes
    hypothesis="lower lr improves convergence",
    gpu_hours=2.5,
)

groundhog.query("what was the best val_accuracy so far?")
```

**Colab / Kaggle:** those run on remote VMs that can't see your localhost. Pass a
reachable URL — `groundhog.init(project_id=..., base_url="https://<ngrok-or-deploy>")`
(e.g. `ngrok http 8000`). No code change otherwise.

---

## W&B sync daemon

```bash
# set W&B creds on the project once (dashboard or API), then:
python connectors/wandb_sync.py --project-id proj_... --watch --interval 60
```
Incremental (only new runs), scoped to the project, harvests `run.notes` as
rationale. Requires `pip install wandb`.

---

## Cognee memory server endpoints (port 8010)

`POST /remember` · `POST /check-config` · `POST /query` · `GET /runs` ·
`GET /agent-findings` · `POST /agent-findings/{id}/dismiss` · `GET /find-file` ·
`GET /lineage/{run_id}` · `POST /improve` · `POST /forget` · `POST /promote` ·
`GET /orphans` · `GET /health`. OpenAPI at `http://localhost:8010/docs`.

## Backend gateway endpoints (port 8000, `/api` prefix)

`POST /api/projects` · `GET /api/projects` · `POST /api/runs/remember` ·
`POST /api/runs/check-config` · `GET /api/runs/` · `POST /api/query` ·
`GET /api/agents/suggestions` · `POST /api/agents/report` · `GET /api/files/find`.
All accept an optional `project_id` to scope to one project.

---

## Best Use of Cognee

Groundhog uses all four lifecycle ops (`remember` / `recall` / `improve` /
`forget`), typed `DataPoint` schemas with real edges, `node_set` scoping,
session-based private/shared memory + promotion, OWL **ontology grounding**
(`ontology/ml_ontology.owl`), pipeline tracing (`enable_tracing`), and the graph
as a **blackboard** that five subagents (config proposer, triage, dataset
steward, literature, report) coordinate through. See
`groundhog_implementation_plan (1).md` for the full design and `db_setup.md` for
the storage/runtime reference.
