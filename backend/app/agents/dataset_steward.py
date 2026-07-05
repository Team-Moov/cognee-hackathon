"""
Dataset Steward — watches for drift, quality issues, and anomalous metric
variance that might indicate dataset problems rather than model problems.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.utils import llm_generate_json

logger = logging.getLogger("groundhog.agents.dataset_steward")

PROMPT = """You are an ML dataset quality steward.

Here are all runs for experiment "{experiment}" (JSON):
{runs_json}

Prior graph memory — decisions, hypotheses, and other agents' findings for
this experiment, recalled from the shared knowledge graph:
{graph_context}

Analyze for dataset health issues:
1. Is there high metric variance between runs with similar configs? (suggests label noise or unstable splits)
2. Is val_acc consistently much higher than train_acc? (suggests eval set contamination)
3. Are there runs where losses went to 0 or infinity? (suggests dataset bugs)
4. Do failed runs cluster around specific config choices? (suggests dataset-config incompatibility)
5. Any sign of distribution shift between early and recent runs?

Return a JSON object:
{{
  "issues_detected": true/false,
  "issues": [
    {{
      "type": "label_noise" | "eval_contamination" | "unstable_split" | "distribution_shift" | "other",
      "description": "what you observed",
      "severity": "high" | "medium" | "low",
      "affected_runs": ["run_id list"]
    }}
  ],
  "overall_health": "healthy" | "warning" | "critical",
  "recommendation": "what to investigate or fix"
}}

If no issues: return issues_detected=false, issues=[], overall_health="healthy".
Only return the JSON object, no markdown fences."""


async def check_dataset_health(
    experiment: str, runs: List[Dict[str, Any]], graph_context: str = ""
) -> Optional[Dict[str, Any]]:
    if len(runs) < 2:
        return None  # need at least 2 runs to detect patterns

    runs_for_prompt = [
        {
            "run_id": r.get("run_id"),
            "config": r.get("config", {}),
            "metrics": r.get("metrics", {}),
            "status": r.get("status"),
            "timestamp": r.get("timestamp", ""),
        }
        for r in runs
    ]

    prompt = PROMPT.format(
        experiment=experiment,
        runs_json=json.dumps(runs_for_prompt, indent=2),
        graph_context=graph_context or "(no prior graph memory yet)",
    )

    try:
        result = await llm_generate_json(prompt)
        if isinstance(result, dict) and "issues_detected" in result:
            return result
        return None
    except Exception as e:
        logger.error("Dataset steward failed: %s", e)
        return None
