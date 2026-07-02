"""
PostgreSQL lineage storage:
  - lineage_graphs  — stores the full nodes/edges JSON blob per run
  - run_lineage     — directed adjacency table for recursive CTE graph traversal
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.db.connection import get_pool

logger = logging.getLogger("groundhog.db.lineage")


async def save_lineage(run_id: str, nodes: list, edges: list) -> None:
    """
    Persist nodes/edges JSON and also populate the run_lineage adjacency table
    from any edges whose source and target look like run IDs.
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # 1. Upsert the JSON blob
            await conn.execute(
                """
                INSERT INTO lineage_graphs (run_id, nodes, edges, updated_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (run_id) DO UPDATE
                    SET nodes = EXCLUDED.nodes,
                        edges = EXCLUDED.edges,
                        updated_at = NOW()
                """,
                run_id,
                json.dumps(nodes),
                json.dumps(edges),
            )

            # 2. Derive adjacency rows from edges where both endpoints are run nodes
            run_node_ids = {n["id"] for n in nodes if n.get("type") == "config"}
            for edge in edges:
                src = edge.get("source", "")
                tgt = edge.get("target", "")
                # Extract run_id from node ids like "cfg-run123"
                p = src.removeprefix("cfg-")
                c = tgt.removeprefix("cfg-").removeprefix("res-")
                if p and c and p != c:
                    # Best-effort: ignore FK violations if run row doesn't exist yet
                    try:
                        await conn.execute(
                            """
                            INSERT INTO run_lineage (parent_run_id, child_run_id, edge_type)
                            VALUES ($1, $2, $3)
                            ON CONFLICT DO NOTHING
                            """,
                            p, c, edge.get("type", "derived_from"),
                        )
                    except Exception:
                        pass

    logger.info("Saved lineage for %s (%d nodes, %d edges)", run_id, len(nodes), len(edges))


async def get_lineage(run_id: str) -> Optional[Dict[str, Any]]:
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT run_id, nodes, edges FROM lineage_graphs WHERE run_id = $1",
            run_id,
        )
    if not row:
        return None
    return {
        "run_id": row["run_id"],
        "nodes": json.loads(row["nodes"]) if isinstance(row["nodes"], str) else row["nodes"],
        "edges": json.loads(row["edges"]) if isinstance(row["edges"], str) else row["edges"],
    }


async def get_ancestors(run_id: str, max_depth: int = 10) -> List[Dict[str, Any]]:
    """
    Recursive CTE: walk UP the lineage DAG from run_id.
    Returns all ancestor run rows (including the start node at depth 0).
    """
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH RECURSIVE ancestors AS (
                SELECT id, experiment, status, metrics, config, rationale,
                       created_at, 0 AS depth
                FROM runs WHERE id = $1
                UNION ALL
              SELECT parent.id, parent.experiment, parent.status, parent.metrics, parent.config, parent.rationale,
                  parent.created_at, a.depth + 1
              FROM ancestors a
              JOIN run_lineage l ON l.child_run_id = a.id
              JOIN runs parent   ON parent.id = l.parent_run_id
                WHERE a.depth < $2
            )
            SELECT * FROM ancestors ORDER BY depth
            """,
            run_id,
            max_depth,
        )
    return [dict(r) for r in rows]


async def get_descendants(run_id: str, max_depth: int = 10) -> List[Dict[str, Any]]:
    """Recursive CTE: walk DOWN the lineage DAG from run_id."""
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            WITH RECURSIVE descendants AS (
                SELECT id, experiment, status, metrics, config, rationale,
                       created_at, 0 AS depth
                FROM runs WHERE id = $1
                UNION ALL
              SELECT child.id, child.experiment, child.status, child.metrics, child.config, child.rationale,
                  child.created_at, d.depth + 1
              FROM descendants d
              JOIN run_lineage l ON l.parent_run_id = d.id
              JOIN runs child    ON child.id = l.child_run_id
                WHERE d.depth < $2
            )
            SELECT * FROM descendants ORDER BY depth
            """,
            run_id,
            max_depth,
        )
    return [dict(r) for r in rows]
