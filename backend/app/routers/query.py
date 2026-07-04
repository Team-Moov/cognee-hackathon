from __future__ import annotations

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config import settings
from app import cognee_client, projects
from app.cognee_client import CogneeClientError

router = APIRouter(tags=["Query"])
logger = logging.getLogger("groundhog.routers.query")


class QueryRequest(BaseModel):
    question: str
    mode: str = "COMPLETION"
    project_id: Optional[str] = None


@router.post("/query")
async def query(req: QueryRequest):
    """Free-form NL query backed by Cognee recall only."""
    if not settings.cognee_api_url:
        raise HTTPException(status_code=503, detail="Cognee server is not configured")

    try:
        cognee_result = await cognee_client.query(
            settings.cognee_api_url,
            question=req.question,
            dataset=projects.resolve_dataset(req.project_id) if req.project_id else None,
            timeout=settings.cognee_call_timeout_seconds,
        )
        return {
            "answer": cognee_result.get("answer", "No relevant information found."),
            "citations": cognee_result.get("sources", []),
            "chunks": [],
            "source": "cognee",
        }
    except CogneeClientError as e:
        logger.warning("query: cognee unreachable: %s", e)
        if not settings.cognee_fallback_on_error:
            raise HTTPException(status_code=502, detail=f"Cognee query failed: {e}")
        raise HTTPException(status_code=502, detail=str(e))
