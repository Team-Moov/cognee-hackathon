"""
Config Proposer — suggests the next experiment configuration.
Reads all prior runs for the experiment, calls Groq to identify
unexplored parameter regions, and writes a dismissible suggestion card.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.utils import llm_generate_json

logger = logging.getLogger("groundhog.agents.config_proposer")

PROMPT = """You are an ML experiment design assistant.

Experiment: {experiment}

Derived insights from this project's run history (parameter sensitivity ranking
and the best config found per dataset), computed deterministically from all runs:
{insights_json}

Prior graph memory — decisions, hypotheses, and other agents' findings for
this experiment, recalled from the shared knowledge graph:
{graph_context}

Completed runs so far (JSON):
{runs_json}

Your task:
1. Use the parameter-sensitivity ranking: propose changes to the HIGH-impact
   parameters, and keep low-impact ones near their best-known value.
2. Identify unexplored regions of the hyperparameter space.
3. Suggest ONE specific next configuration to try.

Return a JSON object with exactly these keys:
{{
  "suggested_config": {{"key": "value", ...}},
  "rationale": "one paragraph explaining why this config makes sense",
  "expected_direction": "what metric you expect to improve and roughly by how much",
  "unexplored_regions": ["list of 2-3 unexplored areas worth investigating"]
}}

Be specific — include concrete hyperparameter values, not ranges.
Only return the JSON object, no markdown fences."""


async def propose_config(
    experiment: str, runs: List[Dict[str, Any]], graph_context: str = "",
    insights: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    if not runs:
        return None

    runs_for_prompt = [
        {
            "run_id": r.get("run_id"),
            "config": r.get("config", {}),
            "metrics": r.get("metrics", {}),
            "status": r.get("status"),
            "rationale": r.get("rationale", ""),
            "gpu_hours": r.get("gpu_hours"),
        }
        for r in runs
    ]

    insights_for_prompt = {
        "parameter_sensitivity": (insights or {}).get("parameter_sensitivity", []),
        "best_per_dataset": (insights or {}).get("best_per_dataset", []),
        "summary": (insights or {}).get("summary", ""),
    }

    prompt = PROMPT.format(
        experiment=experiment,
        insights_json=json.dumps(insights_for_prompt, indent=2),
        graph_context=graph_context or "(no prior graph memory yet)",
        runs_json=json.dumps(runs_for_prompt, indent=2),
    )

    try:
        result = await llm_generate_json(prompt)
        if isinstance(result, dict) and "suggested_config" in result:
            return result
        logger.warning("Config proposer returned unexpected shape: %s", result)
        return None
    except Exception as e:
        logger.error("Config proposer failed: %s", e)
        return None
