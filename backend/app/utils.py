"""Shared utilities: config hashing, similarity, LLM + embedding wrappers."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("groundhog.utils")

# ── Config hashing ─────────────────────────────────────────────────────────

def _round_floats(obj: Any) -> Any:
    if isinstance(obj, float):
        return round(obj, 8)
    if isinstance(obj, dict):
        return {k: _round_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round_floats(i) for i in obj]
    return obj


def compute_config_hash(config: Dict[str, Any]) -> str:
    normalized = json.dumps(_round_floats(config), sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(normalized.encode()).hexdigest()


def config_similarity(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    pairs_a = set(f"{k}={_round_floats(v)}" for k, v in a.items())
    pairs_b = set(f"{k}={_round_floats(v)}" for k, v in b.items())
    union = pairs_a | pairs_b
    return len(pairs_a & pairs_b) / len(union) if union else 0.0


def generate_config_summary(config: Dict[str, Any]) -> str:
    primary = ["model", "architecture", "model_name", "optimizer",
               "learning_rate", "lr", "batch_size", "epochs", "num_epochs"]
    parts = [f"{k}={config[k]}" for k in primary if k in config]
    handled = set(primary)
    parts += [f"{k}={v}" for k, v in config.items() if k not in handled][:3]
    return "Config: " + ", ".join(parts) if parts else "Config: (empty)"


# ── Gemini generative model ────────────────────────────────────────────────

_gen_model = None


def _get_gen_model():
    global _gen_model
    if _gen_model is None:
        import google.generativeai as genai
        from app.config import settings
        key = settings.effective_llm_api_key
        if not key:
            raise RuntimeError("No LLM API key. Set LLM_API_KEY in .env")
        genai.configure(api_key=key)
        _gen_model = genai.GenerativeModel(settings.effective_llm_model)
        logger.info("Gemini generative model ready: %s", settings.effective_llm_model)
    return _gen_model


async def llm_generate(prompt: str) -> str:
    model = _get_gen_model()
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, lambda: model.generate_content(prompt))
    return response.text


async def llm_generate_json(prompt: str) -> Any:
    raw = await llm_generate(prompt)
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Gemini returned non-JSON, falling back to raw")
        return {"raw": text}


# ── Gemini embedding (text-embedding-004, 768-dim) ─────────────────────────

async def embed_text(text: str) -> Optional[List[float]]:
    """
    Embed text using Gemini text-embedding-004 (768 dim).
    Returns None gracefully if no API key is configured.
    """
    from app.config import settings
    key = settings.effective_llm_api_key
    if not key:
        return None

    import google.generativeai as genai
    genai.configure(api_key=key)

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: genai.embed_content(
                model="models/text-embedding-004",
                content=text,
                task_type="RETRIEVAL_DOCUMENT",
            ),
        )
        return result["embedding"]
    except Exception as e:
        logger.warning("embed_text failed: %s", e)
        return None


async def embed_query(text: str) -> Optional[List[float]]:
    """Embed a search query (different task_type for better retrieval)."""
    from app.config import settings
    key = settings.effective_llm_api_key
    if not key:
        return None

    import google.generativeai as genai
    genai.configure(api_key=key)

    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(
            None,
            lambda: genai.embed_content(
                model="models/text-embedding-004",
                content=text,
                task_type="RETRIEVAL_QUERY",
            ),
        )
        return result["embedding"]
    except Exception as e:
        logger.warning("embed_query failed: %s", e)
        return None
