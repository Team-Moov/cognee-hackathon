"""
Hybrid RAG query endpoint:
    1. Embed the question with the local deterministic embedding path
  2. HNSW cosine ANN search (pgvector) → top semantic hits
  3. tsvector GIN full-text search → top keyword hits
  4. Merge + deduplicate → pass to Groq as context
"""
from __future__ import annotations

import json
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.runs import fulltext_search, get_all_runs
from app.utils import llm_generate
from app.config import settings
from app import cognee_client
from app.cognee_client import CogneeClientError

router = APIRouter(tags=["Query"])
logger = logging.getLogger("groundhog.routers.query")

SYSTEM_PROMPT = """You are Groundhog, an AI assistant with deep memory of all ML experiments.
Answer questions about experiment history with concrete metric values, config params, and run IDs.
Failures and negative results are first-class memory — surface them when relevant.
Format in clear markdown. Cite runs inline as [run-id]."""


class QueryRequest(BaseModel):
    question: str
    mode: str = "COMPLETION"


@router.post("/query")
async def query(req: QueryRequest):
    """
    Free-form NL query.

    Primary path: cognee.recall() via the cognee-backed memory server — real
    graph-aware retrieval (auto-routed SearchType) across every connector's
    data, not just what this backend's Postgres table has cached.

    Fallback: Postgres full-text search + Groq completion over the retrieved
    rows, used only if the cognee server is unreachable (or disabled in
    config), so the query bar keeps working during local dev without the
    cognee process running.
    """
    if settings.cognee_api_url:
        try:
            cognee_result = await cognee_client.query(
                settings.cognee_api_url, question=req.question,
                timeout=settings.cognee_call_timeout_seconds,
            )
            return {
                "answer": cognee_result.get("answer", "No relevant information found."),
                "citations": cognee_result.get("sources", []),
                "chunks": [],
                "source": "cognee",
            }
        except CogneeClientError as e:
            logger.warning("query: cognee unreachable, falling back to Postgres full-text: %s", e)
            if not settings.cognee_fallback_on_error:
                raise HTTPException(status_code=502, detail=f"Cognee query failed: {e}")

    # NOTE: pgvector/HNSW semantic search is disabled until the embedding
    # column is added to the DB. Full-text + recent-runs fallback covers all
    # demo queries for the hackathon.
    seen: dict[str, dict] = {}
    try:
        ft_hits = await fulltext_search(req.question, limit=15)
        for r in ft_hits:
            if r["run_id"] not in seen:
                seen[r["run_id"]] = r
        logger.debug("Full-text search: %d hits", len(ft_hits))
    except Exception as e:
        logger.warning("Full-text search failed: %s", e)

    # 3. If still nothing, fall back to most-recent runs
    if not seen:
        recent = await get_all_runs(limit=20)
        for r in recent:
            seen[r["run_id"]] = r

    if not seen:
        return {
            "answer": "No experiments recorded yet. Use POST /api/runs/remember to add a run.",
            "citations": [],
            "chunks": [],
        }

    runs = list(seen.values())[:20]  # cap context size
    runs_context = json.dumps(
        [
            {
                "run_id":     r.get("run_id"),
                "experiment": r.get("experiment"),
                "config":     r.get("config", {}),
                "metrics":    r.get("metrics", {}),
                "status":     r.get("status"),
                "rationale":  r.get("rationale", ""),
                "gpu_hours":  r.get("gpu_hours"),
                "timestamp":  r.get("timestamp", ""),
                "similarity": r.get("similarity"),
                "text_rank":  r.get("text_rank"),
            }
            for r in runs
        ],
        indent=2,
    )

    prompt = f"""{SYSTEM_PROMPT}

Retrieved experiment context ({len(runs)} runs, ranked by relevance):
{runs_context}

Question: {req.question}

Answer:"""

    try:
        answer = await llm_generate(prompt)
        citations = [r["run_id"] for r in runs if r.get("run_id", "") in answer]
        return {
            "answer": answer.strip(),
            "citations": citations,
            "chunks": [{"run_id": r["run_id"], "score": r.get("similarity", r.get("text_rank", 0))} for r in runs],
            "source": "postgres_fallback",
        }
    except Exception as e:
        logger.error("Query LLM failed: %s", e)
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")
