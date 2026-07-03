# Groundhog — Database Setup Reference

> **Last updated:** 2026-07-03  
> **Maintainer:** Ganesh (Person 1 — Data Layer)  
> **Status:** PostgreSQL backend ✅ **PRIMARY API on port 8000**. Frontend (Vite, port 5173) proxies `/api/*` → `localhost:8000`. Cognee layer (`main.py`) is standalone memory tool — not used by frontend. pgvector ⏭️ SKIPPED — tsvector full-text + recent-runs fallback active.

---

## Overview — Two DB Tiers

Groundhog uses **two independent database tiers** that serve different purposes and are managed separately:

| Tier | Component | Technology | Used by |
|---|---|---|---|
| **1 — Cognee Memory Layer** | Relational store | SQLite (`aiosqlite` + SQLAlchemy) | `memory.py`, `schema.py` — the graph/recall engine |
| **1 — Cognee Memory Layer** | Graph store | NetworkX (in-process) | Entity/relationship traversal during `cognify` |
| **1 — Cognee Memory Layer** | Vector store | LanceDB (embedded) | Embedding index for semantic recall |
| **1 — Cognee Memory Layer** | Cache | SQLite (`cache.db`) | Cognee's internal caching layer |
| **2 — App Backend** | Primary store | PostgreSQL 16 + pgvector | `backend/app/` REST API, HNSW vector search |

**Rule:** `memory.py` / `main.py` (root) use **Tier 1 only**. `backend/app/main.py` uses **Tier 2 only**. They do not cross-call each other at the DB level.

---

## Section 1 — Cognee Memory Layer (Tier 1)

### 1.1 What Cognee manages automatically

When you call `cognee.add()` or `cognee.cognify()`, Cognee bootstraps all three stores on first use with zero extra configuration:

- **SQLite relational DB** — stored at:
  ```
  <venv>/Lib/site-packages/cognee/.cognee_system/databases/cognee_db
  ```
- **NetworkX graph** — held entirely in memory during a process; graph structure is persisted to SQLite between sessions.
- **LanceDB vector store** — stored alongside the SQLite DB in the same `.cognee_system/databases/` directory.
- **Cache DB** — `cache.db` in the same directory (used for session/token caching).

> **Note:** The current default storage path is inside the venv. This means the databases are not version-controlled and will be lost if you recreate the venv. See Section 1.4 for how to redirect to a project-local path.

### 1.2 What was confirmed running

```
Cognee version : 1.2.2
Python         : 3.14.3 (Windows 11)
Relational     : SQLite via aiosqlite + SQLAlchemy 2.0
                 URL: sqlite+aiosqlite:///<venv>/.cognee_system/databases/cognee_db
Graph engine   : NetworkX 3.6.1 (in-process, persisted to SQLite)
Vector store   : LanceDB 0.33.0
Cache          : cache.db (SQLite, 795 KB at time of check — has prior data)
LLM provider   : Gemini (gemini/gemini-2.5-flash) via .env
Embeddings     : Gemini (gemini/gemini-embedding-001, 768 dims) via .env
```

These were verified by running:
```powershell
.\venv\Scripts\python.exe -c "import cognee; print(cognee.__version__)"
.\venv\Scripts\pip.exe list | Select-String 'cognee|lancedb|networkx|aiosqlite|sqlalchemy'
```

### 1.3 Packages installed (Cognee tier)

