"""
PostgreSQL CRUD for the `runs` table.
Combines: exact config_hash lookup, HNSW vector similarity search, tsvector full-text search.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.db.connection import get_pool
from app.utils import compute_config_hash, generate_config_summary

logger = logging.getLogger("groundhog.db.runs")


def _row_to_dict(row) -> Dict[str, Any]:
    d = dict(row)
    # asyncpg returns datetime objects; convert to ISO string
    for key in ("created_at", "updated_at"):
        if key in d and isinstance(d[key], datetime):
            d[key] = d[key].isoformat()
    # Remove internal vector/ts columns from API output
    d.pop("embedding", None)
    d.pop("ts", None)
    # Ensure run_id alias
    if "id" in d:
        d["run_id"] = d.pop("id")
    # JSONB comes back as strings in some asyncpg versions
    for col in ("config", "metrics", "artifacts"):
        if isinstance(d.get(col), str):
            try:
                d[col] = json.loads(d[col])
            except Exception:
                pass
    # timestamp alias
    if "timestamp" not in d:
        d["timestamp"] = d.get("created_at", "")
    return d


async def save_run(data: Dict[str, Any]) -> str:
    """Upsert a run into PostgreSQL."""
    run_id = data.get("run_id") or str(uuid.uuid4())[:8]
    config = data.get("config") or {}
    config_hash = compute_config_hash(config)
    config_summary = generate_config_summary(config)
    metrics = data.get("metrics") or {}

    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO runs (
                id, experiment, config, config_hash, config_summary,
                metrics, rationale, git_commit, gpu_hours, artifacts,
                status, error_message, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,NOW())
            ON CONFLICT (id) DO UPDATE SET
                experiment     = EXCLUDED.experiment,
                config         = EXCLUDED.config,
                config_hash    = EXCLUDED.config_hash,
                config_summary = EXCLUDED.config_summary,
                metrics        = EXCLUDED.metrics,
                rationale      = EXCLUDED.rationale,
                git_commit     = EXCLUDED.git_commit,
                gpu_hours      = EXCLUDED.gpu_hours,
                artifacts      = EXCLUDED.artifacts,
                status         = EXCLUDED.status,
                error_message  = EXCLUDED.error_message,
                updated_at     = NOW()
            """,
            run_id,
            data.get("experiment", "unnamed"),
            json.dumps(config),
            config_hash,
            config_summary,
            json.dumps(metrics),
            data.get("rationale", ""),
            data.get("git_commit", "unknown"),
            data.get("gpu_hours"),
            json.dumps([a if isinstance(a, dict) else vars(a) for a in (data.get("artifacts") or [])]),
            data.get("status", "completed"),
            data.get("error_message")
        )
    logger.info("Saved run %s (hash=%s…)", run_id, config_hash[:8])
    return run_id


async def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT * FROM runs WHERE id = $1", run_id
        )
    return _row_to_dict(row) if row else None


async def get_all_runs(
    experiment: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 200,
) -> List[Dict[str, Any]]:
    clauses = []
    args: list = []
    if experiment:
        args.append(experiment)
        clauses.append(f"experiment = ${len(args)}")
    if status:
        args.append(status)
        clauses.append(f"status = ${len(args)}")

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    args.append(limit)

    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM runs {where} ORDER BY created_at DESC LIMIT ${len(args)}",
            *args,
        )
    return [_row_to_dict(r) for r in rows]


async def get_runs_for_experiment(experiment: str) -> List[Dict[str, Any]]:
    return await get_all_runs(experiment=experiment)


async def find_by_config_hash(config_hash: str) -> List[Dict[str, Any]]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM runs WHERE config_hash = $1 ORDER BY created_at DESC",
            config_hash,
        )
    return [_row_to_dict(r) for r in rows]


async def semantic_search(
    query_embedding: "np.ndarray",
    limit: int = 10,
    experiment: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """HNSW cosine ANN search. Returns runs sorted by semantic similarity."""
    clauses = ["embedding IS NOT NULL"]
    args: list = [query_embedding]
    if experiment:
        args.append(experiment)
        clauses.append(f"experiment = ${len(args)}")
    args.append(limit)

    where = "WHERE " + " AND ".join(clauses)
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT *, 1 - (embedding <=> $1) AS similarity
            FROM runs
            {where}
            ORDER BY embedding <=> $1
            LIMIT ${len(args)}
            """,
            *args,
        )
    results = []
    for r in rows:
        d = _row_to_dict(r)
        d["similarity"] = float(r["similarity"])
        results.append(d)
    return results


async def fulltext_search(
    query: str,
    limit: int = 10,
    experiment: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """tsvector GIN full-text search with ts_rank scoring."""
    clauses = ["ts @@ plainto_tsquery('english', $1)"]
    args: list = [query]
    if experiment:
        args.append(experiment)
        clauses.append(f"experiment = ${len(args)}")
    args.append(limit)

    where = "WHERE " + " AND ".join(clauses)
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"""
            SELECT *, ts_rank(ts, plainto_tsquery('english', $1)) AS rank
            FROM runs
            {where}
            ORDER BY rank DESC
            LIMIT ${len(args)}
            """,
            *args,
        )
    results = []
    for r in rows:
        d = _row_to_dict(r)
        d["text_rank"] = float(r["rank"])
        results.append(d)
    return results
