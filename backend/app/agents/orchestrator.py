"""
Orchestrator — event router for the blackboard architecture.

On every `run_remembered` event, the orchestrator fans out to whichever
subagents care about that event. No subagent talks to another directly —
coordination flows through two shared stores with different jobs:

  - Postgres `agent_suggestions` — the UI-facing cache of dismissible cards.
  - The cognee graph — the actual blackboard. Each agent READS prior graph
    context (decisions, hypotheses, other agents' findings) before reasoning,
    and WRITES its own finding back via remember_agent_finding(), so the next
    agent — or a human via the NL query bar — can recall() it later. This is
    what makes "the graph is the coordination layer" (plan Section 7) true,
    instead of every agent only ever seeing its own private Postgres row.

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


async def _write_back(agent_type: str, experiment: str, content: str, metadata: Dict[str, Any]) -> None:
    """Best-effort write of an agent's finding into the graph. Never raises —
    a cognee outage should degrade the blackboard, not break the agent."""
    if not settings.cognee_api_url or not content:
        return
    try:
        await cognee_client.remember_agent_finding(
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

    from app.db.runs import get_runs_for_experiment
    from app.db.suggestions import save_suggestion

    # Load all runs for the experiment once — agents share this context
    all_runs: List[Dict[str, Any]] = await get_runs_for_experiment(experiment)
    prior_runs = [r for r in all_runs if r.get("run_id") != run_id]
    graph_context = await _read_graph_context(experiment)

    # Run all agents concurrently
    await asyncio.gather(
        _run_config_proposer(experiment, all_runs, graph_context, save_suggestion),
        _run_triage(run_data, prior_runs, graph_context, save_suggestion),
        _run_dataset_steward(experiment, all_runs, graph_context, save_suggestion),
        # Literature agent runs every 5 runs to avoid LLM spam
        _run_literature_if_due(experiment, all_runs, graph_context, save_suggestion),
        return_exceptions=True,
    )
    logger.info("Orchestrator: all agents completed for run %s", run_id)


async def on_report_requested(experiment: str) -> str:
    """Called by POST /api/agents/report. Returns the markdown report."""
    from app.db.runs import get_runs_for_experiment
    from app.agents.report import generate_report
    runs = await get_runs_for_experiment(experiment)
    graph_context = await _read_graph_context(experiment)
    # generate_report() writes the report itself back into the graph.
    return await generate_report(experiment, runs, graph_context)


# ── Private helpers ────────────────────────────────────────────────────────

async def _run_config_proposer(experiment, all_runs, graph_context, save):
    try:
        from app.agents.config_proposer import propose_config
        result = await propose_config(experiment, all_runs, graph_context)
        if result:
            await save({
                "type": "config_proposer",
                "experiment": experiment,
                "title": "Next config suggestion",
                "content": result.get("rationale", ""),
                "metadata": result,
            })
            await _write_back("config_proposer", experiment, result.get("rationale", ""), result)
    except Exception as e:
        logger.error("config_proposer failed: %s", e)


async def _run_triage(run_data, prior_runs, graph_context, save):
    try:
        from app.agents.triage import triage_run
        result = await triage_run(run_data, prior_runs, graph_context)
        if result and result.get("anomaly_detected"):
            await save({
                "type": "triage",
                "experiment": run_data.get("experiment", ""),
                "run_id": run_data.get("run_id", ""),
                "title": f"Anomaly: {result.get('anomaly_type', 'unknown')}",
                "content": result.get("message", ""),
                "metadata": result,
            })
            await _write_back(
                "triage", run_data.get("experiment", ""), result.get("message", ""), result
            )
    except Exception as e:
        logger.error("triage failed: %s", e)


async def _run_dataset_steward(experiment, all_runs, graph_context, save):
    try:
        from app.agents.dataset_steward import check_dataset_health
        result = await check_dataset_health(experiment, all_runs, graph_context)
        if result and result.get("issues_detected"):
            await save({
                "type": "dataset_steward",
                "experiment": experiment,
                "title": f"Dataset health: {result.get('overall_health', 'warning')}",
                "content": result.get("recommendation", ""),
                "metadata": result,
            })
            await _write_back("dataset_steward", experiment, result.get("recommendation", ""), result)
    except Exception as e:
        logger.error("dataset_steward failed: %s", e)


async def _run_literature_if_due(experiment, all_runs, graph_context, save):
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
            await save({
                "type": "literature",
                "experiment": experiment,
                "title": f"Related papers ({len(papers)} suggestions)",
                "content": content,
                "metadata": {"papers": papers},
            })
            await _write_back("literature", experiment, content, {"papers": papers})
    except Exception as e:
        logger.error("literature failed: %s", e)
