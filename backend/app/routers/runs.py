from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.db.runs import save_run, get_run, get_all_runs, find_by_config_hash
from app.utils import compute_config_hash, config_similarity
from app.config import settings
from app import cognee_client
from app.cognee_client import CogneeClientError

router = APIRouter(prefix="/runs", tags=["Runs"])
logger = logging.getLogger("groundhog.routers.runs")


class ArtifactIn(BaseModel):
    type: str
    path: str


class RememberRequest(BaseModel):
    run_id: Optional[str] = None
    experiment: str = "unnamed"
    config: Dict[str, Any] = {}
    metrics: Dict[str, Any] = {}
    rationale: str = ""
    git_commit: str = "unknown"
    gpu_hours: Optional[float] = None
    artifacts: List[ArtifactIn] = []
    status: str = "completed"
    error_message: Optional[str] = None


class CheckConfigRequest(BaseModel):
    config: Dict[str, Any]
    experiment: Optional[str] = None


@router.post("/remember")
async def remember(req: RememberRequest, background_tasks: BackgroundTasks):
    run_data = req.model_dump()
    run_id = await save_run(run_data)

    # Build lineage node/edge snapshot and persist
    from app.db.lineage import save_lineage
    await save_lineage(
        run_id,
        nodes=[
            {"id": f"cfg-{run_id}", "type": "config",
             "data": {**req.config, "run_id": run_id}},
            {"id": f"res-{run_id}", "type": "result",
             "data": {"metrics": req.metrics, "status": req.status,
                      "gpu_hours": req.gpu_hours, "run_id": run_id}},
        ],
        edges=[{"source": f"cfg-{run_id}", "target": f"res-{run_id}", "type": "produced"}],
    )

    # Real memory write: cognee.remember() via the cognee-backed memory server.
    # Postgres above is a fast local cache for lineage/listing/agents — this is
    # the actual "Best Use of Cognee" write path. A cognee failure never loses
    # the run (it's already in Postgres); it's surfaced via cognee_status.
    cognee_status = "skipped (no cognee_api_url configured)"
    if settings.cognee_api_url:
        try:
            await cognee_client.remember_run(
                settings.cognee_api_url,
                config=req.config,
                metrics=req.metrics,
                experiment=req.experiment,
                rationale=req.rationale,
                status=req.status,
                gpu_hours=req.gpu_hours,
                git_commit=req.git_commit,
                timeout=settings.cognee_call_timeout_seconds,
            )
            cognee_status = "ok"
        except CogneeClientError as e:
            logger.warning("remember: cognee write failed (Postgres write already succeeded): %s", e)
            cognee_status = f"failed: {e}"
            if not settings.cognee_fallback_on_error:
                raise HTTPException(status_code=502, detail=f"Cognee memory write failed: {e}")

    # Fan out to subagents in background (non-blocking)
    saved = await get_run(run_id)
    background_tasks.add_task(_orchestrate, saved or run_data)

    return {
        "run_id": run_id,
        "status": "ingested",
        "config_hash": compute_config_hash(req.config),
        "cognee_status": cognee_status,
    }


