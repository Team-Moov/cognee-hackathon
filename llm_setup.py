"""
llm_setup.py — Single source of truth for configuring Cognee's LLM + embeddings.

Why this file exists
--------------------
The old main._configure_cognee() did:

    cognee.config.llm_config = {...}          # ❌ no such attribute / setter

which silently did NOTHING — cognee.config has no `llm_config` attribute, only
setter methods (set_llm_provider / set_llm_model / set_llm_api_key / ...). So the
whole provider configuration was a dead no-op and the pipeline only worked by
accident when litellm happened to pick a key up from the environment.

This module replaces that with real, verified configuration and makes Groundhog
runnable with ANY ONE of three chat-provider keys:

    GROUNDHOG_LLM_PROVIDER = groq | gemini | aimlapi

Embeddings are decoupled from the chat key on purpose. Groq has no embeddings
API at all, so if embeddings were tied to the chat provider, a Groq-only user
could never build the graph. Instead embeddings default to a LOCAL fastembed
model (BAAI/bge-small-en-v1.5, 384-dim) that needs no API key and runs offline.
That means a single Groq / Gemini / AI-ML key is enough for the entire system.

Override any of it via the environment (see .env.example).
"""

from __future__ import annotations

import logging
import os

import cognee

logger = logging.getLogger("groundhog.llm_setup")

# ---------------------------------------------------------------------------
# Chat / extraction provider presets (litellm naming, which is what cognee uses)
# ---------------------------------------------------------------------------
# Each preset returns (provider, model, api_key_env, endpoint).
#   - groq    : native litellm "groq/…" models
#   - gemini  : native litellm "gemini/…" models (Google AI Studio keys)
#   - aimlapi : AI/ML API (https://aimlapi.com) is OpenAI-compatible, so it is
#               wired as the "openai" provider pointed at their base URL.
# NOTE on provider names: Cognee's LLMProvider enum only accepts
#   openai | ollama | anthropic | custom | gemini | mistral | azure | bedrock | llama_cpp
# There is NO "groq" provider. Groq is reached through the "custom" adapter,
# which calls litellm.acompletion(model=..., api_base=endpoint). litellm natively
# routes a "groq/…" model string to Groq using GROQ_API_KEY, so we leave the
# endpoint empty. AI/ML API is an OpenAI-compatible service, so it is also the
# "custom" adapter but pointed at its base URL with an "openai/…" model string.
_PROVIDER_PRESETS = {
    "groq": {
        "provider": "custom",
        "default_model": "groq/llama-3.3-70b-versatile",
        "key_envs": ["GROQ_API_KEY"],
        "endpoint": "",
    },
    "gemini": {
        "provider": "gemini",
        "default_model": "gemini/gemini-2.0-flash",
        "key_envs": ["GEMINI_API_KEY", "GOOGLE_API_KEY"],
        "endpoint": "",
    },
    "aimlapi": {
        "provider": "custom",  # OpenAI-compatible base URL
        "default_model": "openai/gpt-4o-mini",
        "key_envs": ["AIMLAPI_API_KEY", "AIML_API_KEY"],
        "endpoint": "https://api.aimlapi.com/v1",
    },
}

_DEFAULT_EMBEDDING_PROVIDER = "fastembed"
_DEFAULT_EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
_DEFAULT_EMBEDDING_DIMS = 384


def _resolve_key(key_envs) -> str:
    for env in key_envs:
        val = os.getenv(env, "").strip()
        if val:
            return val
    return ""


