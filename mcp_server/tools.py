"""
Groundhog MCP Tool Implementations.

Each function here is one MCP tool. They make async HTTP calls to the
Groundhog app backend (Cognee-backed gateway, default: http://localhost:8000)
and return plain-text responses that MCP clients (Claude Code, Cursor, etc.)
can read.

Backend endpoints used:
  POST /api/runs/check-config  → groundhog_check_config
  POST /api/runs/remember      → groundhog_remember
  POST /api/query              → groundhog_query
  GET  /api/files/find         → groundhog_find
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("groundhog.mcp.tools")


def _backend_url(path: str) -> str:
    """Build a full URL against the configured backend base URL."""
    from mcp_server.config import settings
    base = settings.groundhog_api_url.rstrip("/")
    return f"{base}{path}"


async def tool_check_config(
    config: Dict[str, Any],
    experiment: Optional[str] = None,
) -> str:
    """
    Check whether a given experiment configuration has already been tried.

    Args:
        config:     The hyperparameter dict to check (e.g. {"lr": 0.001, "model": "ResNet50"}).
        experiment: Optional experiment name to narrow the search scope.

    Returns:
        A human-readable summary of whether this config was already run,
        including metrics from the matching run if one is found.
    """
    payload: Dict[str, Any] = {"config": config}
    if experiment:
        payload["experiment"] = experiment

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(_backend_url("/api/runs/check-config"), json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        return f"[groundhog_check_config] Backend error {e.response.status_code}: {e.response.text}"
    except Exception as e:
        return f"[groundhog_check_config] Connection error: {e}"

    already_tried: bool = data.get("already_tried", False)
    match_type: str = data.get("match_type", "none")
    score: Optional[float] = data.get("similarity_score")
    recommendation: str = data.get("recommendation", "")
    matches: List[Dict] = data.get("matching_runs", [])

    if not already_tried and match_type == "none":
        return (
            "✅ **No prior runs found for this configuration.** "
            "It is safe to proceed.\n\n"
            f"Config checked: `{json.dumps(config, separators=(',', ':'))}`"
        )

    lines = []
    if match_type == "exact":
        lines.append("⚠️ **EXACT DUPLICATE DETECTED** — this config has already been run.")
    else:
        pct = f"{score:.0%}" if score is not None else "?"
        lines.append(f"⚠️ **SIMILAR CONFIG FOUND** ({pct} match) — review before proceeding.")

    if recommendation:
        lines.append(f"\n**Recommendation:** {recommendation}")

    for run in matches[:3]:
        lines.append(
            f"\n**Run `{run.get('run_id', '?')}`** "
            f"on `{str(run.get('date', ''))[:10]}`  "
            f"| status: `{run.get('status', '?')}`  "
            f"| GPU-h: `{run.get('gpu_hours', '?')}`"
        )
        metrics = run.get("metrics", {})
        if isinstance(metrics, dict) and metrics:
            m_str = ", ".join(f"{k}={v}" for k, v in list(metrics.items())[:4])
            lines.append(f"  Metrics: {m_str}")
        # rationale can arrive as a dict/list (raw recall snippet) — coerce so
        # slicing never blows up on non-string prior-result payloads.
        rationale = run.get("rationale", "")
        if isinstance(rationale, (dict, list)):
            rationale = json.dumps(rationale, default=str)
        rationale = str(rationale)
        if rationale:
            lines.append(f"  Rationale: _{rationale[:200]}_")

    return "\n".join(lines)


async def tool_remember(
    experiment: str,
    config: Dict[str, Any],
    metrics: Dict[str, Any],
    rationale: str,
    status: str = "completed",
    gpu_hours: Optional[float] = None,
    git_commit: str = "unknown",
    error_message: Optional[str] = None,
    artifacts: Optional[List[Dict[str, str]]] = None,
) -> str:
    """
    Record a completed (or failed) experiment run into Groundhog's memory.

    Args:
        experiment:    Name of the experiment or project (e.g. "resnet-lr-sweep").
        config:        The hyperparameter / configuration dict used for this run.
        metrics:       Final result metrics (e.g. {"val_acc": 0.89, "val_loss": 0.31}).
        rationale:     The researcher's (or agent's) reasoning for trying this config.
        status:        One of "completed", "failed", "aborted".
        gpu_hours:     GPU-hours consumed (optional but strongly encouraged).
        git_commit:    Git commit SHA at time of run (optional).
        error_message: If status is "failed", the error or failure reason.
        artifacts:     List of produced files: [{"type": "checkpoint", "path": "/runs/..."}].

    Returns:
        Confirmation with the assigned run_id and config hash.
    """
    payload: Dict[str, Any] = {
        "experiment": experiment,
        "config": config,
        "metrics": metrics,
        "rationale": rationale,
        "status": status,
        "git_commit": git_commit,
        "artifacts": artifacts or [],
    }
    if gpu_hours is not None:
        payload["gpu_hours"] = gpu_hours
    if error_message:
        payload["error_message"] = error_message

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.post(_backend_url("/api/runs/remember"), json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        return f"[groundhog_remember] Backend error {e.response.status_code}: {e.response.text}"
    except Exception as e:
        return f"[groundhog_remember] Connection error: {e}"

    run_id = data.get("run_id", "?")
    config_hash = data.get("config_hash", "?")[:12]
    return (
        f"✅ **Run recorded successfully.**\n\n"
        f"- **Run ID:** `{run_id}`\n"
        f"- **Experiment:** `{experiment}`\n"
        f"- **Status:** `{status}`\n"
        f"- **Config hash:** `{config_hash}…`\n\n"
        f"This run is now queryable via `groundhog_query` and will be "
        f"checked by future `groundhog_check_config` calls."
    )


async def tool_query(question: str) -> str:
    """
    Ask a free-form natural language question about the experiment history.

    Uses full-text search + LLM synthesis to answer questions like:
    "What happened when we used AdamW?", "Which run had the best val_acc?",
    "Why did we abandon learning rate 0.5?", "Catch me up on the ResNet sweep."

    Args:
        question: The natural language question to ask.

    Returns:
        A synthesized, cited answer drawn from Groundhog's experiment memory.
    """
    payload = {"question": question, "mode": "COMPLETION"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(_backend_url("/api/query"), json=payload)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        return f"[groundhog_query] Backend error {e.response.status_code}: {e.response.text}"
    except Exception as e:
        return f"[groundhog_query] Connection error: {e}"

    answer = data.get("answer", "No answer returned.")
    citations: List[str] = data.get("citations", [])
    chunks: List[Dict] = data.get("chunks", [])

    lines = [answer]

    if citations:
        lines.append(f"\n**Cited runs:** " + ", ".join(f"`{c}`" for c in citations))

    if chunks and not citations:
        # Surface top runs even when not explicitly cited
        top = chunks[:5]
        lines.append("\n**Runs retrieved as context:**")
        for c in top:
            score = c.get("score", 0)
            lines.append(f"- `{c.get('run_id', '?')}` (relevance: {score:.3f})")

    return "\n".join(lines)


async def tool_find(description: str) -> str:
    """
    Find an artifact file (checkpoint, plot, eval report, log) by natural language description.

    Searches indexed artifact paths across all runs. Never again spelunk through
    run_47_v2_final_FINAL/ to find a checkpoint.

    Args:
        description: Natural language description of the file
                     (e.g. "best ResNet checkpoint from imagenet sweep",
                      "validation loss curve for AdamW run").

    Returns:
        The exact file path and associated run metadata, or a not-found message.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                _backend_url("/api/files/find"),
                params={"q": description},
            )
            if resp.status_code == 404:
                return (
                    f"❌ **No artifact found** matching: _{description}_\n\n"
                    "Tip: artifacts are only indexed if they were logged via "
                    "`groundhog_remember` with an `artifacts` list."
                )
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        return f"[groundhog_find] Backend error {e.response.status_code}: {e.response.text}"
    except Exception as e:
        return f"[groundhog_find] Connection error: {e}"

    path = data.get("path", "?")
    run_id = data.get("run_id", "?")
    art_type = data.get("artifact_type", "unknown")
    exists = data.get("exists_on_disk", False)
    status_icon = "✅" if exists else "⚠️ (file not found on disk)"

    return (
        f"📁 **Artifact found** {status_icon}\n\n"
        f"- **Path:** `{path}`\n"
        f"- **Type:** `{art_type}`\n"
        f"- **Produced by run:** `{run_id}`\n"
        f"- **Exists on disk:** `{exists}`"
    )
