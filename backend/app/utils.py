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


# Canonical config hashing — MUST match memory.py on the Cognee server so the
# run_id computed here lines up with the Pre-flight Guard's hash. See
# memory.canonical_config for the rationale (strip noise keys, normalise aliases).
CONFIG_NOISE_KEYS = {
    "seed", "random_seed", "gpu_id", "gpu", "device", "devices", "local_rank",
    "rank", "world_size", "num_workers", "workers", "output_dir", "out_dir",
    "save_dir", "log_dir", "checkpoint_dir", "run_name", "name", "run_id",
    "id", "timestamp", "created_at", "date", "wandb", "wandb_project",
    "wandb_entity", "notes", "tags", "group", "resume", "verbose", "debug",
    "pin_memory", "prefetch_factor", "persistent_workers",
}
CONFIG_KEY_ALIASES = {
    "lr": "learning_rate", "model_name": "model", "architecture": "model",
    "arch": "model", "num_epochs": "epochs", "n_epochs": "epochs",
    "bs": "batch_size", "opt": "optimizer", "wd": "weight_decay",
}


def canonical_config(config: Dict[str, Any], significant_keys: Optional[List[str]] = None) -> Dict[str, Any]:
    sig = {k.lower() for k in significant_keys} if significant_keys else None
    out: Dict[str, Any] = {}
    for raw_key, value in config.items():
        # Drop underscore-prefixed bookkeeping keys (e.g. _wandb_url, _runtime) —
        # never hyperparameters, so they must not affect the config hash.
        if str(raw_key).startswith("_"):
            continue
        key = CONFIG_KEY_ALIASES.get(str(raw_key).lower(), str(raw_key).lower())
        if sig is not None:
            if key not in sig and str(raw_key).lower() not in sig:
                continue
        elif key in CONFIG_NOISE_KEYS:
            continue
        if isinstance(value, dict):
            value = canonical_config(value, significant_keys)
        out[key] = value
    return _round_floats(out)


def compute_config_hash(config: Dict[str, Any], significant_keys: Optional[List[str]] = None) -> str:
    normalized = json.dumps(canonical_config(config, significant_keys), sort_keys=True, ensure_ascii=True, default=str)
    return hashlib.sha256(normalized.encode()).hexdigest()


def config_similarity(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    pairs_a = set(f"{k}={_round_floats(v)}" for k, v in a.items())
    pairs_b = set(f"{k}={_round_floats(v)}" for k, v in b.items())
    union = pairs_a | pairs_b
    return len(pairs_a & pairs_b) / len(union) if union else 0.0


_METRIC_ALIASES = {
    "val_accuracy": ["val_accuracy", "val_acc", "validation_accuracy", "accuracy", "acc"],
    "val_loss": ["val_loss", "validation_loss", "loss"],
    "train_accuracy": ["train_accuracy", "train_acc"],
}


def get_metric(metrics: Dict[str, Any], name: str, default: Any = None) -> Any:
    """
    Read a metric by canonical name, tolerating common aliases.

    Ingestion, W&B, and hand-written runs disagree on naming (val_acc vs
    val_accuracy vs accuracy). Agents should read through this so "best run"
    selection doesn't silently see 0 because of a key mismatch.
    """
    for key in _METRIC_ALIASES.get(name, [name]):
        if key in metrics and metrics[key] is not None:
            return metrics[key]
    return default


def generate_config_summary(config: Dict[str, Any]) -> str:
    primary = ["model", "architecture", "model_name", "optimizer",
               "learning_rate", "lr", "batch_size", "epochs", "num_epochs"]
    parts = [f"{k}={config[k]}" for k in primary if k in config]
    handled = set(primary)
    parts += [f"{k}={v}" for k, v in config.items() if k not in handled][:3]
    return "Config: " + ", ".join(parts) if parts else "Config: (empty)"


# ── Multi-provider generative model (chat completions) via litellm ──────────
# Routed through litellm so the subagents work with any one of groq / gemini /
# aimlapi keys — the provider is chosen by GROUNDHOG_LLM_PROVIDER (see
# app.config.Settings.resolve_llm), matching the root cognee server's provider.


async def llm_generate(prompt: str) -> str:
    import litellm
    from app.config import settings

    cfg = settings.resolve_llm()
    if not cfg.get("api_key"):
        raise RuntimeError(
            f"No API key for provider '{settings.groundhog_llm_provider}'. "
            "Set the matching *_API_KEY in .env."
        )

    kwargs = {
        "model": cfg["model"],
        "api_key": cfg["api_key"],
        "messages": [{"role": "user", "content": prompt}],
    }
    if cfg.get("api_base"):
        kwargs["api_base"] = cfg["api_base"]

    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(None, lambda: litellm.completion(**kwargs))
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
        logger.warning("LLM returned non-JSON, falling back to raw: %s", text[:200])
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

    loop = asyncio.get_running_loop()
    from app.config import settings
    return await loop.run_in_executor(
        None,
        lambda: _local_embed(text, settings.embedding_dimensions, "document"),
    )


async def embed_query(text: str) -> Optional[List[float]]:
    """Embed a search query with the same local deterministic embedding path."""
    if not text.strip():
        return None

    loop = asyncio.get_running_loop()
    from app.config import settings
    return await loop.run_in_executor(
        None,
        lambda: _local_embed(text, settings.embedding_dimensions, "query"),
    )
