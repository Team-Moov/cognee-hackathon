"""
HTTP client for the cognee-backed memory server (root main.py, memory.py).

Why HTTP and not an in-process import: main.py's own docstring establishes a
"single gatekeeper" constraint — only one process should touch cognee's local
SQLite/Kuzu/LanceDB files, to avoid concurrent-access file locking issues.
backend/app is a separate FastAPI process, so it reaches cognee over HTTP
instead of importing it directly — same pattern the MCP server already uses.

This module keeps the backend API focused on transport and response shaping
while the actual memory and graph work stays inside the Cognee server.
"""

from __future__ import annotations

import json
import logging
import re
from urllib.parse import quote
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger("groundhog.cognee_client")


class CogneeClientError(Exception):
    """Raised when the cognee memory server is unreachable or returns an error."""


async def _post(base_url: str, path: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(f"{base_url}{path}", json=payload)
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise CogneeClientError(f"cognee server returned {e.response.status_code}: {e.response.text[:300]}") from e
    except httpx.RequestError as e:
        raise CogneeClientError(f"cognee server unreachable at {base_url}{path}: {e}") from e


async def _get(base_url: str, path: str, timeout: float) -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"{base_url}{path}")
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise CogneeClientError(f"cognee server returned {e.response.status_code}: {e.response.text[:300]}") from e
    except httpx.RequestError as e:
        raise CogneeClientError(f"cognee server unreachable at {base_url}{path}: {e}") from e


def _extract_json_payload(text: str) -> Any:
    """Best-effort extraction of a JSON object or array from Cognee's answer text."""
    if not text:
        return None
    candidate = text.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines and lines[0].startswith("```"):
            candidate = "\n".join(lines[1:])
        if candidate.endswith("```"):
            candidate = candidate[:-3].strip()

    for opener, closer in (("[", "]"), ("{", "}")):
        start = candidate.find(opener)
        end = candidate.rfind(closer)
        if start != -1 and end != -1 and end > start:
            snippet = candidate[start:end + 1]
            try:
                return json.loads(snippet)
            except json.JSONDecodeError:
                continue

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _slug(text: str) -> str:
    text = (text or "unknown").strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "unknown"


async def remember_run(
    base_url: str,
    *,
    config: Dict[str, Any],
    metrics: Dict[str, Any],
    experiment: str,
    rationale: str = "",
    status: str = "completed",
    gpu_hours: Optional[float] = None,
    wall_clock_seconds: Optional[float] = None,
    git_commit: str = "unknown",
    output_dir: Optional[str] = None,
    session_id: Optional[str] = None,
    dataset: str = "main_dataset",
    dataset_info: Optional[Dict[str, Any]] = None,
    hypothesis: Optional[str] = None,
    derived_from: Optional[str] = None,
    significant_keys: Optional[List[str]] = None,
    thread: str = "default",
    timeout: float = 60.0,
) -> Dict[str, Any]:
    """Calls the real cognee-backed POST /remember (memory.remember_run)."""
    di = dataset_info or {}
    payload = {
        "config_params": config,
        "result_metrics": metrics,
        "status": status,
        "rationale": rationale,
        "experiment_name": experiment,
        "thread_name": thread,
        "hypothesis": hypothesis or "",
        "gpu_hours": gpu_hours,
        "wall_clock_seconds": wall_clock_seconds,
        "git_commit": git_commit,
        "output_dir": output_dir,
        "derived_from_config_hash": derived_from,
        # dataset provenance — the Cognee server turns these into a Dataset node
        "dataset_name_label": di.get("name") or "unknown",
        "dataset_version": di.get("version") or "v1",
        "preprocessing_notes": di.get("preprocessing") or "",
        "split_rationale": di.get("split_rationale") or "",
        "quality_issues": di.get("quality_issues") or "",
        "session_id": session_id,
        "dataset": dataset,
        "significant_keys": significant_keys,
    }
    return await _post(base_url, "/remember", payload, timeout)


