from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import projects

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


@router.post("/{project_id}/wandb")
async def set_wandb(project_id: str, req: SetWandbRequest) -> Dict[str, Any]:
    proj = projects.set_wandb(project_id, entity=req.entity, project=req.project, api_key=req.api_key)
    if not proj:
        raise HTTPException(status_code=404, detail=f"project not found: {project_id}")
    return proj
