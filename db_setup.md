# Groundhog — Storage & Runtime Reference

> **Status:** Current. Groundhog stores everything in **Cognee's embedded
> databases** plus a few small **JSON indexes**. There is **no Postgres / no
> pgvector** — earlier versions of this file described a two-tier Postgres setup
> that has been fully removed. See the end for the historical note.

---

## Overview — where data lives

| What | Store | Managed by | Written/read by |
|---|---|---|---|
| Graph (nodes + edges) | **Kuzu** (embedded) | Cognee | `memory.py` via `cognify` / `add_data_points` / `recall` |
| Vectors (embeddings) | **LanceDB** (embedded) | Cognee | Cognee recall / semantic search |
| Relational + cache | **SQLite** | Cognee | Cognee internals (datasets, sessions) |
| Run list, artifacts, agent findings | **`groundhog_index.json`** | `run_index.py` | Cognee server (`main.py`) — deterministic, restart-safe listings |
| Projects + W&B creds | **`groundhog_projects.json`** | `backend/app/projects.py` | Backend gateway |
| W&B sync watermark | `connectors/.wandb_sync_state.json` | `connectors/wandb_sync.py` | W&B daemon |

**Why the JSON indexes:** Cognee is a *semantic* memory — great for fuzzy recall,
wrong tool for "give me the exact last 50 runs as structured JSON." Rather than
ask the LLM to hallucinate a run list, the deterministic facts of every
run/artifact/finding are mirrored into `groundhog_index.json` as they're
ingested. Cognee stays responsible for the semantic recall it's actually good at.

---

## Processes & ports

| Service | Port | Start |
|---|---|---|
| Cognee memory server (root `main.py`) — **single gatekeeper** | 8010 | `python main.py` |
| Backend gateway (`backend/app/main.py`) | 8000 | `cd backend && python -m uvicorn app.main:app --port 8000` |
| Frontend (Vite) | 5173 | `cd frontend && npm run dev` |
| MCP server (optional) | 8002 | `python -m uvicorn mcp_server.main:app --port 8002` |

**Single-gatekeeper rule:** only `main.py` (8010) opens Cognee's local DB files.
Everyone else (backend, MCP, connectors, dashboard) reaches memory over HTTP.
**Run exactly one Cognee server** — two processes touching the same Kuzu/LanceDB
files fight over the lock.

---

## LLM + embedding configuration (`llm_setup.py`)

Configured once at startup by `llm_setup.configure_cognee()` using the **real**
Cognee setters (the old `cognee.config.llm_config = {...}` was a no-op):

- **Chat/extraction provider:** `GROUNDHOG_LLM_PROVIDER = groq | gemini | aimlapi`.
  - `groq` and `aimlapi` are wired through Cognee's `custom` provider (litellm);
    there is no native `groq` provider in Cognee's enum. `aimlapi` points the
    OpenAI-compatible base URL at `https://api.aimlapi.com/v1`.
  - `gemini` uses Cognee's native Gemini adapter.
- **Embeddings:** default **local fastembed** (`BAAI/bge-small-en-v1.5`, 384-dim,
  no key, offline). Override via `EMBEDDING_PROVIDER` / `EMBEDDING_MODEL` /
  `EMBEDDING_ENDPOINT` / `EMBEDDING_DIMENSIONS` / `EMBEDDING_API_KEY`.
- **In-process DBs:** `set_graph_database_subprocess_enabled(False)` +
  `set_vector_db_subprocess_enabled(False)` so Kuzu/LanceDB run in the server
  process (one lock owner) — fixes intermittent "Could not set lock on file …
  ladybug" errors on recall. Override with `COGNEE_GRAPH_SUBPROCESS=true`.
- **Access control:** `ENABLE_BACKEND_ACCESS_CONTROL=false` for simple local use.

> `.env` wins: Cognee calls `dotenv.load_dotenv(override=True)` on import, so
> environment values in `.env` override shell exports. Switch providers in `.env`.

### Relevant `.env` keys

```env
GROUNDHOG_LLM_PROVIDER=groq            # groq | gemini | aimlapi
GROQ_API_KEY=... / GEMINI_API_KEY=... / AIMLAPI_API_KEY=...
# EMBEDDING_PROVIDER=fastembed (default) | openai_compatible | gemini | ollama
GROUNDHOG_TYPED_NODES=true             # write typed schema.py nodes + edges
GROUNDHOG_TRACING=true                 # enable_tracing()
GROUNDHOG_RESET_ON_START=false         # true = wipe graph on boot (opt-in only)
PREFLIGHT_SIMILARITY_THRESHOLD=0.55
COGNEE_API_URL=http://localhost:8010   # backend -> cognee
COGNEE_CALL_TIMEOUT_SECONDS=180
```

---

## Cognee storage location & reset

Cognee's stores default to inside the installed package:
```
<site-packages>/cognee/.cognee_system/databases/
```
To reset (clears stale locks + graph; JSON indexes are separate and survive):
delete that `.cognee_system` directory, **or** set `GROUNDHOG_RESET_ON_START=true`
once. Startup no longer prunes automatically — memory now **survives restarts**
(the old lifespan `prune_system` call that wiped the graph every boot was removed).

To move storage out of the package (recommended for deployment), point Cognee at
a persistent path via `cognee.config.data_root_directory` /
`system_root_directory` (env-driven) so a rebuild/redeploy doesn't lose data.

---

## Schema — 9 typed `DataPoint` nodes + edges (`schema.py`)

All 9 node types (`Experiment`, `ResearchThread`, `Config`, `Dataset`, `Result`,
`Artifact`, `Hypothesis`, `Decision`, `AgentAction`) are real `DataPoint`
subclasses with `index_fields` and validators. They now also carry
**relationship fields** (`belongs_to`, `produced_by`, `used_dataset`,
`derived_from`) that become real graph **edges** when written via
`add_data_points`. See `schema_details.md`.

---

## Troubleshooting

- **`Could not set lock on file …ladybug` on query** — a second Cognee process
  is running, or a stale lock from a force-killed process. Ensure one gatekeeper;
  clear `.cognee_system` if stale. In-process DB mode (default) avoids the
  subprocess-vs-main contention.
- **LLM steps fail with "API key not set"** — the provider key for
  `GROUNDHOG_LLM_PROVIDER` isn't in `.env`. Embeddings still work locally.
- **Embedding dimension mismatch after switching embedders** — prune the vector
  store first (`GROUNDHOG_RESET_ON_START=true` once, or delete `.cognee_system`).
  Pick one embedding model per database.
- **`ModuleNotFoundError: cognee`** — `pip install -r requirements.txt`.

---

## Historical note

Earlier revisions of this document described a **Tier 2 PostgreSQL + pgvector**
backend (tables `runs`, `run_lineage`, `lineage_graphs`, `agent_suggestions`).
That tier was removed: pgvector had no usable Windows build, and the deterministic
listings it provided are now served from `groundhog_index.json`. The backend
imports no `asyncpg` / `pgvector` and requires no database install.
