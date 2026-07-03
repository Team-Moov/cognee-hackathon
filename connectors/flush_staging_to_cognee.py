"""
connectors/flush_staging_to_cognee.py — closes the staging-file dead end.

Both wandb_bridge.py and jupyter_magic.py write to local JSON staging files
(staging/wb_staging.json, staging/notebook_notes.json) and stop there —
nothing used to read them back, so W&B runs and notebook hypotheses/decisions
never actually reached the memory graph. This script is that missing read
step: it loads both staging files and POSTs each entry to the cognee-backed
memory server's POST /remember (root main.py), closing the loop for both
Tier-1 connectors described in the plan.

Usage:
    python connectors/flush_staging_to_cognee.py
    python connectors/flush_staging_to_cognee.py --cognee-url http://localhost:8010
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from typing import Any, Dict, List

import httpx

STAGING_DIR = os.path.join(os.path.dirname(__file__), "..", "staging")
WANDB_STAGING_FILE = os.path.join(STAGING_DIR, "wb_staging.json")
NOTEBOOK_STAGING_FILE = os.path.join(STAGING_DIR, "notebook_notes.json")


def _load_json(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


async def _remember(client: httpx.AsyncClient, cognee_url: str, payload: Dict[str, Any]) -> None:
    resp = await client.post(f"{cognee_url}/remember", json=payload, timeout=60.0)
    resp.raise_for_status()
    result = resp.json()
    print(f"  -> remembered config_hash={result.get('config_hash', '')[:12]} "
          f"node_set={result.get('node_set')}")


async def flush_wandb_staging(client: httpx.AsyncClient, cognee_url: str) -> int:
    data = _load_json(WANDB_STAGING_FILE)
    configs = {c["id"]: c for c in data.get("configs", [])}
    results = data.get("results", [])
    if not results:
        print(f"[*] No W&B staging data found at {WANDB_STAGING_FILE}")
        return 0

    print(f"[*] Flushing {len(results)} W&B run(s) from staging into cognee...")
    count = 0
    for result in results:
        config = configs.get(result.get("config_id"), {})
        payload = {
            "config_params": config.get("parameters", {}),
            "result_metrics": result.get("metrics", {}),
            "status": _normalize_status(result.get("status", "completed")),
            "rationale": result.get("summary_text", ""),
            "experiment_name": config.get("research_thread_id", "wandb_import"),
            "thread_name": config.get("research_thread_id", "default"),
            "gpu_hours": result.get("gpu_hours"),
            "wall_clock_seconds": result.get("wall_clock_seconds"),
            "git_commit": "unknown",
            "dataset": "main_dataset",
        }
        try:
            await _remember(client, cognee_url, payload)
            count += 1
        except httpx.HTTPError as e:
            print(f"  [!] Failed to remember W&B run {result.get('id')}: {e}")
    return count


def _normalize_status(wandb_state: str) -> str:
    """W&B run.state values (finished/failed/crashed/killed) -> our completed/failed/aborted."""
    mapping = {
        "finished": "completed",
        "failed": "failed",
        "crashed": "failed",
        "killed": "aborted",
        "running": "aborted",
    }
    return mapping.get((wandb_state or "").lower(), "completed")


async def flush_notebook_staging(client: httpx.AsyncClient, cognee_url: str) -> int:
    data = _load_json(NOTEBOOK_STAGING_FILE)
    hypotheses = data.get("hypotheses", [])
    decisions = data.get("decisions", [])
    observations = data.get("cell_observations", [])
    total = len(hypotheses) + len(decisions) + len(observations)
    if not total:
        print(f"[*] No notebook staging data found at {NOTEBOOK_STAGING_FILE}")
        return 0

    print(f"[*] Flushing {total} notebook note(s) from staging into cognee...")
    count = 0

    for h in hypotheses:
        payload = {
            "config_params": {},
            "result_metrics": {},
            "status": "completed",
            "rationale": f"Hypothesis: {h.get('statement', '')}",
            "hypothesis": h.get("statement", ""),
            "experiment_name": "notebook_scratch",
            "thread_name": h.get("research_thread_id", "default"),
            "git_commit": "unknown",
            "dataset": "main_dataset",
        }
        try:
            await _remember(client, cognee_url, payload)
            count += 1
        except httpx.HTTPError as e:
            print(f"  [!] Failed to remember hypothesis {h.get('id')}: {e}")

    for d in decisions:
        payload = {
            "config_params": {},
            "result_metrics": {},
            "status": "completed",
            "rationale": d.get("rationale", ""),
            "experiment_description": d.get("description", ""),
            "experiment_name": "notebook_scratch",
            "thread_name": d.get("research_thread_id", "default"),
            "git_commit": "unknown",
            "dataset": "main_dataset",
        }
        try:
            await _remember(client, cognee_url, payload)
            count += 1
        except httpx.HTTPError as e:
            print(f"  [!] Failed to remember decision {d.get('id')}: {e}")

    for o in observations:
        payload = {
            "config_params": {},
            "result_metrics": {"duration_seconds": o.get("duration_seconds", 0)},
            "status": "completed" if o.get("success") else "failed",
            "rationale": f"Notebook cell executed:\n{o.get('code_executed', '')[:500]}",
            "experiment_name": "notebook_scratch",
            "thread_name": "cell_observations",
            "git_commit": "unknown",
            "dataset": "main_dataset",
        }
        try:
            await _remember(client, cognee_url, payload)
            count += 1
        except httpx.HTTPError as e:
            print(f"  [!] Failed to remember cell observation {o.get('id')}: {e}")

    return count


async def main(cognee_url: str) -> None:
    async with httpx.AsyncClient() as client:
        try:
            health = await client.get(f"{cognee_url}/health", timeout=5.0)
            health.raise_for_status()
        except httpx.HTTPError as e:
            print(f"[!] Cognee server not reachable at {cognee_url}: {e}")
            print("    Start it first: uvicorn main:app --port 8010")
            return

        wandb_count = await flush_wandb_staging(client, cognee_url)
        notebook_count = await flush_notebook_staging(client, cognee_url)
        print(f"[+] Done. Remembered {wandb_count} W&B run(s) and {notebook_count} notebook note(s).")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cognee-url",
        default=os.getenv("COGNEE_API_URL", "http://localhost:8010"),
        help="Base URL of the cognee-backed memory server (root main.py).",
    )
    args = parser.parse_args()
    asyncio.run(main(args.cognee_url))
