"""Shared utilities: config hashing, similarity, LLM + embedding wrappers."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import math
import re
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


# ── Groq generative model (chat completions) ───────────────────────────────

_groq_client = None


def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        from groq import Groq
        from app.config import settings
        key = settings.effective_llm_api_key
        if not key:
            raise RuntimeError("No Groq API key. Set GROQ_API_KEY in .env")
        _groq_client = Groq(api_key=key)
        logger.info("Groq client ready: %s", settings.effective_llm_model)
    return _groq_client


async def llm_generate(prompt: str) -> str:
    from app.config import settings
    client = _get_groq_client()
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=settings.effective_llm_model,
            messages=[{"role": "user", "content": prompt}],
        ),
    )
    return response.choices[0].message.content


async def llm_generate_json(prompt: str) -> Any:
    raw = await llm_generate(prompt)
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        logger.warning("Groq returned non-JSON, falling back to raw")
        return {"raw": text}


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+")


def _local_embed(text: str, dimensions: int, role: str) -> List[float]:
    if dimensions <= 0:
        raise ValueError("embedding dimensions must be positive")

    vector = [0.0] * dimensions
    tokens = _TOKEN_RE.findall(f"{role} {text.lower()}")
    if not tokens:
        return vector

    for token in tokens:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        weight = 1.0 + (len(token) / 16.0)
        vector[index] += sign * weight

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]

async def embed_text(text: str) -> Optional[List[float]]:
    """
    Embed text using a local deterministic hash embedding.
    Returns None gracefully if the input is empty.
    """
    if not text.strip():
        return None

    loop = asyncio.get_event_loop()
    from app.config import settings
    return await loop.run_in_executor(
        None,
        lambda: _local_embed(text, settings.embedding_dimensions, "document"),
    )


async def embed_query(text: str) -> Optional[List[float]]:
    """Embed a search query with the same local deterministic embedding path."""
    if not text.strip():
        return None

    loop = asyncio.get_event_loop()
    from app.config import settings
    return await loop.run_in_executor(
        None,
        lambda: _local_embed(text, settings.embedding_dimensions, "query"),
    )