async def check_config(
    base_url: str,
    *,
    config: Dict[str, Any],
    dataset: str = "main_dataset",
    significant_keys: Optional[List[str]] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Calls the real cognee-backed POST /check-config (Pre-flight Guard)."""
    return await _post(
        base_url, "/check-config",
        {"config_params": config, "dataset": dataset, "significant_keys": significant_keys},
        timeout,
    )


async def query(
    base_url: str,
    *,
    question: str,
    node_name: Optional[List[str]] = None,
    dataset: Optional[str] = None,
    timeout: float = 45.0,
) -> Dict[str, Any]:
    """Calls the real cognee-backed POST /query (cognee.recall)."""
    payload: Dict[str, Any] = {"question": question}
    if node_name:
        payload["node_name"] = node_name
    if dataset:
        payload["dataset"] = dataset
    return await _post(base_url, "/query", payload, timeout)


async def list_runs(
    base_url: str,
    *,
    experiment: Optional[str] = None,
    status: Optional[str] = None,
    project: Optional[str] = None,
    limit: int = 200,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    """
    Fetch run records from the deterministic GET /runs index.

    This replaces the old approach of asking the LLM to *emit* a JSON array of
    runs from a completion query (slow, token-costly, and prone to hallucinating
    rows). Structured listing is served from the index; Cognee is still used for
    semantic recall via /query.
    """
    params: List[str] = [f"limit={limit}"]
    if experiment:
        params.append(f"experiment={quote(experiment, safe='')}")
    if status:
        params.append(f"status={quote(status, safe='')}")
    if project:
        params.append(f"project={quote(project, safe='')}")
    path = "/runs?" + "&".join(params)
    result = await _get(base_url, path, timeout)
    runs = result.get("runs", []) if isinstance(result, dict) else []
    return {"runs": runs, "total": result.get("total", len(runs)) if isinstance(result, dict) else len(runs)}


async def health(base_url: str, timeout: float = 5.0) -> Dict[str, Any]:
    return await _get(base_url, "/health", timeout)


async def agent_finding(
    base_url: str,
    *,
    agent_type: str,
    experiment: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    dataset: Optional[str] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    payload = {
        "agent_type": agent_type,
        "experiment_name": experiment,
        "content": content,
        "metadata": metadata or {},
    }
    if dataset:
        payload["dataset"] = dataset
    return await _post(base_url, "/agent-finding", payload, timeout)


async def query_graph_context(
    base_url: str,
    *,
    question: str,
    experiment: str,
    dataset: Optional[str] = None,
    timeout: float = 45.0,
) -> str:
    """
    Read half of the subagent <-> graph loop: pull graph context (prior
    decisions, hypotheses, agent findings, ontology-grounded relationships)
    scoped to one experiment, via the real cognee.recall(), instead of the
    agent only ever seeing a local database cache.

    Returns just the answer text (empty string on any failure) since callers
    fold this into an LLM prompt alongside run history from the graph — a
    failed/empty graph lookup should degrade gracefully, not break the agent.
    """
    node_name = [f"experiment:{_slug(experiment)}"]
    try:
        result = await query(base_url, question=question, node_name=node_name, dataset=dataset, timeout=timeout)
        return result.get("answer", "") or ""
    except CogneeClientError as e:
        logger.warning("query_graph_context: cognee unreachable for experiment=%s: %s", experiment, e)
        return ""


async def list_agent_suggestions(
    base_url: str,
    *,
    experiment: Optional[str] = None,
    project: Optional[str] = None,
    include_dismissed: bool = False,
    timeout: float = 45.0,
) -> Dict[str, Any]:
    params: List[str] = []
    if experiment:
        params.append(f"experiment={quote(experiment, safe='')}")
    if project:
        params.append(f"project={quote(project, safe='')}")
    if include_dismissed:
        params.append("include_dismissed=true")
    path = "/agent-findings" + ("?" + "&".join(params) if params else "")
    result = await _get(base_url, path, timeout)
    suggestions = result.get("suggestions", []) if isinstance(result, dict) else []
    return {"suggestions": suggestions, "total": result.get("total", len(suggestions)) if isinstance(result, dict) else len(suggestions)}


async def remember_agent_finding(
    base_url: str,
    *,
    agent_type: str,
    experiment: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    dataset: Optional[str] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """
    Write half of the subagent <-> graph loop: persist a subagent's finding
    into the real graph (POST /agent-finding -> memory.remember_agent_finding),
    tagged experiment/agent/kind so it's recall()-able later by any other
    agent or by a human via the NL query bar.
    """
    payload = {
        "agent_type": agent_type,
        "experiment_name": experiment,
        "content": content,
        "metadata": metadata or {},
    }
    if dataset:
        payload["dataset"] = dataset
    return await _post(base_url, "/agent-finding", payload, timeout)


async def dismiss_finding(base_url: str, *, finding_id: str, timeout: float = 15.0) -> Dict[str, Any]:
    """Persistently dismiss an agent finding on the Cognee server (survives restart)."""
    return await _post(base_url, f"/agent-findings/{quote(finding_id, safe='')}/dismiss", {}, timeout)


async def _delete(base_url: str, path: str, timeout: float) -> Dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.delete(f"{base_url}{path}")
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPStatusError as e:
        raise CogneeClientError(f"cognee server returned {e.response.status_code}: {e.response.text[:300]}") from e
    except httpx.RequestError as e:
        raise CogneeClientError(f"cognee server unreachable at {base_url}{path}: {e}") from e


async def delete_run(base_url: str, *, run_id: str, timeout: float = 30.0) -> Dict[str, Any]:
    return await _delete(base_url, f"/runs/{quote(run_id, safe='')}", timeout)


async def delete_project_data(base_url: str, *, project: str, timeout: float = 30.0) -> Dict[str, Any]:
    return await _delete(base_url, f"/project/{quote(project, safe='')}", timeout)


async def get_graph(base_url: str, *, project: Optional[str] = None, timeout: float = 30.0) -> Dict[str, Any]:
    path = "/graph" + (f"?project={quote(project, safe='')}" if project else "")
    return await _get(base_url, path, timeout)


async def get_insights(base_url: str, *, project: Optional[str] = None, timeout: float = 30.0) -> Dict[str, Any]:
    path = "/insights" + (f"?project={quote(project, safe='')}" if project else "")
    return await _get(base_url, path, timeout)


async def generate_insights(base_url: str, *, project: str, timeout: float = 60.0) -> Dict[str, Any]:
    return await _post(base_url, "/insights/generate", {"project": project}, timeout)


async def find_file(base_url: str, *, description: str, timeout: float = 45.0) -> Dict[str, Any]:
    encoded = quote(description, safe="")
    return await _get(base_url, f"/find-file?description={encoded}", timeout)


async def get_orphans(base_url: str, timeout: float = 45.0) -> Dict[str, Any]:
    return await _get(base_url, "/orphans", timeout)


async def lineage(base_url: str, *, run_id: str, timeout: float = 45.0) -> Dict[str, Any]:
    return await _get(base_url, f"/lineage/{run_id}", timeout)


async def improve(base_url: str, *, dataset_name: str = "main_dataset", timeout: float = 60.0) -> Dict[str, Any]:
    return await _post(base_url, "/improve", {"dataset_name": dataset_name}, timeout)


async def forget(base_url: str, *, dataset_name: str, criteria: Dict[str, Any], timeout: float = 60.0) -> Dict[str, Any]:
    return await _post(base_url, "/forget", {"dataset_name": dataset_name, "criteria": criteria}, timeout)


async def promote(base_url: str, *, to_dataset: str, session_id: str, timeout: float = 60.0) -> Dict[str, Any]:
    return await _post(base_url, "/promote", {"to_dataset": to_dataset, "session_id": session_id}, timeout)


def _slug(text: str) -> str:
    """Mirrors memory.py's _slug() so node_name tags match what remember_run() wrote."""
    import re
    text = (text or "unknown").strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "unknown"
