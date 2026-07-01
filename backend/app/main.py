"""Groundhog — App Layer Backend (PostgreSQL + pgvector + Gemini)."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.db.connection import init_db, close_db
from app.routers import runs, query, files, lineage, agents

logging.basicConfig(
    level=settings.api_log_level.upper(),
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
)
logger = logging.getLogger("groundhog.api")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    logger.info("Groundhog started — PostgreSQL + pgvector + Gemini")
    yield
    await close_db()
    logger.info("Groundhog shut down")


app = FastAPI(
    title="Groundhog — ML Experiment Memory",
    description=(
        "REST API backed by PostgreSQL 16 + pgvector (HNSW cosine) "
        "+ tsvector full-text + recursive CTE graph traversal + Gemini embeddings."
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
    from app.db.connection import get_pool
    try:
        pool = get_pool()
        async with pool.acquire() as conn:
            pg_version = await conn.fetchval("SELECT version()")
        return {"status": "ok", "db": "postgres", "pg_version": pg_version, "version": "3.0.0"}
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
