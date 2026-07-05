"""
wandb_sync.py — automatic W&B → Groundhog sync (daemon).

Replaces the old two-step "edit the hardcoded project, run the bridge, then run
the flush script" flow with a single, configurable, incremental sync that can
run once or watch continuously.

Key improvements over connectors/wandb_bridge.py:
  - **No hardcoded project** — entity/project come from a Groundhog project's
    stored W&B credentials (server-side/local, set at project creation), or from
    CLI flags / env vars.
  - **Incremental** — a per-project watermark means only runs newer than the last
    sync are ingested (no re-cognifying everything each time).
  - **Scoped** — each run is POSTed to the backend with the Groundhog project_id,
    so it lands in that project's isolated memory and triggers the subagents.
  - **--watch** — poll W&B on an interval so "runs finish, memory fills itself".

Usage:
    # one-shot, creds pulled from the Groundhog project
    python connectors/wandb_sync.py --project-id proj_xyz --once

    # continuous, poll every 60s
    python connectors/wandb_sync.py --project-id proj_xyz --interval 60

    # creds supplied directly (no Groundhog project lookup)
    python connectors/wandb_sync.py --wandb-entity me --wandb-project sweep \
        --project-id proj_xyz --once
"""

from __future__ import annotations

import argparse
import json
import os
import time
from typing import Any, Dict, List, Optional

import httpx

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECTS_FILE = os.getenv(
    "GROUNDHOG_PROJECTS_FILE", os.path.join(_ROOT, "groundhog_projects.json")
)
_STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".wandb_sync_state.json")


# ---------------------------------------------------------------------------
# Groundhog project lookup (local file) + sync watermark
# ---------------------------------------------------------------------------

