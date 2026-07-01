from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.db.lineage import get_lineage as db_get_lineage, get_ancestors, get_descendants
from app.db.runs import get_run

router = APIRouter(prefix="/runs", tags=["Lineage"])


@router.get("/lineage/{run_id}")
async def get_lineage(run_id: str):
    lineage = await db_get_lineage(run_id)
    if lineage:
        return lineage

    # Synthesize minimal lineage from the run row
    run = await get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"No lineage or run found for: {run_id}")

    return {
        "run_id": run_id,
        "nodes": [
            {"id": f"cfg-{run_id}", "type": "config",
             "data": {**run.get("config", {}), "run_id": run_id}},
            {"id": f"res-{run_id}", "type": "result",
             "data": {"metrics": run.get("metrics", {}), "status": run.get("status"),
                      "gpu_hours": run.get("gpu_hours"), "run_id": run_id}},
        ],
        "edges": [{"source": f"cfg-{run_id}", "target": f"res-{run_id}", "type": "produced"}],
    }


@router.get("/lineage/{run_id}/ancestors")
async def lineage_ancestors(run_id: str, max_depth: int = Query(default=10, le=20)):
    """Recursive CTE graph walk UP the DAG — all runs this run was derived from."""
    rows = await get_ancestors(run_id, max_depth=max_depth)
    return {"run_id": run_id, "direction": "ancestors", "nodes": rows}


@router.get("/lineage/{run_id}/descendants")
async def lineage_descendants(run_id: str, max_depth: int = Query(default=10, le=20)):
    """Recursive CTE graph walk DOWN the DAG — all runs derived from this one."""
    rows = await get_descendants(run_id, max_depth=max_depth)
    return {"run_id": run_id, "direction": "descendants", "nodes": rows}
