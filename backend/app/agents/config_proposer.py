"""
Config Proposer — suggests the next experiment configuration.
Reads all prior runs for the experiment, calls Gemini to identify
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

Completed runs so far (JSON):
{runs_json}

Your task:
1. Identify unexplored regions of the hyperparameter space.
2. Look at which changes improved performance and which hurt it.
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


async def propose_config(experiment: str, runs: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
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

    prompt = PROMPT.format(
        experiment=experiment,
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
