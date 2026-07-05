from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app import cognee_client, projects
from app.cognee_client import CogneeClientError
from app.utils import compute_config_hash

router = APIRouter(prefix="/runs", tags=["Runs"])
logger = logging.getLogger("groundhog.routers.runs")


class ArtifactIn(BaseModel):
    type: str
    path: str


class DatasetIn(BaseModel):
    name: Optional[str] = None
    version: Optional[str] = "v1"
    preprocessing: Optional[str] = ""
    split_rationale: Optional[str] = ""
    quality_issues: Optional[str] = ""


class RememberRequest(BaseModel):
    run_id: Optional[str] = None
    project_id: Optional[str] = Field(default=None, description="Project to scope this run to (isolates memory)")
    experiment: str = "unnamed"
    thread: str = "default"
    config: Dict[str, Any] = Field(default_factory=dict)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""
    git_commit: str = "unknown"
    gpu_hours: Optional[float] = None
    wall_clock_seconds: Optional[float] = None
    artifacts: List[ArtifactIn] = Field(default_factory=list)
    output_dir: Optional[str] = Field(default=None, description="Directory to scan for output files/artifacts")
    dataset: Optional[DatasetIn] = Field(default=None, description="Dataset used (name/version/preprocessing/split/quality)")
    hypothesis: Optional[str] = Field(default=None, description="What this run is testing")
    derived_from: Optional[str] = Field(default=None, description="config_hash/run_id this config was adapted from")
    status: str = "completed"
    error_message: Optional[str] = None


class CheckConfigRequest(BaseModel):
    config: Dict[str, Any]
    project_id: Optional[str] = None
    experiment: Optional[str] = None


@router.post("/remember")
async def remember(req: RememberRequest, background_tasks: BackgroundTasks):
    run_data = req.model_dump()
    dataset = projects.resolve_dataset(req.project_id)
    sig_keys = projects.significant_keys_for(req.project_id)
    run_data["project"] = dataset
    cognee_status = "skipped (no cognee_api_url configured)"
    stored_run_id = req.run_id or compute_config_hash(req.config, sig_keys)

    # Mirror the run into the project's W&B project (if creds are configured) in
    # the BACKGROUND. The W&B upload (wandb.init + finish) can take tens of
    # seconds, so awaiting it inline made every remember() block ~30s and could
    # time out a whole sweep. Fire-and-forget keeps run recording fast; the mirror
    # runs after the response and logs its own failures.
    wandb_status = {"pushed": "queued", "background": True}
    background_tasks.add_task(_mirror_to_wandb, req)

    if settings.cognee_api_url:
        try:
            result = await cognee_client.remember_run(
                settings.cognee_api_url,
                config=req.config,
                metrics=req.metrics,
                experiment=req.experiment,
                thread=req.thread,
                rationale=req.rationale,
                status=req.status,
                gpu_hours=req.gpu_hours,
                wall_clock_seconds=req.wall_clock_seconds,
                git_commit=req.git_commit,
                output_dir=req.output_dir,
                dataset=dataset,
                dataset_info=req.dataset.model_dump() if req.dataset else None,
                hypothesis=req.hypothesis,
                derived_from=req.derived_from,
                significant_keys=sig_keys,
                timeout=settings.cognee_call_timeout_seconds,
            )
            cognee_status = "ok"
            stored_run_id = result.get("node_id") or result.get("config_hash") or stored_run_id
            run_data["run_id"] = stored_run_id
            run_data["cognee_result"] = result
        except CogneeClientError as e:
            logger.warning("remember: cognee write failed: %s", e)
            cognee_status = f"failed: {e}"
            if not settings.cognee_fallback_on_error:
                raise HTTPException(status_code=502, detail=f"Cognee memory write failed: {e}")

    background_tasks.add_task(_orchestrate, run_data)

    return {
        "run_id": stored_run_id,
        "status": "ingested",
        "config_hash": compute_config_hash(req.config),
        "cognee_status": cognee_status,
        "wandb": wandb_status,
    }


