# Groundhog — Data Layer & API Server

This is the data and memory layer for Groundhog, built on **Cognee** (open-source memory layer for AI agents). It provides a REST API for the frontend dashboard and MCP server to interact with the ML experiment memory graph.

## Architecture & Constraints

*   **Single Gatekeeper:** To avoid SQLite/Kuzu file locking issues with concurrent access, **only the FastAPI server imports and calls `cognee`**. All other components (Dashboard, MCP server, File Watcher) must route through this API.
*   **Tech Stack:** Python 3.11+, Cognee (local SQLite/Kuzu), FastAPI, Groq for LLM generation, local deterministic embeddings for vector recall, and Watchdog.

## Setup Instructions

1.  **Environment Setup**
    Create a Python virtual environment and install dependencies:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```

2.  **API Keys**
    Rename `.env.example` to `.env` or edit the existing `.env` file and insert your Groq API key.
    ```env
    GROQ_API_KEY="your_groq_api_key_here"
    ```

3.  **Verification (Day 1 check)**
    Run the Day 1 test script to ensure Cognee can successfully connect to Groq for generation.
    ```bash
    python test_day1.py
    ```

4.  **Seed Demo Data**
    Before running the server or connecting the frontend, populate the graph with realistic synthetic ML runs:
    ```bash
    python seed_demo_data.py
    ```
    *Note: The script includes brief delays between insertions to respect Groq's free-tier rate limits.*

5.  **Run the API Server**
    Start the FastAPI application. It will automatically start the file watcher in a background thread.
    ```bash
    uvicorn main:app --host 0.0.0.0 --port 8010 --reload
    ```
    Port 8010, not 8000 — `backend/app/main.py` (the Postgres app layer the frontend/MCP server call) also runs on 8000 and needs to run alongside this one; see `backend/app/cognee_client.py`.

    The API contract (OpenAPI spec) is available at `http://localhost:8010/docs` and `http://localhost:8010/openapi.json`.

## API Endpoints

*   **`POST /remember`**: Ingest a run.
*   **`POST /check-config`**: Pre-flight Guard to check for duplicate configs via exact hash match or semantic similarity.
*   **`POST /query`**: Free-form memory query.
*   **`GET /find-file`**: Artifact lookup by description.
*   **`GET /lineage/{run_id}`**: Full decision/config chain for a run.
*   **`POST /improve`**: Trigger graph enrichment.
*   **`POST /forget`**: Remove stale data.
*   **`POST /promote`**: Promote node to shared dataset.
*   **`GET /orphans`**: Find untracked files and broken artifact references.
*   **`GET /health`**: Server health check.

## File Watcher

The API server automatically runs a `watchdog` process monitoring the `./watched_runs` directory. Dropping a valid JSON/YAML result file into this directory will automatically trigger ingestion into the memory graph.
