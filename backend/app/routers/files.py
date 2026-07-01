from __future__ import annotations

import os
from fastapi import APIRouter, HTTPException, Query

from app.db.runs import get_all_runs

router = APIRouter(prefix="/files", tags=["Files"])


@router.get("/find")
async def find_file(q: str = Query(..., description="Natural language description of the artifact")):
    """Locate a run artifact by text description (keyword match against paths)."""
    runs = await get_all_runs(limit=200)
    q_lower = q.lower()
    tokens = [t for t in q_lower.split() if len(t) > 2]

    for run in runs:
        for art in run.get("artifacts", []):
            path = art.get("path", "").lower()
            atype = art.get("type", "").lower()
            if any(t in path or t in atype for t in tokens):
                full_path = art.get("path", "")
                return {
                    "path": full_path,
                    "run_id": run.get("run_id"),
                    "artifact_type": art.get("type"),
                    "exists_on_disk": os.path.exists(full_path),
                }

    raise HTTPException(status_code=404, detail=f"No artifact matching: {q}")


@router.get("/orphans")
async def get_orphans():
    """Find untracked files on disk and broken artifact references."""
    runs = await get_all_runs(limit=200)
    known_paths = set()
    broken = []

    for run in runs:
        for art in run.get("artifacts", []):
            path = art.get("path", "")
            if path:
                known_paths.add(path)
                if not os.path.exists(path):
                    broken.append({
                        "run_id": run.get("run_id"),
                        "missing_path": path,
                    })

    artifact_root = os.path.abspath(os.getenv("ARTIFACT_ROOT_DIR", "./runs"))
    untracked = []
    total_bytes = 0
    if os.path.isdir(artifact_root):
        for dirpath, _, filenames in os.walk(artifact_root):
            for fname in filenames:
                fpath = os.path.abspath(os.path.join(dirpath, fname))
                if fpath not in known_paths:
                    size = 0
                    try:
                        size = os.path.getsize(fpath)
                    except OSError:
                        pass
                    total_bytes += size
                    untracked.append(fpath)

    return {
        "untracked_files": untracked,
        "broken_nodes": broken,
        "untracked_size_gb": round(total_bytes / 1e9, 3),
    }
