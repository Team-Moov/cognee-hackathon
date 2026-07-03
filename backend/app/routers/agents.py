from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app import cognee_client
from app.cognee_client import CogneeClientError

router = APIRouter(prefix="/agents", tags=["Agents"])
logger = logging.getLogger("groundhog.routers.agents")


@router.get("/suggestions")
async def list_suggestions(experiment: Optional[str] = None, dismissed: bool = False):
    """
    List agent suggestion cards. Dismissal state is persisted on the Cognee
    server's structured index (not an in-memory set), so it survives restart.
    Pass dismissed=true to include already-dismissed cards.
    """
    if not settings.cognee_api_url:
        return {"suggestions": [], "total": 0}

    try:
        result = await cognee_client.list_agent_suggestions(
            settings.cognee_api_url,
            experiment=experiment,
            include_dismissed=dismissed,
            timeout=settings.cognee_call_timeout_seconds,
        )
        suggestions = result.get("suggestions", []) if isinstance(result, dict) else []
        return {"suggestions": suggestions, "total": len(suggestions)}
    except CogneeClientError as e:
        logger.warning("suggestions: cognee unreachable: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/suggestions/{suggestion_id}/dismiss")
async def dismiss(suggestion_id: str):
    if not settings.cognee_api_url:
        raise HTTPException(status_code=503, detail="Cognee server is not configured")
    try:
        await cognee_client.dismiss_finding(
            settings.cognee_api_url,
            finding_id=suggestion_id,
            timeout=settings.cognee_call_timeout_seconds,
        )
        return {"status": "dismissed", "id": suggestion_id}
    except CogneeClientError as e:
        logger.warning("dismiss: cognee unreachable: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


class ReportRequest(BaseModel):
    experiment: str


@router.post("/report")
async def generate_report(req: ReportRequest):
    from app.agents.orchestrator import on_report_requested
    try:
        report_md = await on_report_requested(req.experiment)
        return {"experiment": req.experiment, "report": report_md}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