async def _mirror_to_wandb(req: RememberRequest) -> Dict[str, Any]:
    """Push this run to the project's W&B project if it has W&B creds attached."""
    if not req.project_id:
        return {"pushed": False, "reason": "no project_id"}
    proj = projects.get_project(req.project_id, include_secrets=True)
    wb = (proj or {}).get("wandb") or {}
    if not wb.get("project"):
        return {"pushed": False, "reason": "project has no W&B project configured"}

    from app import wandb_push

    name = (req.run_id or req.experiment or "groundhog-run").strip()
    try:
        return await wandb_push.push_run_async(
            entity=wb.get("entity"),
            project=wb.get("project"),
            api_key=wb.get("api_key"),
            name=name,
            config=req.config,
            metrics=req.metrics,
            notes=req.rationale or "",
            tags=[t for t in [req.status, req.experiment] if t],
            status=req.status,
            group=req.experiment,
            job_type=req.thread,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("W&B mirror failed: %s", e)
        return {"pushed": False, "reason": str(e)}


@router.post("/check-config")
async def check_config(req: CheckConfigRequest):
    """Pre-flight guard backed by Cognee recall only."""
    if not settings.cognee_api_url:
        raise HTTPException(status_code=503, detail="Cognee server is not configured")

    try:
        cognee_result = await cognee_client.check_config(
            settings.cognee_api_url,
            config=req.config,
            dataset=projects.resolve_dataset(req.project_id),
            significant_keys=projects.significant_keys_for(req.project_id),
            timeout=settings.cognee_call_timeout_seconds,
        )
        if cognee_result.get("already_tried"):
            return {
                "already_tried": True,
                "matching_runs": [_cognee_result_to_summary(cognee_result)],
                "similarity_score": cognee_result.get("similarity_score") or 0.0,
                "match_type": cognee_result.get("match_type", "similar"),
                "recommendation": (
                    f"Cognee's memory graph found a prior match (match_type={cognee_result.get('match_type')}). "
                    "Review before proceeding."
                ),
                "source": "cognee",
            }
        return {
            "already_tried": False,
            "matching_runs": [],
            "similarity_score": 0.0,
            "match_type": "none",
            "recommendation": "No matching or similar config found in Cognee memory. Safe to run.",
            "source": "cognee",
        }
    except CogneeClientError as e:
        logger.warning("check-config: cognee unreachable: %s", e)
        if not settings.cognee_fallback_on_error:
            raise HTTPException(status_code=502, detail=f"Cognee memory check failed: {e}")
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/")
async def list_runs(experiment: Optional[str] = None, status: Optional[str] = None,
                    project_id: Optional[str] = None):
    if not settings.cognee_api_url:
        return {"runs": [], "total": 0}

    try:
        result = await cognee_client.list_runs(
            settings.cognee_api_url,
            experiment=experiment,
            status=status,
            project=projects.resolve_dataset(project_id) if project_id else None,
            timeout=settings.cognee_call_timeout_seconds,
        )
        runs = result.get("runs", []) if isinstance(result, dict) else []
        return {"runs": runs, "total": result.get("total", len(runs)) if isinstance(result, dict) else len(runs)}
    except CogneeClientError as e:
        logger.warning("list_runs: cognee query failed: %s", e)
        if not settings.cognee_fallback_on_error:
            raise HTTPException(status_code=502, detail=f"Cognee run listing failed: {e}")
        raise HTTPException(status_code=502, detail=str(e))


@router.delete("/{run_id}")
async def delete_run(run_id: str):
    if not settings.cognee_api_url:
        raise HTTPException(status_code=503, detail="Cognee server is not configured")
    try:
        return await cognee_client.delete_run(
            settings.cognee_api_url, run_id=run_id,
            timeout=settings.cognee_call_timeout_seconds,
        )
    except CogneeClientError as e:
        raise HTTPException(status_code=502, detail=str(e))


def _cognee_result_to_summary(cognee_result: Dict[str, Any]) -> Dict[str, Any]:
    prior = cognee_result.get("prior_result") or {}
    rationale = prior.get("rationale", prior.get("raw", ""))
    if isinstance(rationale, (dict, list)):
        rationale = json.dumps(rationale, default=str)
    metrics = prior.get("metrics", {})
    return {
        "run_id": prior.get("id") or prior.get("node_id") or "unknown",
        "date": prior.get("timestamp", ""),
        "metrics": metrics if isinstance(metrics, dict) else {},
        "config": prior.get("config", {}),
        "gpu_hours": prior.get("gpu_hours"),
        "status": prior.get("status", "completed"),
        "rationale": str(rationale),
    }


async def _orchestrate(run_data: Dict[str, Any]) -> None:
    try:
        from app.agents.orchestrator import on_run_remembered
        await on_run_remembered(run_data)
    except Exception as e:
        logger.error("Orchestrator error: %s", e)