def configure_cognee() -> dict:
    """
    Configure Cognee's LLM + embedding providers from environment variables.

    MUST be called once, before any cognee.add()/cognify()/recall()/remember()
    call. Returns a small dict describing what was configured (used by /health).
    """
    # Hackathon-friendly: turn off multi-tenant access control so the local
    # single-process server doesn't need a logged-in user for every call.
    # (Cognee 1.2 defaults this ON. Opt out unless the user set it explicitly.)
    os.environ.setdefault("ENABLE_BACKEND_ACCESS_CONTROL", "false")

    # Run Kuzu (graph) + LanceDB (vector) IN-PROCESS, not in a subprocess.
    # Cognee's default subprocess mode makes the write path (add/cognify) and the
    # read path (recall) contend for the same embedded-DB lock on Windows, which
    # surfaced as intermittent "Could not set lock on file …ladybug" errors on
    # query. With a single in-process owner there's one lock holder and the
    # contention disappears. Overridable via env if a user needs subprocess mode.
    try:
        graph_sub = os.getenv("COGNEE_GRAPH_SUBPROCESS", "false").strip().lower() in {"1", "true", "yes"}
        vector_sub = os.getenv("COGNEE_VECTOR_SUBPROCESS", "false").strip().lower() in {"1", "true", "yes"}
        cognee.config.set_graph_database_subprocess_enabled(graph_sub)
        cognee.config.set_vector_db_subprocess_enabled(vector_sub)
    except Exception as e:
        logger.warning("Could not set DB subprocess mode: %s", e)

    provider_key = os.getenv("GROUNDHOG_LLM_PROVIDER", "groq").strip().lower()
    preset = _PROVIDER_PRESETS.get(provider_key)
    if preset is None:
        logger.warning(
            "Unknown GROUNDHOG_LLM_PROVIDER=%r — falling back to 'groq'. "
            "Valid: groq | gemini | aimlapi",
            provider_key,
        )
        provider_key = "groq"
        preset = _PROVIDER_PRESETS["groq"]

    model = os.getenv("LLM_MODEL", "").strip() or preset["default_model"]
    api_key = _resolve_key(preset["key_envs"])
    endpoint = os.getenv("LLM_ENDPOINT", "").strip() or preset["endpoint"]

    if not api_key:
        logger.warning(
            "No API key found for provider '%s' (looked in %s). "
            "LLM-backed steps (cognify extraction, recall completion) WILL FAIL "
            "until you set one of those env vars. Embeddings still work locally.",
            provider_key,
            ", ".join(preset["key_envs"]),
        )

    # --- Configure the chat / extraction LLM via the REAL setters ----------
    cognee.config.set_llm_provider(preset["provider"])
    cognee.config.set_llm_model(model)
    if api_key:
        cognee.config.set_llm_api_key(api_key)
    if endpoint:
        cognee.config.set_llm_endpoint(endpoint)

    # Mirror into the environment too, so litellm's native provider routing
    # (GROQ_API_KEY for "groq/…", GEMINI_API_KEY for "gemini/…", OPENAI_API_KEY
    # + OPENAI_API_BASE for the OpenAI-compatible AI/ML API) all resolve.
    if api_key:
        os.environ["LLM_API_KEY"] = api_key
        os.environ.setdefault(preset["key_envs"][0], api_key)
        if provider_key == "groq":
            os.environ.setdefault("GROQ_API_KEY", api_key)
        elif provider_key == "gemini":
            os.environ.setdefault("GEMINI_API_KEY", api_key)
        elif provider_key == "aimlapi":
            os.environ.setdefault("OPENAI_API_KEY", api_key)
    os.environ["LLM_PROVIDER"] = preset["provider"]
    os.environ["LLM_MODEL"] = model
    if endpoint:
        os.environ["LLM_ENDPOINT"] = endpoint
        os.environ.setdefault("OPENAI_API_BASE", endpoint)

    # --- Configure embeddings (local by default, no key required) ----------
    emb_provider = os.getenv("EMBEDDING_PROVIDER", _DEFAULT_EMBEDDING_PROVIDER).strip()
    emb_model = os.getenv("EMBEDDING_MODEL", _DEFAULT_EMBEDDING_MODEL).strip()
    emb_dims_raw = os.getenv("EMBEDDING_DIMENSIONS", "").strip()
    emb_endpoint = os.getenv("EMBEDDING_ENDPOINT", "").strip()
    emb_key = os.getenv("EMBEDDING_API_KEY", "").strip()

    cognee.config.set_embedding_provider(emb_provider)
    cognee.config.set_embedding_model(emb_model)
    if emb_dims_raw:
        cognee.config.set_embedding_dimensions(int(emb_dims_raw))
    elif emb_provider == _DEFAULT_EMBEDDING_PROVIDER and emb_model == _DEFAULT_EMBEDDING_MODEL:
        cognee.config.set_embedding_dimensions(_DEFAULT_EMBEDDING_DIMS)
    if emb_endpoint:
        cognee.config.set_embedding_endpoint(emb_endpoint)
    if emb_key:
        cognee.config.set_embedding_api_key(emb_key)

    summary = {
        "llm_provider": preset["provider"],
        "llm_provider_alias": provider_key,
        "llm_model": model,
        "llm_endpoint": endpoint or "(default)",
        "llm_key_present": bool(api_key),
        "embedding_provider": emb_provider,
        "embedding_model": emb_model,
    }
    logger.info(
        "Cognee configured: chat=%s/%s (key=%s) embeddings=%s/%s",
        provider_key, model, "set" if api_key else "MISSING",
        emb_provider, emb_model,
    )
    return summary
