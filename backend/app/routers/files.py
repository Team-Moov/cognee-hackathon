from __future__ import annotations

import logging
from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app import cognee_client
from app.cognee_client import CogneeClientError

router = APIRouter(prefix="/files", tags=["Files"])
logger = logging.getLogger("groundhog.routers.files")


@router.get("/find")
async def find_file(q: str = Query(..., description="Natural language description of the artifact")):
    if not settings.cognee_api_url:
        raise HTTPException(status_code=503, detail="Cognee server is not configured")
    try:
        result = await cognee_client.find_file(
            settings.cognee_api_url,
            description=q,
            timeout=settings.cognee_call_timeout_seconds,
        )
        return {
            "path": result.get("file_path", result.get("path", "")),
            "run_id": result.get("artifact_id", result.get("run_id", "")),
            "artifact_type": result.get("artifact_type", "other"),
            "exists_on_disk": result.get("exists_on_disk", False),
        }
    except CogneeClientError as e:
        logger.warning("find_file: cognee unreachable: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/orphans")
async def get_orphans():
    if not settings.cognee_api_url:
        raise HTTPException(status_code=503, detail="Cognee server is not configured")
    try:
        result = await cognee_client.get_orphans(
            settings.cognee_api_url,
            timeout=settings.cognee_call_timeout_seconds,
        )
        return {
            "untracked_files": [item.get("file_path", item) for item in result.get("untracked_files", [])],
            "broken_nodes": [
                {"missing_path": item.get("file_path", ""), "run_id": item.get("result_id", "")}
                for item in result.get("broken_references", [])
            ],
            "untracked_size_gb": result.get("untracked_size_gb", 0),
        }
    except CogneeClientError as e:
        logger.warning("orphans: cognee unreachable: %s", e)
        raise HTTPException(status_code=502, detail=str(e))
