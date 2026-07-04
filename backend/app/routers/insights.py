from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app import cognee_client, projects
from app.cognee_client import CogneeClientError

router = APIRouter(prefix="/insights", tags=["Insights"])
logger = logging.getLogger("groundhog.routers.insights")


@router.get("")
async def get_insights(project_id: Optional[str] = None):
    """Latest derived insights (parameter sensitivity, best-per-dataset) for a project."""
    if not settings.cognee_api_url:
        return {"n_runs": 0, "parameter_sensitivity": [], "best_per_dataset": [], "summary": "Cognee not configured."}
    try:
        return await cognee_client.get_insights(
            settings.cognee_api_url,
            project=projects.resolve_dataset(project_id) if project_id else None,
            timeout=settings.cognee_call_timeout_seconds,
        )
    except CogneeClientError as e:
        raise HTTPException(status_code=502, detail=str(e))


class GenerateRequest(BaseModel):
    project_id: Optional[str] = None


@router.post("/generate")
async def generate_insights(req: GenerateRequest):
    """Force-recompute insights for a project."""
    if not settings.cognee_api_url:
        raise HTTPException(status_code=503, detail="Cognee server is not configured")
    try:
        return await cognee_client.generate_insights(
            settings.cognee_api_url,
            project=projects.resolve_dataset(req.project_id),
            timeout=settings.cognee_call_timeout_seconds,
        )
    except CogneeClientError as e:
        raise HTTPException(status_code=502, detail=str(e))
