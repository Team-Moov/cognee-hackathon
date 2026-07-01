"""PostgreSQL CRUD for the agent_suggestions table."""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from app.db.connection import get_pool

logger = logging.getLogger("groundhog.db.suggestions")


def _row_to_dict(row) -> Dict[str, Any]:
    from datetime import datetime
    d = dict(row)
    for key in ("created_at",):
        if key in d and isinstance(d[key], datetime):
            d[key] = d[key].isoformat()
    if isinstance(d.get("payload"), str):
        try:
            d["payload"] = json.loads(d["payload"])
        except Exception:
            pass
    return d


async def save_suggestion(data: Dict[str, Any]) -> str:
    suggestion_id = str(uuid.uuid4())
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO agent_suggestions
                (id, run_id, experiment, agent_type, payload, severity, dismissed)
            VALUES ($1, $2, $3, $4, $5, $6, FALSE)
            """,
            suggestion_id,
            data.get("run_id"),
            data.get("experiment"),
            data.get("agent_type", "unknown"),
            json.dumps(data.get("payload", {})),
            data.get("severity"),
        )
    logger.info("Saved suggestion %s (type=%s)", suggestion_id, data.get("agent_type"))
    return suggestion_id


async def get_suggestions(
    experiment: Optional[str] = None,
    dismissed: bool = False,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    clauses = ["dismissed = $1"]
    args: list = [dismissed]
    if experiment:
        args.append(experiment)
        clauses.append(f"experiment = ${len(args)}")
    args.append(limit)

    where = "WHERE " + " AND ".join(clauses)
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM agent_suggestions {where} ORDER BY created_at DESC LIMIT ${len(args)}",
            *args,
        )
    return [_row_to_dict(r) for r in rows]


async def dismiss_suggestion(suggestion_id: str) -> None:
    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE agent_suggestions SET dismissed = TRUE WHERE id = $1",
            suggestion_id,
        )
    logger.info("Dismissed suggestion %s", suggestion_id)
