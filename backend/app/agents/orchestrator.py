"""
Orchestrator — event router for the blackboard architecture.

On every `run_remembered` event, the orchestrator fans out to whichever
subagents care about that event. No subagent talks to another directly —
all coordination flows through Firestore (the shared graph / blackboard).

This runs as a FastAPI BackgroundTask, so it never blocks the API response.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

logger = logging.getLogger("groundhog.orchestrator")


async def on_run_remembered(run_data: Dict[str, Any]) -> None:
    """
    Called after a run is persisted. Fans out to all relevant subagents concurrently.
    All agent outputs are written back to Firestore `agent_suggestions` collection.
    """
    experiment = run_data.get("experiment", "")
    run_id = run_data.get("run_id", "")
    logger.info("Orchestrator: run_remembered  experiment=%s  run_id=%s", experiment, run_id)

    from app.db.runs import get_runs_for_experiment
    from app.db.suggestions import save_suggestion

    # Load all runs for the experiment once — agents share this context
    all_runs: List[Dict[str, Any]] = await get_runs_for_experiment(experiment)
    prior_runs = [r for r in all_runs if r.get("run_id") != run_id]

    # Run all agents concurrently
    await asyncio.gather(
        _run_config_proposer(experiment, all_runs, save_suggestion),
        _run_triage(run_data, prior_runs, save_suggestion),
        _run_dataset_steward(experiment, all_runs, save_suggestion),
        # Literature agent runs every 5 runs to avoid LLM spam
        _run_literature_if_due(experiment, all_runs, save_suggestion),
        return_exceptions=True,
    )
    logger.info("Orchestrator: all agents completed for run %s", run_id)


async def on_report_requested(experiment: str) -> str:
    """Called by POST /api/agents/report. Returns the markdown report."""
    from app.db.runs import get_runs_for_experiment
    from app.agents.report import generate_report
    runs = await get_runs_for_experiment(experiment)
    return await generate_report(experiment, runs)


# ── Private helpers ────────────────────────────────────────────────────────

async def _run_config_proposer(experiment, all_runs, save):
    try:
        from app.agents.config_proposer import propose_config
        result = await propose_config(experiment, all_runs)
        if result:
            await save({
                "type": "config_proposer",
                "experiment": experiment,
                "title": "Next config suggestion",
                "content": result.get("rationale", ""),
                "metadata": result,
            })
    except Exception as e:
        logger.error("config_proposer failed: %s", e)


async def _run_triage(run_data, prior_runs, save):
    try:
        from app.agents.triage import triage_run
        result = await triage_run(run_data, prior_runs)
        if result and result.get("anomaly_detected"):
            await save({
                "type": "triage",
                "experiment": run_data.get("experiment", ""),
                "run_id": run_data.get("run_id", ""),
                "title": f"Anomaly: {result.get('anomaly_type', 'unknown')}",
                "content": result.get("message", ""),
                "metadata": result,
            })
    except Exception as e:
        logger.error("triage failed: %s", e)


async def _run_dataset_steward(experiment, all_runs, save):
    try:
        from app.agents.dataset_steward import check_dataset_health
        result = await check_dataset_health(experiment, all_runs)
        if result and result.get("issues_detected"):
            await save({
                "type": "dataset_steward",
                "experiment": experiment,
                "title": f"Dataset health: {result.get('overall_health', 'warning')}",
                "content": result.get("recommendation", ""),
                "metadata": result,
            })
    except Exception as e:
        logger.error("dataset_steward failed: %s", e)


async def _run_literature_if_due(experiment, all_runs, save):
    # Only run every 5 completed runs to cap LLM cost
    completed = [r for r in all_runs if r.get("status") == "completed"]
    if len(completed) % 5 != 0 or len(completed) == 0:
        return
    try:
        from app.agents.literature import suggest_papers
        papers = await suggest_papers(experiment, all_runs)
        if papers:
            import json
            await save({
                "type": "literature",
                "experiment": experiment,
                "title": f"Related papers ({len(papers)} suggestions)",
                "content": json.dumps(papers, indent=2),
                "metadata": {"papers": papers},
            })
    except Exception as e:
        logger.error("literature failed: %s", e)