@router.post("/check-config")
async def check_config(req: CheckConfigRequest):
    """
    Pre-flight Guard.

    Two sources are checked, because they cover different scopes:
      1. Postgres exact-hash match — fast, but only knows about runs THIS
         backend has ingested via /remember.
      2. cognee.recall() via the cognee-backed memory server — the
         cross-connector memory graph, which also includes runs written by
         the W&B bridge, the Jupyter magic, the file watcher, or an MCP
         client (Claude Code), none of which necessarily touch this Postgres
         table directly.
    """
    incoming_hash = compute_config_hash(req.config)

    # 1. Exact hash match — local Postgres cache (fast path)
    exact_matches = await find_by_config_hash(incoming_hash)
    if exact_matches:
        run = exact_matches[0]
        return {
            "already_tried": True,
            "matching_runs": [_run_summary(run)],
            "similarity_score": 1.0,
            "match_type": "exact",
            "recommendation": (
                f"This exact config was already run on {run.get('timestamp','')[:10]} "
                f"({run.get('gpu_hours','?')} GPU-hours). "
                + (_metric_line(run)) + " Skip to save compute."
            ),
            "source": "postgres",
        }

    # 2. cognee's memory graph — catches matches from other connectors that
    #    never wrote into this backend's Postgres table.
    if settings.cognee_api_url:
        try:
            cognee_result = await cognee_client.check_config(
                settings.cognee_api_url, config=req.config,
                timeout=settings.cognee_call_timeout_seconds,
            )
            if cognee_result.get("already_tried"):
                return {
                    "already_tried": True,
                    "matching_runs": [_cognee_result_to_summary(cognee_result)],
                    "similarity_score": cognee_result.get("similarity_score") or 0.0,
                    "match_type": cognee_result.get("match_type", "similar"),
                    "recommendation": (
                        f"Cognee's memory graph found a prior match "
                        f"(match_type={cognee_result.get('match_type')}). "
                        "Review before proceeding."
                    ),
                    "source": "cognee",
                }
        except CogneeClientError as e:
            logger.warning("check-config: cognee unreachable, using Postgres-only similarity: %s", e)
            if not settings.cognee_fallback_on_error:
                raise HTTPException(status_code=502, detail=f"Cognee memory check failed: {e}")

    # 3. Similarity fallback over locally-cached runs
    all_runs = await get_all_runs(
        experiment=req.experiment if req.experiment else None, limit=100
    )
    best_score, best_run = 0.0, None
    for run in all_runs:
        score = config_similarity(req.config, run.get("config", {}))
        if score > best_score:
            best_score, best_run = score, run

    if best_run and best_score >= 0.5:
        return {
            "already_tried": False,
            "matching_runs": [_run_summary(best_run)],
            "similarity_score": round(best_score, 3),
            "match_type": "similar",
            "recommendation": (
                f"Similar config found ({best_score:.0%} match): "
                f"run {best_run['run_id']} on {best_run.get('timestamp','')[:10]}. "
                "Review differences before proceeding."
            ),
            "source": "postgres",
        }

    return {
        "already_tried": False,
        "matching_runs": [],
        "similarity_score": 0.0,
        "match_type": "none",
        "recommendation": "No matching or similar config found. Safe to run.",
        "source": "none",
    }


def _cognee_result_to_summary(cognee_result: Dict[str, Any]) -> Dict[str, Any]:
    """Adapt memory.check_config()'s prior_result shape to the frontend's run-summary shape."""
    prior = cognee_result.get("prior_result") or {}
    return {
        "run_id": prior.get("id") or prior.get("node_id") or "unknown",
        "date": prior.get("timestamp", ""),
        "metrics": prior.get("metrics", {}),
        "config": prior.get("config", {}),
        "gpu_hours": prior.get("gpu_hours"),
        "status": prior.get("status", "completed"),
        "rationale": prior.get("rationale", prior.get("raw", "")),
    }


@router.get("/")
async def list_runs(experiment: Optional[str] = None, status: Optional[str] = None):
    runs = await get_all_runs(experiment=experiment, status=status)
    return {"runs": runs, "total": len(runs)}


# ── helpers ────────────────────────────────────────────────────────────────

def _run_summary(run: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "run_id": run.get("run_id"),
        "date": run.get("timestamp", ""),
        "metrics": run.get("metrics", {}),
        "config": run.get("config", {}),
        "gpu_hours": run.get("gpu_hours"),
        "status": run.get("status"),
        "rationale": run.get("rationale", ""),
    }


def _metric_line(run: Dict[str, Any]) -> str:
    m = run.get("metrics", {})
    if m.get("val_acc") is not None:
        return f"Result: val_acc={m['val_acc']:.4f}."
    if m.get("perplexity") is not None:
        return f"Result: perplexity={m['perplexity']:.2f}."
    return f"Status: {run.get('status', '?')}."


async def _orchestrate(run_data: Dict[str, Any]) -> None:
    try:
        from app.agents.orchestrator import on_run_remembered
        await on_run_remembered(run_data)
    except Exception as e:
        import logging
        logging.getLogger("groundhog.runs").error("Orchestrator error: %s", e)
