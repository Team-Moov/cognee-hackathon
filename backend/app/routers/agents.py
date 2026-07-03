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
_DISMISSED_SUGGESTIONS: set[str] = set()


@router.get("/suggestions")
async def list_suggestions(experiment: Optional[str] = None, dismissed: bool = False):
    if not settings.cognee_api_url:
        return {"suggestions": [], "total": 0}

    try:
        result = await cognee_client.list_agent_suggestions(
            settings.cognee_api_url,
            experiment=experiment,
            timeout=settings.cognee_call_timeout_seconds,
        )
        suggestions = result.get("suggestions", []) if isinstance(result, dict) else []
        if not dismissed:
            suggestions = [s for s in suggestions if str(s.get("id", "")) not in _DISMISSED_SUGGESTIONS]
        return {"suggestions": suggestions, "total": len(suggestions)}
    except CogneeClientError as e:
        logger.warning("suggestions: cognee unreachable: %s", e)
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/suggestions/{suggestion_id}/dismiss")
async def dismiss(suggestion_id: str):
    _DISMISSED_SUGGESTIONS.add(suggestion_id)
    return {"status": "dismissed", "id": suggestion_id}


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