def _load_project(project_id: str) -> Optional[Dict[str, Any]]:
    if not os.path.exists(_PROJECTS_FILE):
        return None
    try:
        with open(_PROJECTS_FILE, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    for p in data.get("projects", []):
        if p.get("project_id") == project_id:
            return p
    return None


def _load_state() -> Dict[str, Any]:
    if not os.path.exists(_STATE_FILE):
        return {}
    try:
        with open(_STATE_FILE, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, json.JSONDecodeError):
        return {}


def _save_state(state: Dict[str, Any]) -> None:
    tmp = _STATE_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
    os.replace(tmp, _STATE_FILE)


# ---------------------------------------------------------------------------
# W&B extraction
# ---------------------------------------------------------------------------

def _result_summary(state: str, metrics: Dict[str, Any], notes: str) -> str:
    loss = metrics.get("val_loss", metrics.get("loss", "N/A"))
    acc = metrics.get("val_accuracy", metrics.get("val_acc", metrics.get("accuracy", "N/A")))
    s = f"Run status: {state}. val_loss={loss}, val_accuracy={acc}."
    if notes:
        s += f" Researcher notes: {notes}"
    return s


_STATE_MAP = {"finished": "completed", "failed": "failed", "crashed": "failed",
              "killed": "aborted", "running": "aborted"}

# Config keys people commonly log a dataset under, so a synced W&B run can be
# attached to the right dataset node instead of a catch-all "unknown".
_DATASET_CONFIG_KEYS = ("dataset", "dataset_name", "data", "datamodule", "data_name")


def _infer_dataset_name(config: Dict[str, Any], default: Optional[str]) -> Optional[str]:
    """Best-effort dataset name from a W&B run's config, else the project default."""
    for k in _DATASET_CONFIG_KEYS:
        v = config.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
        if isinstance(v, dict):
            name = v.get("name") or v.get("dataset")
            if isinstance(name, str) and name.strip():
                return name.strip()
    return default


def fetch_new_runs(entity: str, project: str, api_key: Optional[str],
                   since_created: Optional[str],
                   default_dataset: Optional[str] = None) -> List[Dict[str, Any]]:
    """Return W&B runs created after `since_created` (ISO ts), newest last."""
    import wandb
    if api_key:
        os.environ["WANDB_API_KEY"] = api_key
    api = wandb.Api()
    runs = api.runs(f"{entity}/{project}")

    collected = []
    for run in runs:
        # Skip runs the app itself mirrored INTO W&B (tagged groundhog-origin) —
        # re-ingesting them would duplicate runs that already live in memory and
        # form a mirror<->sync feedback loop.
        if "groundhog-origin" in (getattr(run, "tags", None) or []):
            continue
        created = str(getattr(run, "created_at", "") or "")
        if since_created and created and created <= since_created:
            continue
        clean_config = {k: v for k, v in run.config.items() if not k.startswith("_")}
        dataset_name = _infer_dataset_name(clean_config, default_dataset)
        clean_config["_wandb_url"] = run.url
        clean_metrics = {k: v for k, v in run.summary.items() if not k.startswith("_")}
        wall = run.summary.get("_runtime", 0.0) or 0.0
        collected.append({
            "wandb_id": run.id,
            "created_at": created,
            "config": clean_config,
            "metrics": clean_metrics,
            "status": _STATE_MAP.get((run.state or "").lower(), "completed"),
            "rationale": _result_summary(run.state, clean_metrics, run.notes or ""),
            "gpu_hours": round(wall / 3600.0, 2) if wall else 0.0,
            "experiment": run.group or project,
            "thread": run.job_type or "default",
            "dataset_name": dataset_name,
        })
    collected.sort(key=lambda r: r["created_at"])
    return collected


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------

def sync_once(backend_url: str, project_id: str, entity: str, project: str,
              api_key: Optional[str], default_dataset: Optional[str] = None) -> int:
    state = _load_state()
    watermark = state.get(project_id, {}).get("since_created")
    try:
        new_runs = fetch_new_runs(entity, project, api_key, watermark, default_dataset)
    except Exception as e:
        print(f"[!] W&B fetch failed: {e}")
        return 0

    if not new_runs:
        print(f"[*] {project_id}: no new W&B runs since {watermark or 'the beginning'}")
        return 0

    print(f"[*] {project_id}: {len(new_runs)} new W&B run(s) to ingest")
    count = 0
    last_created = watermark
    with httpx.Client(timeout=180.0) as client:
        for r in new_runs:
            payload = {
                "project_id": project_id,
                "experiment": r["experiment"],
                "thread": r["thread"],
                "config": r["config"],
                "metrics": r["metrics"],
                "rationale": r["rationale"],
                "status": r["status"],
                "gpu_hours": r["gpu_hours"],
                "git_commit": "wandb",
            }
            if r.get("dataset_name"):
                payload["dataset"] = {"name": r["dataset_name"], "version": "wandb-sync"}
            try:
                resp = client.post(f"{backend_url}/api/runs/remember", json=payload)
                resp.raise_for_status()
                count += 1
                last_created = r["created_at"] or last_created
                print(f"    -> ingested W&B run {r['wandb_id']} ({r['status']})")
            except httpx.HTTPError as e:
                print(f"    [!] failed to ingest {r['wandb_id']}: {e}")

    state.setdefault(project_id, {})["since_created"] = last_created
    _save_state(state)
    return count


def resolve_creds(args) -> Dict[str, Optional[str]]:
    """CLI/env creds win; else pull from the Groundhog project's stored W&B creds."""
    entity, project, api_key = args.wandb_entity, args.wandb_project, args.wandb_api_key
    default_dataset = getattr(args, "default_dataset", None)
    if (not entity or not project) and args.project_id:
        proj = _load_project(args.project_id)
        wb = (proj or {}).get("wandb", {})
        entity = entity or wb.get("entity")
        project = project or wb.get("project")
        api_key = api_key or wb.get("api_key")
        default_dataset = default_dataset or wb.get("default_dataset")
    api_key = api_key or os.getenv("WANDB_API_KEY")
    return {"entity": entity, "project": project, "api_key": api_key,
            "default_dataset": default_dataset}


def main():
    ap = argparse.ArgumentParser(description="Sync W&B runs into a Groundhog project.")
    ap.add_argument("--project-id", required=True, help="Groundhog project_id to ingest into")
    ap.add_argument("--backend-url", default=os.getenv("GROUNDHOG_API_URL", "http://localhost:8000"))
    ap.add_argument("--wandb-entity", default=None)
    ap.add_argument("--wandb-project", default=None)
    ap.add_argument("--wandb-api-key", default=None)
    ap.add_argument("--default-dataset", dest="default_dataset", default=None,
                    help="Dataset name for synced runs that don't log one in their W&B config")
    ap.add_argument("--interval", type=int, default=0, help="Poll every N seconds (0 = run once)")
    ap.add_argument("--once", action="store_true", help="Sync once and exit")
    args = ap.parse_args()

    creds = resolve_creds(args)
    if not creds["entity"] or not creds["project"]:
        print("[!] No W&B entity/project. Set them on the Groundhog project, or pass "
              "--wandb-entity/--wandb-project.")
        return

    print(f"[*] Syncing W&B {creds['entity']}/{creds['project']} -> Groundhog {args.project_id}")

    if args.once or args.interval <= 0:
        n = sync_once(args.backend_url, args.project_id, creds["entity"], creds["project"],
                      creds["api_key"], creds.get("default_dataset"))
        print(f"[+] Done. Ingested {n} run(s).")
        return

    print(f"[*] Watch mode: polling every {args.interval}s. Ctrl+C to stop.")
    try:
        while True:
            sync_once(args.backend_url, args.project_id, creds["entity"], creds["project"],
                      creds["api_key"], creds.get("default_dataset"))
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[*] Stopped.")


if __name__ == "__main__":
    main()
