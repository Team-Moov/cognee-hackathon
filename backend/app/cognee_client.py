"""
HTTP client for the cognee-backed memory server (root main.py, memory.py).

Why HTTP and not an in-process import: main.py's own docstring establishes a
"single gatekeeper" constraint — only one process should touch cognee's local
SQLite/Kuzu/LanceDB files, to avoid concurrent-access file locking issues.
backend/app is a separate FastAPI process (Postgres + Groq), so it reaches
cognee over HTTP instead of importing it directly — same pattern the MCP
server already uses.

Before this module existed, backend/app had zero cognee involvement: /remember,
/check-config, and /query were pure Postgres + hand-rolled similarity/full-text
search. Now those three hot paths call through to the real cognee-backed
remember()/recall() operations here, with Postgres kept only for the
agent_suggestions table and a fast local lineage/listing cache — not as a
Cognee substitute.
"""

from __future__ import annotations

import logging
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


async def remember_run(
    base_url: str,
    *,
    config: Dict[str, Any],
    metrics: Dict[str, Any],
    experiment: str,
    rationale: str = "",
    status: str = "completed",
    gpu_hours: Optional[float] = None,
    git_commit: str = "unknown",
    output_dir: Optional[str] = None,
    session_id: Optional[str] = None,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    """Calls the real cognee-backed POST /remember (memory.remember_run)."""
    payload = {
        "config_params": config,
        "result_metrics": metrics,
        "status": status,
        "rationale": rationale,
        "experiment_name": experiment,
        "thread_name": "default",
        "gpu_hours": gpu_hours,
        "git_commit": git_commit,
        "output_dir": output_dir,
        "session_id": session_id,
        "dataset": "main_dataset",
    }
    return await _post(base_url, "/remember", payload, timeout)


async def check_config(
    base_url: str,
    *,
    config: Dict[str, Any],
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Calls the real cognee-backed POST /check-config (Pre-flight Guard)."""
    return await _post(base_url, "/check-config", {"config_params": config, "dataset": "main_dataset"}, timeout)


async def query(
    base_url: str,
    *,
    question: str,
    node_name: Optional[List[str]] = None,
    timeout: float = 45.0,
) -> Dict[str, Any]:
    """Calls the real cognee-backed POST /query (cognee.recall)."""
    payload: Dict[str, Any] = {"question": question}
    if node_name:
        payload["node_name"] = node_name
    return await _post(base_url, "/query", payload, timeout)


async def health(base_url: str, timeout: float = 5.0) -> Dict[str, Any]:
    return await _get(base_url, "/health", timeout)


async def query_graph_context(
    base_url: str,
    *,
    question: str,
    experiment: str,
    timeout: float = 45.0,
) -> str:
    """
    Read half of the subagent <-> graph loop: pull graph context (prior
    decisions, hypotheses, agent findings, ontology-grounded relationships)
    scoped to one experiment, via the real cognee.recall(), instead of the
    agent only ever seeing flat Postgres rows.

    Returns just the answer text (empty string on any failure) since callers
    fold this into an LLM prompt alongside their Postgres-sourced run rows —
    a failed/empty graph lookup should degrade gracefully, not break the agent.
    """
    node_name = [f"experiment:{_slug(experiment)}"]
    try:
        result = await query(base_url, question=question, node_name=node_name, timeout=timeout)
        return result.get("answer", "") or ""
    except CogneeClientError as e:
        logger.warning("query_graph_context: cognee unreachable for experiment=%s: %s", experiment, e)
        return ""


async def remember_agent_finding(
    base_url: str,
    *,
    agent_type: str,
    experiment: str,
    content: str,
    metadata: Optional[Dict[str, Any]] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """
    Write half of the subagent <-> graph loop: persist a subagent's finding
    into the real graph (POST /agent-finding -> memory.remember_agent_finding),
    tagged experiment/agent/kind so it's recall()-able later by any other
    agent or by a human via the NL query bar — not just visible in this one
    agent's private Postgres suggestion row.
    """
    payload = {
        "agent_type": agent_type,
        "experiment_name": experiment,
        "content": content,
        "metadata": metadata or {},
    }
    return await _post(base_url, "/agent-finding", payload, timeout)


def _slug(text: str) -> str:
    """Mirrors memory.py's _slug() so node_name tags match what remember_run() wrote."""
    import re
    text = (text or "unknown").strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_") or "unknown"
