"""
projects.py — Local project registry (the "front door").

A Project is what a researcher creates in the UI to get a `project_id`. That id
is then pasted into their notebook / .py repo (via the groundhog SDK) or used to
bind a W&B project, so everything they do is recorded under one isolated memory.

Design:
  - project_id maps 1:1 to a Cognee `dataset_name`, which is how Cognee isolates
    memory. So "create a project" == "reserve a dataset". No new storage engine.
  - Everything is LOCAL. This registry is a JSON file on disk; W&B credentials
    live in the same local file (single-user local box — no cloud, no vault).
  - A per-project token is issued for the SDK to authenticate writes. Locally
    it's mostly a routing handle; it becomes a real secret if this is ever
    deployed for multiple users.

This is a thin registry only — the actual memory still lives in Cognee via the
existing /remember, /check-config, /query paths, now scoped by dataset=project_id.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

_LOCK = threading.RLock()

_STORE_PATH = os.getenv(
    "GROUNDHOG_PROJECTS_FILE",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "groundhog_projects.json"),
)
_STORE_PATH = os.path.abspath(_STORE_PATH)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    text = (text or "project").strip().lower()
    return _SLUG_RE.sub("_", text).strip("_") or "project"


def _load() -> Dict[str, Any]:
    if not os.path.exists(_STORE_PATH):
        return {"projects": []}
    try:
        with open(_STORE_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        data.setdefault("projects", [])
        return data
    except (OSError, json.JSONDecodeError):
        return {"projects": []}


def _save(data: Dict[str, Any]) -> None:
    tmp = _STORE_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)
    os.replace(tmp, _STORE_PATH)


def _public(project: Dict[str, Any], include_secrets: bool = False) -> Dict[str, Any]:
    """Project view for API responses. Hides the W&B API key unless asked."""
    out = {
        "project_id": project["project_id"],
        "name": project.get("name"),
        "dataset": project["dataset"],
        "created_at": project.get("created_at"),
        "significant_keys": project.get("significant_keys") or [],
        "wandb": {
            "entity": (project.get("wandb") or {}).get("entity"),
            "project": (project.get("wandb") or {}).get("project"),
            "configured": bool((project.get("wandb") or {}).get("api_key")),
            "last_synced_run": (project.get("wandb") or {}).get("last_synced_run"),
        },
        "token": project.get("token"),
    }
    if include_secrets:
        out["wandb"]["api_key"] = (project.get("wandb") or {}).get("api_key")
    return out


def create_project(
    name: str,
    wandb_entity: Optional[str] = None,
    wandb_project: Optional[str] = None,
    wandb_api_key: Optional[str] = None,
    significant_keys: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Create a project, returning its public view (with project_id + token)."""
    project_id = f"proj_{_slug(name)}_{uuid.uuid4().hex[:8]}"
    project = {
        "project_id": project_id,
        "name": name,
        "dataset": project_id,  # project_id IS the Cognee dataset name
        "token": secrets.token_urlsafe(24),
        "created_at": datetime.utcnow().isoformat(),
        "significant_keys": significant_keys or [],
        "wandb": {
            "entity": wandb_entity,
            "project": wandb_project,
            "api_key": wandb_api_key,
            "last_synced_run": None,
        },
    }
    with _LOCK:
        data = _load()
        data["projects"].append(project)
        _save(data)
    return _public(project, include_secrets=False)


def list_projects() -> List[Dict[str, Any]]:
    with _LOCK:
        data = _load()
    return [_public(p) for p in data["projects"]]


def get_project(project_id: str, include_secrets: bool = False) -> Optional[Dict[str, Any]]:
    with _LOCK:
        data = _load()
    for p in data["projects"]:
        if p["project_id"] == project_id:
            return _public(p, include_secrets=include_secrets)
    return None


def _get_raw(project_id: str) -> Optional[Dict[str, Any]]:
    data = _load()
    for p in data["projects"]:
        if p["project_id"] == project_id:
            return p
    return None


def set_wandb(project_id: str, *, entity: Optional[str] = None, project: Optional[str] = None,
              api_key: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Attach/update W&B credentials on a project (stored locally)."""
    with _LOCK:
        data = _load()
        for p in data["projects"]:
            if p["project_id"] == project_id:
                wb = p.setdefault("wandb", {})
                if entity is not None:
                    wb["entity"] = entity
                if project is not None:
                    wb["project"] = project
                if api_key is not None:
                    wb["api_key"] = api_key
                _save(data)
                return _public(p)
    return None


def update_synced_run(project_id: str, run_id: str) -> None:
    """Record the last W&B run ingested (incremental-sync watermark)."""
    with _LOCK:
        data = _load()
        for p in data["projects"]:
            if p["project_id"] == project_id:
                p.setdefault("wandb", {})["last_synced_run"] = run_id
                _save(data)
                return


def resolve_dataset(project_id: Optional[str]) -> str:
    """
    Map a project_id to its Cognee dataset. Unknown/None falls back to
    'main_dataset' so pre-project callers keep working.
    """
    if not project_id:
        return "main_dataset"
    proj = _get_raw(project_id)
    return proj["dataset"] if proj else project_id


def significant_keys_for(project_id: Optional[str]) -> Optional[List[str]]:
    if not project_id:
        return None
    proj = _get_raw(project_id)
    keys = (proj or {}).get("significant_keys") or []
    return keys or None
