from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app import cognee_client
from app.cognee_client import CogneeClientError

router = APIRouter(prefix="/runs", tags=["Lineage"])
logger = logging.getLogger("groundhog.routers.lineage")


@router.get("/lineage/{run_id}")
async def get_lineage(run_id: str):
    if not settings.cognee_api_url:
        raise HTTPException(status_code=503, detail="Cognee server is not configured")

    try:
        result = await cognee_client.lineage(
            settings.cognee_api_url,
            run_id=run_id,
            timeout=settings.cognee_call_timeout_seconds,
        )
        lineage_text = result.get("lineage") or result.get("answer") or result.get("detail") or "No lineage found."
        return _synthesized_lineage(run_id, lineage_text)
    except CogneeClientError as e:
        logger.warning("lineage: cognee unreachable: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/lineage/{run_id}/ancestors")
async def lineage_ancestors(run_id: str, max_depth: int = Query(default=10, le=20)):
    if not settings.cognee_api_url:
        raise HTTPException(status_code=503, detail="Cognee server is not configured")
    try:
        result = await cognee_client.lineage(
            settings.cognee_api_url,
            run_id=run_id,
            timeout=settings.cognee_call_timeout_seconds,
        )
        lineage_text = result.get("lineage") or result.get("answer") or "No lineage found."
        return {
            "run_id": run_id,
            "direction": "ancestors",
            "nodes": [_text_node(run_id, lineage_text, kind="ancestor_summary")],
            "max_depth": max_depth,
        }
    except CogneeClientError as e:
        logger.warning("lineage ancestors: cognee unreachable: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/lineage/{run_id}/descendants")
async def lineage_descendants(run_id: str, max_depth: int = Query(default=10, le=20)):
    if not settings.cognee_api_url:
        raise HTTPException(status_code=503, detail="Cognee server is not configured")
    try:
        result = await cognee_client.lineage(
            settings.cognee_api_url,
            run_id=run_id,
            timeout=settings.cognee_call_timeout_seconds,
        )
        lineage_text = result.get("lineage") or result.get("answer") or "No lineage found."
        return {
            "run_id": run_id,
            "direction": "descendants",
            "nodes": [_text_node(run_id, lineage_text, kind="descendant_summary")],
            "max_depth": max_depth,
        }
    except CogneeClientError as e:
        logger.warning("lineage descendants: cognee unreachable: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


def _synthesized_lineage(run_id: str, lineage_text: str):
    return {
        "run_id": run_id,
        "nodes": [
            {
                "id": f"cfg-{run_id}",
                "type": "config",
                "data": {
                    "run_id": run_id,
                    "description": f"Cognee lineage lookup for {run_id}",
                },
            },
            {
                "id": f"res-{run_id}",
                "type": "result",
                "data": {
                    "run_id": run_id,
                    "status": "completed",
                    "rationale": lineage_text,
                },
            },
        ],
        "edges": [{"source": f"cfg-{run_id}", "target": f"res-{run_id}", "type": "produced"}],
    }


def _text_node(run_id: str, lineage_text: str, kind: str):
    return {
        "id": f"{kind}-{run_id}",
        "type": "artifact",
        "data": {
            "run_id": run_id,
            "statement": lineage_text,
        },
    }
