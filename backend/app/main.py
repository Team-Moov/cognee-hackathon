"""Groundhog — App Layer Backend (Cognee-backed API gateway + Groq)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app import cognee_client
from app.routers import runs, query, files, lineage, agents, projects, insights

logging.basicConfig(
    level=settings.api_log_level.upper(),
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("groundhog.api")


import asyncio
import sys
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.append(_ROOT)

# NOTE: `projects` (imported above from app.routers) is the ROUTER module; the
# projects *data* module is imported under an alias to avoid shadowing it, which
# would break `app.include_router(projects.router, ...)` below.
from app import projects as projects_module
from connectors.wandb_sync import sync_once

async def _wandb_sync_loop():
    while True:
        try:
            projs = projects_module.list_projects()
            for p in projs:
                wb = p.get("wandb") or {}
                if wb.get("sync_enabled") and wb.get("entity") and wb.get("project"):
                    # Run in executor to avoid blocking the event loop
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        sync_once,
                        f"http://127.0.0.1:{settings.api_port}",
                        p["project_id"],
                        wb["entity"],
                        wb["project"],
                        wb.get("api_key")
                    )
        except Exception as e:
            logger.warning("Background W&B sync loop error: %s", e)
        await asyncio.sleep(60)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Groundhog started — Cognee-backed API gateway")
    sync_task = asyncio.create_task(_wandb_sync_loop())
    yield
    sync_task.cancel()
    logger.info("Groundhog shut down")


app = FastAPI(
    title="Groundhog — ML Experiment Memory",
    description=(
        "REST API backed by Cognee memory and Groq generation."
    ),
    version="3.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(projects.router, prefix="/api")
app.include_router(runs.router,    prefix="/api")
app.include_router(query.router,   prefix="/api")
app.include_router(files.router,   prefix="/api")
app.include_router(lineage.router, prefix="/api")
app.include_router(agents.router,  prefix="/api")
app.include_router(insights.router, prefix="/api")


@app.get("/api/graph")
async def graph(project_id: str | None = None):
    """Node-link memory graph for the Memory Graph view, scoped to a project."""
    if not settings.cognee_api_url:
        return {"nodes": [], "edges": []}
    try:
        return await cognee_client.get_graph(
            settings.cognee_api_url,
            project=projects_module.resolve_dataset(project_id) if project_id else None,
            timeout=settings.cognee_call_timeout_seconds,
        )
    except Exception as e:
        logger.warning("graph fetch failed: %s", e)
        return {"nodes": [], "edges": [], "error": str(e)}


@app.get("/api/health")
async def health():
    try:
        cognee_health = await cognee_client.health(settings.cognee_api_url, timeout=5.0)
        return {
            "status": "ok",
            "db": "cognee",
            "cognee": cognee_health,
            "version": "3.0.0",
        }
    except Exception as e:
        return {"status": "degraded", "error": str(e), "version": "3.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
        log_level=settings.api_log_level,
    )
