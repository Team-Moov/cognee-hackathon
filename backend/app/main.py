"""Groundhog — App Layer Backend (Cognee-backed API gateway + Groq)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app import cognee_client
from app.routers import runs, query, files, lineage, agents

logging.basicConfig(
    level=settings.api_log_level.upper(),
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("groundhog.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Groundhog started — Cognee-backed API gateway")
    yield
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

app.include_router(runs.router,    prefix="/api")
app.include_router(query.router,   prefix="/api")
app.include_router(files.router,   prefix="/api")
app.include_router(lineage.router, prefix="/api")
app.include_router(agents.router,  prefix="/api")


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