All installed into the project venv (`.\venv\`) via `pip install cognee` (listed in root `requirements.txt`):

| Package | Version | Role |
|---|---|---|
| `cognee` | 1.2.2 | Core memory framework |
| `aiosqlite` | 0.22.1 | Async SQLite driver for relational store |
| `SQLAlchemy` | 2.0.51 | ORM + connection pool for relational layer |
| `lancedb` | 0.33.0 | Embedded vector store (replaces Kuzu for vectors) |
| `networkx` | 3.6.1 | In-process graph engine |
| `pydantic` | 2.12.5 | DataPoint schema validation |
| `pydantic-settings` | 2.14.2 | `.env` loading for config |
| `numpy` | 2.5.0 | Vector math |
| `watchdog` | 6.0.0 | File watcher connector |

> **Kuzu is NOT installed.** Despite `health()` in `main.py` reporting `"SQLite (relational) + Kuzu (graph)"`, the actual graph engine at runtime is NetworkX. Cognee 1.2.2 defaults to NetworkX when `kuzu` is not present. This is fine for the hackathon — NetworkX performs well for the graph sizes we are dealing with. If Kuzu is desired, `pip install kuzu` and set `GRAPH_DATABASE_PROVIDER=kuzu` in `.env`.

### 1.4 Redirecting storage to a project-local path (recommended)

To keep databases inside the repo (and out of the venv), add these lines to `.env`:

```env
# Redirect Cognee storage to project-local directories
DATA_PATH=./cognee_data
DB_PATH=./cognee_system
```

Or configure programmatically at startup (in `main.py`'s `_configure_cognee()`):

```python
import pathlib
cognee.config.set_data_path(str(pathlib.Path("./cognee_data").resolve()))
cognee.config.set_system_root_directory(str(pathlib.Path("./cognee_system").resolve()))
```

Add `cognee_data/` and `cognee_system/` to `.gitignore` (already done for `*.db`, `*.sqlite`).

### 1.5 Schema — 9 DataPoint node types (schema.py)

`schema.py` was expanded from a single-class stub (`Experiment` only) to the full 9-node schema:

| Class | Embeddable fields | Key structural fields |
|---|---|---|
| `Experiment` | `description` | `name`, `owner`, `created_at` |
| `ResearchThread` | `hypothesis_summary` | `name`, `status`, `experiment_id` |
| `Config` | `summary_text` | `parameters` (dict), `config_hash` (SHA-256) |
| `Dataset` | `preprocessing_notes`, `split_rationale`, `quality_issues` | `name`, `version`, `parent_dataset_id` |
| `Result` | `summary_text` | `metrics` (dict), `status`, `gpu_hours`, `config_id`, `dataset_id` |
| `Artifact` | `description` | `file_path`, `artifact_type`, `result_id`, `exists_on_disk` |
| `Hypothesis` | `statement` | `status`, `research_thread_id` |
| `Decision` | `description`, `rationale` | `made_by`, `timestamp`, `research_thread_id` |
| `AgentAction` | `rationale` | `action_type`, `parameters` (dict), `source`, `timestamp` |

**Validation confirmed:**
```powershell
.\venv\Scripts\python.exe -c "
from schema import (Experiment, ResearchThread, Config, Dataset, Result,
                    Artifact, Hypothesis, Decision, AgentAction, ALL_EDGE_TYPES)
print('All 9 DataPoint classes imported OK')
print('Edge types:', ALL_EDGE_TYPES)
"
```
Output: `All 9 DataPoint classes imported OK` — all field validators fire correctly.

### 1.6 How Cognee creates the databases on first use

No manual migration step is needed. The flow is:

1. `main.py` loads `.env` via `load_dotenv()`.
2. `_configure_cognee()` pushes LLM + embedding config into `cognee.config`.
3. The lifespan handler calls `cognee.prune.prune_system(metadata=False)` — a non-destructive ping that forces Cognee to initialise all three stores if they don't exist.
4. From that point on, every `cognee.add()` call writes to SQLite; every `cognee.cognify()` call builds the NetworkX graph and writes embeddings to LanceDB.

### 1.7 Environment variables consumed by Cognee

Set in `.env` at project root:

```env
LLM_PROVIDER=gemini
LLM_MODEL=gemini/gemini-2.5-flash
LLM_API_KEY=<your-gemini-api-key>

EMBEDDING_PROVIDER=gemini
EMBEDDING_MODEL=gemini/gemini-embedding-001
EMBEDDING_API_KEY=<your-gemini-api-key>
EMBEDDING_DIMENSIONS=768
```

Cognee reads these environment variable names directly — no prefix wrapping needed.

---

## Section 2 — Backend PostgreSQL Layer (Tier 2)

The `backend/` directory is a separate FastAPI service with its own `requirements.txt` and its own database. It does **not** import `cognee` for its primary data path — it uses PostgreSQL + pgvector for the runs/lineage/suggestions tables exposed to the frontend.

### 2.1 Schema (backend/app/db/schema.sql)

Four tables, applied automatically by `init_db()` at startup:

| Table | Purpose |
|---|---|
| `runs` | One row per ML run. Columns: `id`, `experiment`, `config` (JSONB), `config_hash`, `config_summary`, `metrics` (JSONB), `rationale`, `git_commit`, `gpu_hours`, `artifacts` (JSONB), `status`, `embedding` (vector 768), `ts` (tsvector), `created_at` |
| `run_lineage` | Directed adjacency list for graph traversal. Columns: `parent_run_id`, `child_run_id`, `edge_type` |
| `lineage_graphs` | Pre-computed full nodes/edges JSON per run. Columns: `run_id`, `nodes` (JSONB), `edges` (JSONB) |
| `agent_suggestions` | Cards from subagents. Columns: `id`, `run_id`, `experiment`, `agent_type`, `payload` (JSONB), `severity`, `dismissed`, `created_at` |

**PostgreSQL extensions required** (both bundled with PG 16 standard install):
- `vector` (pgvector) — HNSW cosine index for ANN vector search
- `pg_trgm` — trigram full-text index (used alongside `tsvector`)

### 2.2 PostgreSQL installation (Windows)

> **This step is NOT yet done.** PostgreSQL is not installed on this machine. The backend will fail to start until it is.

**Steps to install PostgreSQL 16 + pgvector on Windows:**

1. **Download PostgreSQL 16** from https://www.postgresql.org/download/windows/  
   Use the interactive installer (includes pgAdmin, StackBuilder).

2. During install:
   - Set superuser password (remember it — goes in `DATABASE_URL`)
   - Default port: `5432` (keep it)
   - Run **StackBuilder** at the end and install the **pgvector** extension from the "Database Add-ons" category.

3. **Alternatively** — install pgvector separately after PG install:
   ```powershell
   # If pgvector wasn't installed via StackBuilder:
   # Download pgvector Windows binaries from https://github.com/pgvector/pgvector/releases
   # Copy the .dll and .sql files to your PostgreSQL share/extension directory
   ```

4. **Create the database:**
   ```powershell
   # Open psql (comes with PG install, usually at C:\Program Files\PostgreSQL\16\bin\psql.exe)
   psql -U postgres
   ```
   Then inside psql:
   ```sql
   CREATE DATABASE groundhog;
   -- Verify pgvector is available:
   \c groundhog
   CREATE EXTENSION IF NOT EXISTS vector;
   SELECT * FROM pg_extension WHERE extname = 'vector';
   -- Should return one row
   \q
   ```

5. **Set `DATABASE_URL` in `backend/.env`:**
   ```env
   DATABASE_URL=postgresql://postgres:<your-password>@localhost:5432/groundhog
   ```
   Copy from `backend/.env.example`:
   ```powershell
   Copy-Item backend\.env.example backend\.env
   # Then edit backend\.env with your password
   ```

### 2.3 Backend Python packages (backend/requirements.txt)

Install into the venv **from the project root**:

```powershell
.\venv\Scripts\pip.exe install -r backend\requirements.txt
```

Installed into the venv on 2026-07-03 via:
```powershell
.\venv\Scripts\pip.exe install asyncpg pgvector groq httpx pydantic-settings
```

| Package | Installed version | Role |
|---|---|---|
| `asyncpg` | **0.31.0** ✅ | Async PostgreSQL driver |
| `pgvector` | **0.4.2** ✅ | `register_vector` codec for asyncpg + numpy codec |
| `groq` | **1.5.0** ✅ | LLM completions for query synthesis |
| `httpx` | **0.28.1** ✅ (was already present) | HTTP client for connector calls |

> **Note:** `asyncpg` and `pgvector` (the Python package) are distinct from the PostgreSQL `pgvector` extension. Both are needed — the PG extension provides the `vector` column type; the Python package teaches asyncpg how to encode/decode it.

### 2.4 Running the backend service

```powershell
# From project root, once PostgreSQL is running:
.\venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --app-dir backend
```

Or via the module entry point:
```powershell
cd backend
..\venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

On startup, `init_db()` runs `backend/app/db/schema.sql` — all four tables and indexes are created with `IF NOT EXISTS`, so it is safe to run repeatedly.

### 2.5 Health check

Once running:
```powershell
curl http://localhost:8000/api/health
# Expected: {"status":"ok","db":"postgres","pg_version":"PostgreSQL 16.x...","version":"3.0.0"}
```

---

## Section 3 — Running Both Tiers Together

The two tiers run as separate processes on different ports:

| Service | Port | Start command |
|---|---|---|
| Cognee/memory API (root `main.py`) | `8000` | `.\venv\Scripts\python.exe main.py` |
| Backend API (`backend/app/main.py`) | `8000` (same port, different service) | See 2.4 |

> **They share port 8000 by default — only one should run at a time, or change one port.** The frontend at `backend/` targets the backend API. The MCP server targets the root `main.py` API. Configure accordingly.

To run on separate ports, change `PORT=8001` in root `.env` (for `main.py`) and keep `backend/.env` at `8000`.

---

## Section 4 — Quick-Start Checklist

### Cognee layer (no install needed beyond `pip install -r requirements.txt`)

```powershell
# 1. Create venv (if not already done)
python -m venv venv

# 2. Install root dependencies
.\venv\Scripts\pip.exe install -r requirements.txt

# 3. Copy .env and fill in API key
Copy-Item .env.example .env
# Edit .env: set LLM_API_KEY and EMBEDDING_API_KEY to your Gemini key

# 4. Verify schema imports
.\venv\Scripts\python.exe -c "from schema import Experiment, Result, Config, Dataset, Artifact, Hypothesis, Decision, AgentAction, ResearchThread; print('OK')"

# 5. Start the Cognee API
.\venv\Scripts\python.exe main.py
# → Server on http://localhost:8000
# → Databases auto-created on first request to /remember
```

### Backend PostgreSQL layer

```powershell
# 1. Install PostgreSQL 16 + pgvector (see Section 2.2)

# 2. Create the groundhog database (see Section 2.2 step 4)

# 3. Install backend Python deps
.\venv\Scripts\pip.exe install -r backend\requirements.txt

# 4. Set up backend/.env
Copy-Item backend\.env.example backend\.env
# Edit: set DATABASE_URL with your PG password, and GROQ_API_KEY or LLM_API_KEY

# 5. Start the backend API
.\venv\Scripts\python.exe -m uvicorn app.main:app --reload --app-dir backend --port 8001

# 6. Health check
curl http://localhost:8001/api/health
```

---

## Section 5 — What Was Done (Chronological Log)

| Date | Action | Result |
|---|---|---|
| 2026-07-01 | Pulled `Ganesh` branch — initial `schema.py` (Experiment only), `memory.py`, `main.py`, `watcher.py` | Cognee layer scaffolded |
| 2026-07-02 | Verified `cognee.add()` + `cognify()` working for a single `Experiment` node | SQLite + NetworkX + LanceDB auto-created ✅ |
| 2026-07-02 | Confirmed Gemini LLM + embedding provider configured in `.env` | API key present and working |
| 2026-07-03 | Pulled `Vishal` branch — added `backend/` (FastAPI + PostgreSQL schema), `frontend/`, `connectors/`, `ontology/` | Full backend scaffolding merged in |
| 2026-07-03 | Inspected actual Cognee DB backends — confirmed NetworkX (not Kuzu), LanceDB (not Qdrant) | Documented in Section 1.3 |
| 2026-07-03 | Expanded `schema.py` from 1 class (`Experiment`) to all 9 `DataPoint` subclasses | Verified all classes import and validators fire ✅ |
| 2026-07-03 | Installed backend Python packages into venv: `asyncpg 0.31.0`, `pgvector 0.4.2`, `groq 1.5.0` | All import OK ✅ |
| 2026-07-03 | Installed PostgreSQL 16.14 via GUI installer. Service `postgresql-x64-16` confirmed running on port 5432 | ✅ PG server running |
| 2026-07-03 | Created `groundhog` database + `pg_trgm` extension. `pgvector` extension skipped — no prebuilt Windows binary, build tools absent, GitHub CDN blocked | Decision: use Cognee/LanceDB for all vector ops |
| 2026-07-03 | Booted `main.py` — `GET /health` returned `{"status":"ok", "cognee_version":"1.2.2"}` | **Cognee API fully operational** ✅ |
| 2026-07-03 | Chose **Option B** — run Cognee memory layer (`main.py`) as primary API. `backend/app/main.py` (PG+pgvector) deferred until pgvector is available | Hackathon strategy locked |
| 2026-07-03 | **Architecture pivot**: PostgreSQL backend promoted to **primary API (port 8000)**. Frontend now proxied via Vite `vite.config.js`. Cognee layer decoupled | Dashboard fully wired to PG |
| 2026-07-03 | Fixed `backend/app/db/runs.py` — removed dead `numpy`/`embedding` code. Fixed `connection.py` empty body. Disabled `semantic_search` in `query.py` (no pgvector column) | All 500 errors resolved ✅ |
| 2026-07-03 | Fixed `frontend/src/services/api.js` trailing-slash bug on `listRuns`. Created `frontend/vite.config.js` proxy rule for `/api/*` | Runs now appear on dashboard ✅ |

---

## Section 6 — Troubleshooting

### `ModuleNotFoundError: No module named 'cognee'`
```powershell
# Activate venv first, or use full path:
.\venv\Scripts\pip.exe install cognee
```

### `cognee.infrastructure.engine.models.DataPoint` import fails
The `schema.py` has a fallback import:
```python
try:
    from cognee.infrastructure.engine.models.DataPoint import DataPoint
except ImportError:
    from cognee.base_data_point import DataPoint
```
If both fail, your cognee version is very old — `pip install --upgrade cognee`.

### Cognee stores data in the venv (undesirable)
Set `DATA_PATH` and `DB_PATH` in `.env` to project-local paths (see Section 1.4).

### Backend fails: `cannot connect to PostgreSQL`
PostgreSQL is not installed or not running. Follow Section 2.2. Check with:
```powershell
# If PG is installed:
pg_isready -h localhost -p 5432
```

### `pgvector` extension missing: `type "vector" does not exist`
Run inside psql:
```sql
\c groundhog
CREATE EXTENSION IF NOT EXISTS vector;
```
If that fails, pgvector is not installed — see Section 2.2 step 3.

### `asyncpg` or `pgvector` (Python package) not found
```powershell
.\venv\Scripts\pip.exe install asyncpg pgvector
```

### `cache.db-wal` grows large
The WAL file is Cognee's SQLite write-ahead log. It is checkpointed automatically. If it grows unexpectedly large, it means a Cognee process was killed mid-write. Safe to delete if no Cognee process is running; it will be recreated.
