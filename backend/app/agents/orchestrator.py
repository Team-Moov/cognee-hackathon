"""
Orchestrator — event router for the blackboard architecture.

On every `run_remembered` event, the orchestrator fans out to whichever
subagents care about that event. No subagent talks to another directly —
coordination flows through the Cognee memory server, which keeps two views of
each finding (Postgres was removed):

  - The structured index (run_index) on the Cognee server — the UI-facing,
    deduplicated, dismissible cards served via GET /agent-findings.
  - The cognee graph — the actual blackboard. Each agent READS prior graph
    context (decisions, hypotheses, other agents' findings) before reasoning,
    and WRITES its own finding back via /agent-finding (remember_agent_finding),
    so the next agent — or a human via the NL query bar — can recall() it
    later. This is what makes "the graph is the coordination layer" (plan
    Section 7) true, instead of every agent only ever seeing its own private row.

This runs as a FastAPI BackgroundTask, so it never blocks the API response.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from app.config import settings
from app import cognee_client

logger = logging.getLogger("groundhog.orchestrator")


async def _read_graph_context(experiment: str) -> str:
    """Fetched once per event and shared by every agent — avoids N duplicate
    cognee calls for the same experiment in a single orchestration pass."""
    if not settings.cognee_api_url:
        return ""
    return await cognee_client.query_graph_context(
        settings.cognee_api_url,
        question=(
            f"What decisions, hypotheses, and prior agent findings exist for "
            f"experiment '{experiment}'?"
        ),
        experiment=experiment,
        timeout=settings.cognee_call_timeout_seconds,
    )


async def _load_runs(experiment: str) -> List[Dict[str, Any]]:
    if not settings.cognee_api_url:
        return []
    result = await cognee_client.list_runs(
        settings.cognee_api_url,
        experiment=experiment,
        timeout=settings.cognee_call_timeout_seconds,
    )
    runs = result.get("runs", []) if isinstance(result, dict) else []
    return runs if isinstance(runs, list) else []


async def _write_back(agent_type: str, experiment: str, content: str, metadata: Dict[str, Any]) -> None:
    """Best-effort write of an agent's finding into the graph. Never raises —
    a cognee outage should degrade the blackboard, not break the agent."""
    if not settings.cognee_api_url or not content:
        return
    try:
        await cognee_client.agent_finding(
            settings.cognee_api_url,
            agent_type=agent_type,
            experiment=experiment,
            content=content,
            metadata=metadata,
            timeout=settings.cognee_call_timeout_seconds,
        )
    except Exception as e:
        logger.warning("graph write-back failed for agent=%s experiment=%s: %s", agent_type, experiment, e)


async def on_run_remembered(run_data: Dict[str, Any]) -> None:
    """
    Called after a run is persisted. Fans out to all relevant subagents concurrently.
    """
    experiment = run_data.get("experiment", "")
    run_id = run_data.get("run_id", "")
    logger.info("Orchestrator: run_remembered  experiment=%s  run_id=%s", experiment, run_id)

    # Load all runs for the experiment once — agents share this context
    all_runs: List[Dict[str, Any]] = await _load_runs(experiment)
    prior_runs = [r for r in all_runs if r.get("run_id") != run_id]
    graph_context = await _read_graph_context(experiment)

    # Run all agents concurrently
    await asyncio.gather(
        _run_config_proposer(experiment, all_runs, graph_context),
        _run_triage(run_data, prior_runs, graph_context),
        _run_dataset_steward(experiment, all_runs, graph_context),
        # Literature agent runs every 5 runs to avoid LLM spam
        _run_literature_if_due(experiment, all_runs, graph_context),
        return_exceptions=True,
    )
    logger.info("Orchestrator: all agents completed for run %s", run_id)


async def on_report_requested(experiment: str) -> str:
    """Called by POST /api/agents/report. Returns the markdown report."""
    from app.agents.report import generate_report
    runs = await _load_runs(experiment)
    graph_context = await _read_graph_context(experiment)
    # generate_report() writes the report itself back into the graph.
    return await generate_report(experiment, runs, graph_context)


# ── Private helpers ────────────────────────────────────────────────────────

async def _run_config_proposer(experiment, all_runs, graph_context):
    try:
        from app.agents.config_proposer import propose_config
        result = await propose_config(experiment, all_runs, graph_context)
        if result:
            await _write_back("config_proposer", experiment, result.get("rationale", ""), result)
    except Exception as e:
        logger.error("config_proposer failed: %s", e)


async def _run_triage(run_data, prior_runs, graph_context):
    try:
        from app.agents.triage import triage_run
        result = await triage_run(run_data, prior_runs, graph_context)
        if result and result.get("anomaly_detected"):
            # Carry run_id in metadata so the card dedups per-run (each run can
            # legitimately raise its own anomaly) rather than per-experiment.
            result["run_id"] = run_data.get("run_id", "")
            await _write_back(
                "triage", run_data.get("experiment", ""), result.get("message", ""), result
            )
    except Exception as e:
        logger.error("triage failed: %s", e)


async def _run_dataset_steward(experiment, all_runs, graph_context):
    try:
        from app.agents.dataset_steward import check_dataset_health
        result = await check_dataset_health(experiment, all_runs, graph_context)
        if result and result.get("issues_detected"):
            await _write_back("dataset_steward", experiment, result.get("recommendation", ""), result)
    except Exception as e:
        logger.error("dataset_steward failed: %s", e)


async def _run_literature_if_due(experiment, all_runs, graph_context):
    # Only run every 5 completed runs to cap LLM cost
    completed = [r for r in all_runs if r.get("status") == "completed"]
    if len(completed) % 5 != 0 or len(completed) == 0:
        return
    try:
        from app.agents.literature import suggest_papers
        papers = await suggest_papers(experiment, all_runs, graph_context)
        if papers:
            import json
            content = json.dumps(papers, indent=2)
            await _write_back("literature", experiment, content, {"papers": papers})
    except Exception as e:
        logger.error("literature failed: %s", e)
