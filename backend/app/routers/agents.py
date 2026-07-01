from __future__ import annotations

from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.suggestions import get_suggestions, save_suggestion, dismiss_suggestion

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.get("/suggestions")
async def list_suggestions(experiment: Optional[str] = None, dismissed: bool = False):
    suggestions = await get_suggestions(experiment=experiment, dismissed=dismissed)
    return {"suggestions": suggestions, "total": len(suggestions)}


@router.post("/suggestions/{suggestion_id}/dismiss")
async def dismiss(suggestion_id: str):
    await dismiss_suggestion(suggestion_id)
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
