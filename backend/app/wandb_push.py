"""
wandb_push.py — write a Groundhog run *back* into its project's W&B project.

The rest of the system pulls runs FROM W&B (connectors/wandb_sync.py). This is the
one place that goes the other way: when a run is logged through the app (the
dashboard "Log run" form or the SDK), and the Groundhog project has W&B
credentials attached, we mirror it into W&B so it shows up under
`entity/project` just like a real training run.

Windows note: wandb's default "service" subprocess hangs on some Windows setups
(it never returns from wandb.init). We disable it here (WANDB_*_DISABLE_SERVICE)
and bound init with a timeout so a flaky network can't wedge a request.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("groundhog.wandb_push")

# W&B run.state -> what exit_code / behaviour to use on finish().
_FAILED_STATES = {"failed", "aborted", "crashed", "killed"}


def _coerce_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """Keep only things W&B can chart: scalars (and bools as 0/1)."""
    clean: Dict[str, Any] = {}
    for k, v in (metrics or {}).items():
        if isinstance(v, bool):
            clean[k] = int(v)
        elif isinstance(v, (int, float)):
            clean[k] = v
    return clean


def push_run(
    *,
    entity: Optional[str],
    project: str,
    api_key: Optional[str],
    name: Optional[str] = None,
    config: Optional[Dict[str, Any]] = None,
    metrics: Optional[Dict[str, Any]] = None,
    notes: str = "",
    tags: Optional[List[str]] = None,
    status: str = "completed",
    group: Optional[str] = None,
    job_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Synchronously create + finish one W&B run. Never raises — returns a status
    dict so the caller can surface it without failing the whole request.
    """
    if not project:
        return {"pushed": False, "reason": "no W&B project configured"}

    # Disable the service subprocess (hangs on Windows) before importing wandb.
    os.environ.setdefault("WANDB_X_DISABLE_SERVICE", "true")
    os.environ.setdefault("WANDB_DISABLE_SERVICE", "true")
    os.environ.setdefault("WANDB_SILENT", "true")
    os.environ.setdefault("WANDB_CONSOLE", "off")
    if api_key:
        os.environ["WANDB_API_KEY"] = api_key

    try:
        import wandb
    except ImportError:
        return {"pushed": False, "reason": "wandb not installed"}

    # Tag every app-mirrored run so the W&B->app sync loop can recognise and SKIP
    # its own echoes — otherwise a project with both mirroring and auto-sync
    # enabled forms a feedback loop that re-ingests these as duplicate runs.
    GROUNDHOG_ORIGIN_TAG = "groundhog-origin"
    all_tags = list(dict.fromkeys([*(tags or []), GROUNDHOG_ORIGIN_TAG]))

    try:
        run = wandb.init(
            entity=entity or None,
            project=project,
            name=name or None,
            notes=notes or "",
            tags=all_tags,
            group=group or None,
            job_type=job_type or None,
            config=config or {},
            reinit=True,
            settings=wandb.Settings(silent=True, console="off", init_timeout=45),
        )
        clean_metrics = _coerce_metrics(metrics or {})
        if clean_metrics:
            run.log(clean_metrics)
        run_id = run.id
        run_url = run.url
        run.finish(exit_code=1 if status.lower() in _FAILED_STATES else 0)
        logger.info("pushed run %s to W&B %s/%s", run_id, entity, project)
        return {
            "pushed": True,
            "wandb_id": run_id,
            "url": run_url,
            "entity": entity,
            "project": project,
        }
    except Exception as e:  # noqa: BLE001 — never let a W&B hiccup fail the caller
        logger.warning("W&B push failed: %s", e)
        return {"pushed": False, "reason": str(e)}


async def push_run_async(**kwargs: Any) -> Dict[str, Any]:
    """Run the blocking push off the event loop so it can't stall the server."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, lambda: push_run(**kwargs))
