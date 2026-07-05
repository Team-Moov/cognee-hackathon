from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import projects, cognee_client
from app.config import settings
from app.cognee_client import CogneeClientError

router = APIRouter(prefix="/projects", tags=["Projects"])
logger = logging.getLogger("groundhog.routers.projects")


class CreateProjectRequest(BaseModel):
    name: str = Field(..., description="Human-readable project name")
    wandb_entity: Optional[str] = Field(default=None, description="W&B entity/username")
    wandb_project: Optional[str] = Field(default=None, description="W&B project name")
    wandb_api_key: Optional[str] = Field(default=None, description="W&B API key (stored locally)")
    significant_keys: Optional[List[str]] = Field(
        default=None,
        description="Config keys that define an experiment (others treated as noise for the Pre-flight hash)",
    )


class SetWandbRequest(BaseModel):
    entity: Optional[str] = None
    project: Optional[str] = None
    api_key: Optional[str] = None
    default_dataset: Optional[str] = Field(
        default=None,
        description="Dataset name to attach to W&B-synced runs that don't log one in their config",
    )

class SetSyncRequest(BaseModel):
    enabled: bool


@router.post("")
async def create_project(req: CreateProjectRequest) -> Dict[str, Any]:
    proj = projects.create_project(
        name=req.name,
        wandb_entity=req.wandb_entity,
        wandb_project=req.wandb_project,
        wandb_api_key=req.wandb_api_key,
        significant_keys=req.significant_keys,
    )
    logger.info("created project %s (dataset=%s)", proj["project_id"], proj["dataset"])
    return proj


@router.get("")
async def list_projects() -> Dict[str, Any]:
    items = projects.list_projects()
    return {"projects": items, "total": len(items)}


@router.get("/{project_id}")
async def get_project(project_id: str) -> Dict[str, Any]:
    proj = projects.get_project(project_id)
    if not proj:
        raise HTTPException(status_code=404, detail=f"project not found: {project_id}")
    return proj


@router.delete("/{project_id}")
async def delete_project(project_id: str) -> Dict[str, Any]:
    """Delete a project: its registry entry AND all its runs/findings/insights + Cognee dataset."""
    dataset = projects.resolve_dataset(project_id)
    removed = projects.delete_project(project_id)
    data_stats = {}
    if settings.cognee_api_url:
        try:
            data_stats = await cognee_client.delete_project_data(
                settings.cognee_api_url, project=dataset,
                timeout=settings.cognee_call_timeout_seconds,
            )
        except CogneeClientError as e:
            logger.warning("delete project data failed: %s", e)
    if not removed:
        raise HTTPException(status_code=404, detail=f"project not found: {project_id}")
    return {"status": "deleted", "project_id": project_id, **data_stats}


@router.post("/{project_id}/wandb")
async def set_wandb(project_id: str, req: SetWandbRequest) -> Dict[str, Any]:
    proj = projects.set_wandb(project_id, entity=req.entity, project=req.project,
                              api_key=req.api_key, default_dataset=req.default_dataset)
    if not proj:
        raise HTTPException(status_code=404, detail=f"project not found: {project_id}")
    return proj

@router.put("/{project_id}/wandb/sync")
async def toggle_wandb_sync(project_id: str, req: SetSyncRequest) -> Dict[str, Any]:
    proj = projects.set_wandb_sync(project_id, enabled=req.enabled)
    if not proj:
        raise HTTPException(status_code=404, detail=f"project not found: {project_id}")
    return proj
