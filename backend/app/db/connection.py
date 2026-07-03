"""
asyncpg connection pool + schema bootstrap.
call await init_db() once at startup.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import asyncpg

logger = logging.getLogger("groundhog.db")
_pool: Optional[asyncpg.Pool] = None

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


async def _init_conn(conn: asyncpg.Connection) -> None:
    """Per-connection init hook — reserved for future codec registration."""
    pass


async def init_db() -> None:
    """Create the connection pool and run schema migrations."""
    global _pool
    from app.config import settings

    logger.info("Connecting to PostgreSQL…")
    _pool = await asyncpg.create_pool(
        settings.database_url,
        min_size=2,
        max_size=10,
        init=_init_conn,
        command_timeout=30,
    )
    async with _pool.acquire() as conn:
        schema_sql = SCHEMA_PATH.read_text(encoding="utf-8")
        await conn.execute(schema_sql)
    logger.info("PostgreSQL ready — schema applied")


async def close_db() -> None:
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


def get_pool() -> asyncpg.Pool:
    if _pool is None:
        raise RuntimeError("Database pool not initialised — call await init_db() first")
    return _pool
