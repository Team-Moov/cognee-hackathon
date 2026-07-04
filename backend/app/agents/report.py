"""
Report Agent — assembles retrospectives and model cards on demand.
Traverses all lineage and run history for an experiment.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List

from app.utils import llm_generate
from app.config import settings
from app import cognee_client

logger = logging.getLogger("groundhog.agents.report")

PROMPT = """You are an ML research report writer.

Generate a comprehensive retrospective report for experiment "{experiment}".

All runs (sorted by timestamp):
{runs_json}

Prior graph memory — decisions, hypotheses, and other agents' findings for
this experiment, recalled from the shared knowledge graph:
{graph_context}

Your report should include:

## Executive Summary
What was attempted, what was the best result, how much compute was used.

## What Worked
Top 3 findings with specific config values and metrics.

## What Failed and Why
Failures, dead ends, and the lessons they encode.

## Key Decisions
Major turning points in the experiment — config changes, model switches, etc.

## Recommendations
Top 3 concrete next steps with specific parameter values to try.

## Model Card (if applicable)
Best model summary: architecture, training procedure, eval results, known limitations.

Use markdown formatting. Be specific — include actual metric values and config parameters."""


async def generate_report(
    experiment: str, runs: List[Dict[str, Any]], graph_context: str = "", project: str = None
) -> str:
    if not runs:
        return f"# {experiment}\n\nNo runs recorded yet."

    runs_sorted = sorted(runs, key=lambda r: r.get("timestamp", ""))
    runs_for_prompt = [
        {
            "run_id": r.get("run_id"),
            "config": r.get("config", {}),
            "metrics": r.get("metrics", {}),
            "status": r.get("status"),
            "rationale": r.get("rationale", ""),
            "gpu_hours": r.get("gpu_hours"),
            "timestamp": r.get("timestamp", ""),
        }
        for r in runs_sorted
    ]

    prompt = PROMPT.format(
        experiment=experiment,
        runs_json=json.dumps(runs_for_prompt, indent=2),
        graph_context=graph_context or "(no prior graph memory yet)",
    )

    try:
        report_text = await llm_generate(prompt)
        # Write the report itself back into the graph so a future "catch me
        # up" query or another agent's graph_context lookup can find it.
        if settings.cognee_api_url:
            try:
                await cognee_client.remember_agent_finding(
                    settings.cognee_api_url,
                    agent_type="report",
                    experiment=experiment,
                    content=report_text,
                    dataset=project,
                    timeout=settings.cognee_call_timeout_seconds,
                )
            except Exception as e:
                logger.warning("report: graph write-back failed (non-fatal): %s", e)
        return report_text
    except Exception as e:
        logger.error("Report agent failed: %s", e)
        return f"# {experiment} — Report generation failed\n\nError: {e}"
