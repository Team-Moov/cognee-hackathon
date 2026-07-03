"""
Triage Agent — flags anomalies in new run results.
Checks for suspiciously good results (possible data leak), contradictions
with prior trends, and OOM/divergence patterns.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.utils import llm_generate_json

logger = logging.getLogger("groundhog.agents.triage")

PROMPT = """You are an ML results triage agent. A new run just completed.

New run (JSON):
{new_run_json}

Prior runs for this experiment (JSON):
{prior_runs_json}

Prior graph memory — decisions, hypotheses, and other agents' findings for
this experiment, recalled from the shared knowledge graph:
{graph_context}

Check for anomalies:
1. Is the new result suspiciously good compared to prior results (possible data leak, label leakage, or eval set contamination)?
2. Does the result contradict an established trend in the prior runs?
3. Are there any red flags (e.g. val_acc much higher than train_acc, loss is 0, metrics are missing)?
4. If the run failed — is there a pattern explaining why?

Return a JSON object with exactly these keys:
{{
  "anomaly_detected": true/false,
  "anomaly_type": "data_leak" | "contradicts_trend" | "suspicious_metrics" | "oom_pattern" | "divergence" | null,
  "severity": "high" | "medium" | "low" | null,
  "message": "one paragraph explaining the finding (or 'No anomalies detected.' if clean)",
  "recommendation": "what the researcher should check or do next"
}}

Only return the JSON object, no markdown fences."""


async def triage_run(
    new_run: Dict[str, Any], prior_runs: List[Dict[str, Any]], graph_context: str = ""
) -> Optional[Dict[str, Any]]:
    new_for_prompt = {
        "run_id": new_run.get("run_id"),
        "config": new_run.get("config", {}),
        "metrics": new_run.get("metrics", {}),
        "status": new_run.get("status"),
        "rationale": new_run.get("rationale", ""),
        "gpu_hours": new_run.get("gpu_hours"),
        "error_message": new_run.get("error_message", ""),
    }
    prior_for_prompt = [
        {
            "run_id": r.get("run_id"),
            "config": r.get("config", {}),
            "metrics": r.get("metrics", {}),
            "status": r.get("status"),
        }
        for r in prior_runs[-10:]  # last 10 to keep prompt size bounded
    ]

    prompt = PROMPT.format(
        new_run_json=json.dumps(new_for_prompt, indent=2),
        prior_runs_json=json.dumps(prior_for_prompt, indent=2),
        graph_context=graph_context or "(no prior graph memory yet)",
    )

    try:
        result = await llm_generate_json(prompt)
        if isinstance(result, dict) and "anomaly_detected" in result:
            return result
        return None
    except Exception as e:
        logger.error("Triage agent failed: %s", e)
        return None
