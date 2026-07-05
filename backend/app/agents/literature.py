"""
Literature Agent — suggests relevant papers for the active research thread.
Uses Groq knowledge to propose papers matching the model/dataset/technique.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from app.utils import llm_generate_json, get_metric

logger = logging.getLogger("groundhog.agents.literature")

PROMPT = """You are an ML literature review assistant.

Experiment context:
- Experiment name: {experiment}
- Models used: {models}
- Optimizers used: {optimizers}
- Best result so far: {best_result}
- Researcher's notes: {rationale_summary}
- Prior graph memory (decisions, hypotheses, other agents' findings): {graph_context}

Suggest 3–5 highly relevant research papers that could:
1. Provide theoretical grounding for the current approach
2. Suggest specific improvements to try
3. Help explain surprising results (good or bad)

For each paper return:
{{
  "title": "exact paper title",
  "venue": "conference/journal and year",
  "key_insight": "one sentence on why this paper is relevant",
  "actionable_suggestion": "one specific thing the researcher could try based on this paper"
}}

Return a JSON array of these objects.
Only return the JSON array, no markdown fences."""


async def suggest_papers(
    experiment: str, runs: List[Dict[str, Any]], graph_context: str = ""
) -> Optional[List[Dict[str, Any]]]:
    if not runs:
        return None

    models = list({r.get("config", {}).get("model", "") for r in runs if r.get("config", {}).get("model")})
    optimizers = list({r.get("config", {}).get("optimizer", "") for r in runs if r.get("config", {}).get("optimizer")})
    completed = [r for r in runs if r.get("status") == "completed" and r.get("metrics")]
    
    best_result = "none yet"
    if completed:
        # Find run with best validation accuracy (alias-tolerant so val_acc /
        # val_accuracy / accuracy all count instead of silently scoring 0).
        best = max(completed, key=lambda r: get_metric(r.get("metrics", {}), "val_accuracy", 0) or 0)
        best_result = json.dumps(best.get("metrics", {}))

    rationale_summary = ". ".join(
        r.get("rationale", "") for r in runs[-5:] if r.get("rationale")
    )[:500]

    prompt = PROMPT.format(
        experiment=experiment,
        models=", ".join(models) or "unknown",
        optimizers=", ".join(optimizers) or "unknown",
        best_result=best_result,
        rationale_summary=rationale_summary or "No notes available",
        graph_context=graph_context or "(no prior graph memory yet)",
    )

    try:
        result = await llm_generate_json(prompt)
        if isinstance(result, list):
            return result
        return None
    except Exception as e:
        logger.error("Literature agent failed: %s", e)
        return None
