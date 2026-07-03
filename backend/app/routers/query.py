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
        }
    except Exception as e:
        logger.error("Query LLM failed: %s", e)
        raise HTTPException(status_code=500, detail=f"LLM error: {e}")
