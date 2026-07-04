"""
memory.py — Groundhog Core Memory Wrappers

All calls to cognee go through these functions. API route handlers must NOT
call cognee directly — always use these wrappers so behavior stays
consistent and testable.

SDK usage notes (read before touching this file):

  - This module uses cognee's native "V2 memory API" — cognee.remember(),
    cognee.recall(), cognee.improve(), cognee.forget() — instead of manually
    recreating that behavior on top of the lower-level add()/cognify()/
    search()/prune() primitives. remember()/recall()/improve()/forget() are
    real functions exported from cognee's top-level package (cognee>=1.2),
    not just conceptual names from our own plan.

  - The ONE place we still drop down to add()+cognify() directly is ontology-
    grounded ingestion: cognify()'s `ontology_file_path` kwarg is not forwarded
    by remember()'s kwarg router, so grounded runs are ingested by manually
    sequencing add() -> cognify(ontology_file_path=...) -> improve() — the
    same three steps remember() performs internally, with the ontology hook
    added in the middle. See _remember_with_ontology() below.

  - Experiment/thread/config scoping uses cognee's native `node_set` (at
    write time) and `node_name` (at read time) tagging instead of a bespoke
    "one cognee dataset per experiment" scheme.

  - Private/exploratory memory uses cognee's native `session_id` mechanism
    (session_id on remember()/recall()) instead of a hand-rolled private
    dataset + copy-on-promote scheme. Promotion is a real operation:
    cognee.improve(dataset=..., session_ids=[...]) bridges session content
    into the permanent graph.

Functions:
  - remember_run        : ingest a full run document into the graph
  - check_config        : Pre-flight Guard — exact tag match + semantic fallback
  - query_memory        : free-form NL question answering with graph recall
  - improve_memory      : wraps cognee.improve() for graph enrichment
  - forget_stale        : wraps cognee.forget() for noise reduction
  - promote_to_shared   : bridges session memory into the shared graph
  - remember_agent_finding : subagent write-back into the shared graph (blackboard)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import cognee
from cognee import SearchType

from ontology.ml_ontology import ONTOLOGY_FILE_PATH

logger = logging.getLogger("groundhog.memory")

# Whether to also persist typed DataPoint nodes + edges (schema.py) alongside the
# text document. Defaults on: it runs on local embeddings (no LLM/key needed) and
# is what makes the typed schema a real, traversable graph instead of dead code.
_TYPED_NODES = os.getenv("GROUNDHOG_TYPED_NODES", "true").strip().lower() in {"1", "true", "yes"}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _round_floats(obj):
    if isinstance(obj, float):
        return round(obj, 8)
    if isinstance(obj, dict):
        return {k: _round_floats(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round_floats(i) for i in obj]
    return obj


# --- Canonical config hashing (Pre-flight Guard robustness) -----------------
# Real-world configs carry noise that does NOT change "have I tried this?":
# seeds, device ids, output paths, run names, worker counts, timestamps, W&B
# bookkeeping. Hashing the raw dict makes two logically-identical experiments
# hash differently (seed=1 vs seed=2) so the Guard falsely says "never tried".
# We strip that noise and normalise key aliases before hashing so the Guard
# matches the configs researchers actually run.

CONFIG_NOISE_KEYS = {
    "seed", "random_seed", "gpu_id", "gpu", "device", "devices", "local_rank",
    "rank", "world_size", "num_workers", "workers", "output_dir", "out_dir",
    "save_dir", "log_dir", "checkpoint_dir", "run_name", "name", "run_id",
    "id", "timestamp", "created_at", "date", "wandb", "wandb_project",
    "wandb_entity", "notes", "tags", "group", "resume", "verbose", "debug",
    "pin_memory", "prefetch_factor", "persistent_workers",
}

CONFIG_KEY_ALIASES = {
    "lr": "learning_rate",
    "model_name": "model",
    "architecture": "model",
    "arch": "model",
    "num_epochs": "epochs",
    "n_epochs": "epochs",
    "bs": "batch_size",
    "opt": "optimizer",
    "wd": "weight_decay",
}


def canonical_config(
    params: Dict[str, Any],
    significant_keys: Optional[List[str]] = None,
    ignore_keys: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Reduce a config to only the parameters that define the experiment.

    - If significant_keys is given, keep ONLY those (after alias-normalising).
    - Otherwise drop CONFIG_NOISE_KEYS (+ any caller-supplied ignore_keys) and
      normalise aliases (lr -> learning_rate, model_name -> model, ...).
    Nested dicts are canonicalised recursively; floats are rounded.
    """
    ignore = set(CONFIG_NOISE_KEYS) | {(k or "").lower() for k in (ignore_keys or [])}
    sig = {(k or "").lower() for k in significant_keys} if significant_keys else None

    out: Dict[str, Any] = {}
    for raw_key, value in params.items():
        key = CONFIG_KEY_ALIASES.get(str(raw_key).lower(), str(raw_key).lower())
        if sig is not None:
            if key not in sig and str(raw_key).lower() not in sig:
                continue
        elif key in ignore:
            continue
        if isinstance(value, dict):
            value = canonical_config(value, ignore_keys=ignore_keys)
        out[key] = value
    return _round_floats(out)


def _normalize_config(params: Dict[str, Any],
                      significant_keys: Optional[List[str]] = None) -> str:
    """Deterministic JSON serialization of the CANONICAL config for hashing."""
    normalized = canonical_config(params, significant_keys=significant_keys)
    return json.dumps(normalized, sort_keys=True, ensure_ascii=True, default=str)


def compute_config_hash(params: Dict[str, Any],
                        significant_keys: Optional[List[str]] = None) -> str:
    """
    SHA-256 hash of the canonicalised config: identical *meaningful*
    hyperparameters produce the same hash even if noise fields (seed, paths,
    run names) or key aliases (lr vs learning_rate) differ.
    """
    normalized_str = _normalize_config(params, significant_keys=significant_keys)
    return hashlib.sha256(normalized_str.encode()).hexdigest()


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    """Lowercase, punctuation-stripped slug safe for use inside a node_set tag."""
    text = (text or "unknown").strip().lower()
    text = _SLUG_RE.sub("_", text).strip("_")
    return text or "unknown"


def _node_set_for_run(
    experiment_name: str,
    thread_name: str,
    config_hash: str,
    status: str,
) -> List[str]:
    """
    Native cognee tagging scheme for a run.

    These become first-class graph nodes after cognify()/remember() runs,
    letting recall() scope queries to one experiment/thread via `node_name`,
    and letting check_config() do an exact tag lookup on `confighash:<hash>`
    instead of hoping the hash string shows up verbatim in completion text.
    """
    return [
        f"experiment:{_slug(experiment_name)}",
        f"thread:{_slug(thread_name)}",
        f"confighash:{config_hash}",
        f"status:{_slug(status)}",
    ]


def generate_config_summary(params: Dict[str, Any]) -> str:
    """Short natural-language description of a config dict — this is what gets embedded."""
    parts = []
    model = params.get("model") or params.get("architecture") or params.get("model_name")
    if model:
        parts.append(f"model={model}")
    optimizer = params.get("optimizer")
    if optimizer:
        parts.append(f"optimizer={optimizer}")
    lr = params.get("learning_rate") or params.get("lr")
    if lr is not None:
        parts.append(f"lr={lr}")
    bs = params.get("batch_size")
    if bs is not None:
        parts.append(f"batch_size={bs}")
    epochs = params.get("epochs") or params.get("num_epochs")
    if epochs is not None:
        parts.append(f"epochs={epochs}")
    handled = {"model", "architecture", "model_name", "optimizer", "learning_rate",
               "lr", "batch_size", "epochs", "num_epochs"}
    extras = [f"{k}={v}" for k, v in params.items() if k not in handled]
    parts.extend(extras[:4])
    return "Config: " + ", ".join(parts) if parts else "Config: (empty)"


def generate_result_summary(metrics: Dict[str, Any], status: str, rationale: str = "") -> str:
    """Short NL description of a result — supports negative-result recall via status text."""
    parts = []
    if status != "completed":
        parts.append(f"Run {status}.")
    for key in ["val_accuracy", "val_loss", "test_accuracy", "test_loss",
                "f1_score", "mAP", "perplexity"]:
        val = metrics.get(key)
        if val is not None:
            parts.append(f"{key}={val:.4f}" if isinstance(val, float) else f"{key}={val}")
    if rationale:
        parts.append(f"Researcher note: {rationale[:200]}")
    if not parts:
        parts.append("No metrics recorded.")
    return "Result: " + " | ".join(parts)


def _build_run_document(run_data: Dict[str, Any], config_hash: str, config_summary: str,
                         result_summary: str, status: str, rationale: str) -> str:
    """Rich structured text document — cognee extracts entities/relationships from this."""
    result_metrics = run_data.get("result_metrics", {})
    doc_lines = [
        f"## Run Record — {datetime.utcnow().isoformat()}",
        f"**Experiment:** {run_data.get('experiment_name', 'unnamed')}",
        f"**Description:** {run_data.get('experiment_description', '')}",
        f"**Owner:** {run_data.get('owner', 'unknown')}",
        f"**Research Thread:** {run_data.get('thread_name', 'default')}",
        f"**Hypothesis:** {run_data.get('hypothesis', '')}",
        "",
        f"### Config (hash: {config_hash})",
        config_summary,
        f"Raw parameters: {json.dumps(run_data.get('config_params', {}), sort_keys=True)}",
        "",
        "### Dataset",
        f"Name: {run_data.get('dataset_name_label', 'unknown')}",
        f"Version: {run_data.get('dataset_version', 'v1')}",
        f"Preprocessing: {run_data.get('preprocessing_notes', '')}",
        f"Split rationale: {run_data.get('split_rationale', '')}",
        f"Quality issues: {run_data.get('quality_issues', '')}",
        "",
        f"### Result (status: {status})",
        result_summary,
        f"Metrics: {json.dumps(result_metrics, sort_keys=True)}",
        f"GPU hours: {run_data.get('gpu_hours', 'N/A')}",
        f"Wall clock seconds: {run_data.get('wall_clock_seconds', 'N/A')}",
        "",
        "### Rationale",
        rationale or "(no rationale provided)",
        "",
        "### Provenance",
        f"Git commit: {run_data.get('git_commit', 'unknown')}",
        f"Config hash: {config_hash}",
        f"Derived from config hash: {run_data.get('derived_from_config_hash', 'none')}",
    ]
    return "\n".join(doc_lines)


async def _write_typed_nodes(
    run_data: Dict[str, Any],
    config_hash: str,
    config_summary: str,
    result_summary: str,
    status: str,
    artifact_dicts: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Persist the run as real typed DataPoint nodes (schema.py) with real edges,
    via cognee.tasks.storage.add_data_points().

    This is the fix for the "typed schema is dead code" gap: previously the 9
    DataPoint classes were only ever used in a test, and the actual graph was
    whatever the LLM happened to extract from a markdown blob. Now every run
    also lands as an enforced, typed subgraph:

        Experiment <- belongs_to - ResearchThread
        Config     - belongs_to  -> ResearchThread
        Result     - produced_by -> Config
        Result     - used_dataset-> Dataset
        Artifact   - produced_by -> Result

    Runs entirely on local embeddings (embed_triplets=False → no LLM call), so
    it works with any provider key. Best-effort: any failure is logged and does
    NOT abort ingestion (the text path already succeeded by the time we get here).
    """
    from schema import (
        Experiment, ResearchThread, Config, Dataset, Result, Artifact,
    )
    from cognee.tasks.storage import add_data_points

    exp = Experiment(
        name=run_data.get("experiment_name", "unnamed"),
        description=run_data.get("experiment_description", "") or run_data.get("experiment_name", "unnamed"),
        owner=run_data.get("owner", "unknown"),
    )
    thread = ResearchThread(
        name=run_data.get("thread_name", "default"),
        hypothesis_summary=run_data.get("hypothesis", "") or "default thread",
        belongs_to=exp,
    )
    cfg = Config(
        parameters=run_data.get("config_params", {}),
        summary_text=config_summary,
        config_hash=config_hash,
        belongs_to=thread,
    )
    dataset = Dataset(
        name=run_data.get("dataset_name_label", "unknown"),
        version=run_data.get("dataset_version", "v1"),
        preprocessing_notes=run_data.get("preprocessing_notes", ""),
        split_rationale=run_data.get("split_rationale", ""),
        quality_issues=run_data.get("quality_issues", ""),
    )
    result = Result(
        metrics=run_data.get("result_metrics", {}),
        gpu_hours=run_data.get("gpu_hours"),
        wall_clock_seconds=run_data.get("wall_clock_seconds"),
        status=status,
        summary_text=result_summary,
        produced_by=cfg,
        used_dataset=dataset,
        belongs_to=thread,
    )
    nodes: List[Any] = [exp, thread, cfg, dataset, result]
    for art in artifact_dicts:
        nodes.append(Artifact(
            file_path=art["file_path"],
            artifact_type=art.get("artifact_type", "other"),
            description=art.get("description", ""),
            exists_on_disk=art.get("exists_on_disk", True),
            produced_by=result,
        ))

    await add_data_points(nodes, embed_triplets=False)
    return {
        "typed_nodes_written": len(nodes),
        "result_node_id": str(result.id),
        "config_node_id": str(cfg.id),
    }


def _scan_artifacts(directory: str) -> List[str]:
    """Walk a directory and return all file paths found."""
    paths = []
    for root, _dirs, files in os.walk(directory):
        for fname in files:
            paths.append(os.path.abspath(os.path.join(root, fname)))
    return paths


def _result_to_text(result_obj: Any) -> str:
    """Best-effort text extraction from a cognee RecallResponse/search result item."""
    if isinstance(result_obj, str):
        return result_obj
    if hasattr(result_obj, "content"):
        return str(getattr(result_obj, "content"))
    if hasattr(result_obj, "text"):
        return str(getattr(result_obj, "text"))
    if isinstance(result_obj, dict):
        return json.dumps(result_obj, default=str)
    return str(result_obj)


def _extract_result_snippet(result_obj: Any) -> Dict[str, Any]:
    """Extract a clean snippet dict from a cognee recall() result item."""
    if isinstance(result_obj, dict):
        return result_obj
    if hasattr(result_obj, "model_dump"):
        try:
            return result_obj.model_dump(mode="json")
        except Exception:
            pass
    if hasattr(result_obj, "__dict__"):
        return {k: str(v) for k, v in vars(result_obj).items() if not k.startswith("_")}
    return {"raw": str(result_obj)[:500]}


def _rough_similarity(a: str, b: str) -> float:
    """Token overlap (Jaccard) — display-only heuristic, used solely by find_file."""
    tokens_a = set(a.lower().split())
    tokens_b = set(b.lower().split())
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


def _prior_from_index(config_hash: str) -> Optional[Dict[str, Any]]:
    """
    Return a clean prior-run dict from the structured index for an exact
    config-hash match, or None if the run isn't indexed. Gives the Pre-flight
    Guard real fields (run_id, metrics, gpu_hours, rationale) rather than a
    raw recall snippet.
    """
    try:
        import run_index
        run = run_index.get_run(config_hash)
    except Exception:
        return None
    if not run:
        return None
    return {
        "id": run.get("run_id"),
        "run_id": run.get("run_id"),
        "experiment": run.get("experiment"),
        "config": run.get("config", {}),
        "metrics": run.get("metrics", {}),
        "status": run.get("status", "completed"),
        "gpu_hours": run.get("gpu_hours"),
        "rationale": run.get("rationale", ""),
        "timestamp": run.get("timestamp", ""),
    }


def _extract_recall_score(result_obj: Any) -> Optional[float]:
    """
    Pull cognee's real vector-similarity score off a recall() hit.

    CHUNKS/graph recall entries carry a `score` field (0..1, higher = closer).
    This is the actual embedding similarity from the vector store — used instead
    of the old token-overlap guess so the Pre-flight Guard reports a meaningful
    number. Returns None when no real score is present.
    """
    for attr in ("score", "similarity", "distance"):
        val = getattr(result_obj, attr, None)
        if val is None and isinstance(result_obj, dict):
            val = result_obj.get(attr)
        if isinstance(val, (int, float)):
            score = float(val)
            # `distance` is inverted (lower = closer); convert to a similarity.
            if attr == "distance":
                score = max(0.0, 1.0 - score)
            return round(score, 3)
    return None


# ---------------------------------------------------------------------------
# remember_run
# ---------------------------------------------------------------------------


async def remember_run(
    run_data: Dict[str, Any],
    dataset_name: str = "main_dataset",
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Ingest a full run document into the Cognee graph.

    If `session_id` is set, this is a private/exploratory write: it goes into
    cognee's session cache (fast, cheap) rather than the permanent graph, and
    self-improvement is left on so it bridges into the permanent graph in the
    background. Call promote_to_shared(session_id=..., to_dataset=dataset_name)
    later to make it explicitly shared team memory — see Section 4.5 of the
    plan ("private vs shared memory with an explicit promote action").

    Without `session_id`, this is a permanent/shared write, tagged with
    node_set=[experiment, thread, confighash, status] so later recall() calls
    can scope to a slice of the graph via node_name instead of a fuzzy text
    search, and ontology-grounded via cognify(ontology_file_path=...) when the
    ontology file is present.

    Expected run_data keys — see RememberRequest in main.py for the full list.

    Returns dict with config_hash, summaries, artifact paths, and cognee's own
    RememberResult/pipeline info for debugging.
    """
    start = time.time()
    config_params = run_data.get("config_params", {})
    if not isinstance(config_params, dict):
        raise ValueError("config_params must be a dict")

    significant_keys = run_data.get("significant_keys")
    config_hash = compute_config_hash(config_params, significant_keys)
    config_summary = generate_config_summary(config_params)
    result_metrics = run_data.get("result_metrics", {})
    status = run_data.get("status", "completed")
    rationale = run_data.get("rationale", "")
    result_summary = generate_result_summary(result_metrics, status, rationale)

    document = _build_run_document(run_data, config_hash, config_summary, result_summary,
                                    status, rationale)

    node_set = _node_set_for_run(
        experiment_name=run_data.get("experiment_name", "unnamed"),
        thread_name=run_data.get("thread_name", "default"),
        config_hash=config_hash,
        status=status,
    )

    # --- Artifact scanning (filesystem side-effect, unrelated to cognee) ---
    artifact_dicts: List[Dict[str, Any]] = []
    output_dir = run_data.get("output_dir")
    if output_dir and os.path.isdir(output_dir):
        artifact_dicts = scan_and_register_artifacts(output_dir, result_id=config_hash)
        logger.info("Scanned %d artifacts from %s", len(artifact_dicts), output_dir)
    artifact_paths = [a["file_path"] for a in artifact_dicts]

    # --- Typed DataPoint graph (schema.py) FIRST — real nodes + edges, local ---
    # embeddings, no LLM needed. Done before the text/LLM path so the enforced
    # structured graph is captured even if LLM extraction later fails (e.g. no
    # key). This is what turns schema.py into a real, traversable graph.
    typed_result: Dict[str, Any] = {"typed_nodes_written": 0}
    if _TYPED_NODES and not session_id:
        try:
            typed_result = await _write_typed_nodes(
                run_data, config_hash, config_summary, result_summary, status, artifact_dicts
            )
            logger.info("Wrote %d typed nodes for config_hash=%s",
                        typed_result.get("typed_nodes_written", 0), config_hash[:12])
        except Exception as e:
            logger.warning("Typed-node write failed: %s", e)
            typed_result = {"typed_nodes_written": 0, "error": str(e)}

    # --- Text document → cognee (semantic layer; needs the LLM/key) ----------
    # Non-fatal: if the LLM step fails, the typed graph + structured index above
    # still succeeded, so the run is not lost — only the semantic recall layer
    # is degraded for this run. raw_result records what happened.
    raw_result: Dict[str, Any]
    try:
        if session_id:
            logger.info("remember_run: session write session_id=%s config_hash=%s",
                        session_id, config_hash[:12])
            remember_result = await cognee.remember(
                document,
                dataset_name=dataset_name,
                session_id=session_id,
            )
            raw_result = {"mode": "session", "session_id": session_id, "status": "ok"}
            if hasattr(remember_result, "to_dict"):
                raw_result.update(remember_result.to_dict())
        else:
            logger.info("remember_run: permanent write dataset=%s config_hash=%s node_set=%s",
                        dataset_name, config_hash[:12], node_set)
            raw_result = await _remember_with_ontology(document, dataset_name, node_set)
            raw_result["status"] = "ok"
    except Exception as e:
        logger.warning("Semantic (text) ingestion failed for %s — typed graph + index "
                       "still recorded. Error: %s", config_hash[:12], e)
        raw_result = {"mode": "degraded", "status": "semantic_failed", "error": str(e)}

    elapsed = time.time() - start

    return {
        "node_id": config_hash,
        "config_hash": config_hash,
        "config_summary": config_summary,
        "result_summary": result_summary,
        "dataset_name": dataset_name,
        "artifact_paths": artifact_paths,
        "artifacts": artifact_dicts,
        "elapsed_seconds": round(elapsed, 2),
        "node_set": node_set,
        "session_id": session_id,
        "cognee_result": raw_result,
        "typed_result": typed_result,
    }


async def _remember_with_ontology(
    document: str,
    dataset_name: str,
    node_set: List[str],
) -> Dict[str, Any]:
    """
    Permanent-memory ingestion, ontology-grounded when the ontology file exists.

    remember()'s kwarg router does not forward `ontology_file_path` through to
    cognify(), so ontology-grounded ingestion can't go through remember() as a
    single call. Instead we sequence the same three steps remember() performs
    internally (add -> cognify -> improve), with ontology_file_path injected
    into the cognify() call. This is still 100% native cognee calls — just
    orchestrated by us instead of by remember() — not a reimplementation of
    what those calls do internally.
    """
    await cognee.add(document, dataset_name=dataset_name, node_set=node_set)

    cognify_kwargs: Dict[str, Any] = {"datasets": [dataset_name]}
    if ONTOLOGY_FILE_PATH and os.path.exists(ONTOLOGY_FILE_PATH):
        cognify_kwargs["ontology_file_path"] = ONTOLOGY_FILE_PATH
    else:
        logger.warning("Ontology file not found at %s — ingesting without ontology grounding",
                        ONTOLOGY_FILE_PATH)

    cognify_result = await cognee.cognify(**cognify_kwargs)
    await cognee.improve(dataset=dataset_name)

    return {
        "mode": "permanent",
        "ontology_grounded": "ontology_file_path" in cognify_kwargs,
        "cognify_result": {str(k): str(v) for k, v in (cognify_result or {}).items()},
    }


# ---------------------------------------------------------------------------
# check_config (Pre-flight Guard)
# ---------------------------------------------------------------------------


async def check_config(
    config_params: Dict[str, Any],
    dataset_name: str = "main_dataset",
    significant_keys: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Pre-flight Guard: have I tried this config before?

    Strategy:
    1. Exact match — recall() scoped to the `confighash:<hash>` node_set tag
       that remember_run() wrote. This is a real graph-node tag lookup, not a
       hope that the hash string appears verbatim in generated completion text.
    2. Semantic fallback — recall() with auto_route=True, letting cognee's own
       query classifier pick the best SearchType instead of us hardcoding one.
    """
    config_hash = compute_config_hash(config_params, significant_keys)
    config_summary = generate_config_summary(config_params)
    tag = f"confighash:{config_hash}"

    # Fast, structured exact-match: the config_hash IS the run_id in the index.
    # This gives clean prior-run fields (run_id, metrics, gpu_hours, rationale)
    # for the Pre-flight Guard instead of a raw recall snippet showing "unknown".
    indexed_prior = _prior_from_index(config_hash)
    if indexed_prior is not None:
        logger.info("Exact config match via index for %s", config_hash[:12])
        return {
            "already_tried": True,
            "match_type": "exact",
            "config_hash": config_hash,
            "prior_result": indexed_prior,
            "similarity_score": 1.0,
        }

    try:
        exact_results = await cognee.recall(
            query_text=f"Configuration with hash {config_hash}",
            query_type=SearchType.CHUNKS,
            datasets=[dataset_name] if dataset_name else None,
            node_name=[tag],
            top_k=3,
        )
        if exact_results:
            logger.info("Exact config tag match found for %s", config_hash[:12])
            return {
                "already_tried": True,
                "match_type": "exact",
                "config_hash": config_hash,
                "prior_result": _extract_result_snippet(exact_results[0]),
                "similarity_score": 1.0,
            }
    except Exception as e:
        logger.warning("Exact tag lookup failed: %s", e)

    try:
        semantic_results = await cognee.recall(
            query_text=f"Experiment with config: {config_summary}",
            query_type=SearchType.CHUNKS,
            datasets=[dataset_name] if dataset_name else None,
            top_k=5,
        )
        if semantic_results:
            top = semantic_results[0]
            # Prefer cognee's real vector-similarity score; only fall back to a
            # clearly-labelled token-overlap heuristic if the store gave none.
            score = _extract_recall_score(top)
            heuristic = score is None
            if heuristic:
                score = _rough_similarity(config_summary, _result_to_text(top))
            threshold = float(os.getenv("PREFLIGHT_SIMILARITY_THRESHOLD", "0.55"))
            if score is not None and score > threshold:
                logger.info("Semantic config match found (score=%.3f, heuristic=%s)", score, heuristic)
                return {
                    "already_tried": True,
                    "match_type": "similar",
                    "config_hash": config_hash,
                    "prior_result": _extract_result_snippet(top),
                    "similarity_score": round(score, 3),
                    "score_is_heuristic": heuristic,
                }
    except Exception as e:
        logger.warning("Semantic config lookup failed: %s", e)

    return {
        "already_tried": False,
        "match_type": "none",
        "config_hash": config_hash,
        "prior_result": None,
        "similarity_score": None,
    }


# ---------------------------------------------------------------------------
# query_memory
# ---------------------------------------------------------------------------


async def query_memory(
    question: str,
    dataset_name: Optional[str] = None,
    node_name: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Free-form natural language question answered via cognee.recall().

    auto_route=True lets cognee's own classifier pick GRAPH_COMPLETION,
    TEMPORAL, TRIPLET_COMPLETION, etc. as appropriate instead of us hardcoding
    GRAPH_COMPLETION for every query shape. Pass node_name to scope the
    question to one experiment/thread (e.g. ["experiment:resnet_sweep"]).

    Does NOT filter by run status — negative/failed results are first-class
    memory and should surface when contextually relevant.
    """
    logger.info("query_memory: question='%s' dataset=%s node_name=%s",
                question[:80], dataset_name, node_name)
    try:
        results = await cognee.recall(
            query_text=question,
            datasets=[dataset_name] if dataset_name else None,
            node_name=node_name,
            auto_route=True,
            top_k=15,
        )

        sources = []
        answer_parts = []
        for r in results:
            snippet = _extract_result_snippet(r)
            sources.append(snippet.get("id") or snippet.get("node_id") or _result_to_text(r)[:100])
            answer_parts.append(_result_to_text(r))

        answer = "\n\n---\n\n".join(answer_parts) if answer_parts else "No relevant information found."
        return {
            "answer": answer,
            "sources": sources,
            "result_count": len(results),
            "dataset": dataset_name,
        }
    except Exception as e:
        logger.error("query_memory failed: %s", e)
        return {
            "answer": f"Query failed: {e}",
            "sources": [],
            "result_count": 0,
            "dataset": dataset_name,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# improve_memory
# ---------------------------------------------------------------------------


async def improve_memory(
    dataset_name: str = "main_dataset",
    generate_retrospective: bool = True,
) -> Dict[str, Any]:
    """
    Enrich the graph (cognee.improve) and, optionally, produce a short
    "lab meeting" retrospective summary (plan §9.1).

    Two distinct steps:
      1. cognee.improve() — real graph enrichment (memify-family operation:
         triplet embeddings + indexing), distinct from ingestion/cognify.
      2. A retrospective completion — recall() asked to summarise what has been
         learned, which is the human-facing "every 10 runs" summary the plan
         calls for. This is skipped if generate_retrospective=False (e.g. the
         auto-trigger path, to avoid spending LLM tokens on every N-th run).
    """
    logger.info("improve_memory: dataset=%s retrospective=%s", dataset_name, generate_retrospective)
    try:
        result = await cognee.improve(dataset=dataset_name)
        retrospective = ""
        if generate_retrospective:
            try:
                recall_out = await cognee.recall(
                    query_text=(
                        "Summarise what has been learned across these ML experiment runs so far: "
                        "which directions worked, which configs failed, and where to look next. "
                        "Write it as a short lab-meeting-style retrospective."
                    ),
                    datasets=[dataset_name],
                    auto_route=True,
                    top_k=15,
                )
                retrospective = "\n\n".join(_result_to_text(r) for r in recall_out) if recall_out else ""
            except Exception as e:  # retrospective is best-effort
                logger.warning("Retrospective generation failed: %s", e)
        return {
            "status": "completed",
            "dataset": dataset_name,
            "message": "Graph enrichment triggered via cognee.improve()",
            "retrospective": retrospective,
            "raw_result": {str(k): str(v) for k, v in (result or {}).items()} if isinstance(result, dict) else str(result),
        }
    except Exception as e:
        logger.error("improve_memory failed: %s", e)
        return {
            "status": "failed",
            "dataset": dataset_name,
            "error": str(e),
        }


# ---------------------------------------------------------------------------
# forget_stale
# ---------------------------------------------------------------------------


async def forget_stale(dataset_name: str, criteria: Dict[str, Any]) -> Dict[str, Any]:
    """
    Remove stale data from a dataset via cognee's native forget().

    Supported criteria keys:
      - everything: bool             — forget every dataset the user owns
      - delete_dataset: bool         — forget the entire named dataset
      - memory_only: bool            — keep raw data/files, wipe graph+vectors only
                                        (dataset can be re-cognified afterwards)
      - data_id: str                 — forget one specific data item (UUID)

    Note on targeted "forget all aborted runs" style criteria: cognee.forget()
    deletes by dataset or by a specific data_id, not by a content predicate —
    there is no server-side "delete where status=X" call. Doing that requires
    first resolving matching data_ids via recall() and forgetting each one;
    we attempt that best-effort below and report exactly how many were found
    versus how many could actually be resolved to a data_id, rather than
    faking a success count.
    """
    logger.info("forget_stale: dataset=%s criteria=%s", dataset_name, criteria)

    try:
        if criteria.get("everything"):
            result = await cognee.forget(everything=True)
            return {"status": "completed", "dataset": dataset_name, "criteria": criteria,
                    "deleted_count": result.get("datasets_removed", 0), "note": "All datasets removed."}

        if criteria.get("delete_dataset"):
            memory_only = bool(criteria.get("memory_only"))
            result = await cognee.forget(dataset=dataset_name, memory_only=memory_only)
            return {"status": "completed", "dataset": dataset_name, "criteria": criteria,
                    "deleted_count": -1, "note": f"Dataset removed (memory_only={memory_only}).",
                    "raw_result": result}

        data_id = criteria.get("data_id")
        if data_id:
            result = await cognee.forget(dataset=dataset_name, data_id=data_id,
                                          memory_only=bool(criteria.get("memory_only")))
            return {"status": "completed", "dataset": dataset_name, "criteria": criteria,
                    "deleted_count": 1, "raw_result": result}

        # Best-effort targeted forgetting by content predicate (status / age).
        status_filter = criteria.get("status")
        if status_filter:
            matches = await cognee.recall(
                query_text=f"runs with status {status_filter}",
                datasets=[dataset_name],
                node_name=[f"status:{_slug(status_filter)}"],
                query_type=SearchType.CHUNKS,
                top_k=50,
            )
            resolved, unresolved = 0, 0
            for m in matches:
                found_id = getattr(m, "data_id", None) or _extract_result_snippet(m).get("data_id")
                if not found_id:
                    unresolved += 1
                    continue
                try:
                    await cognee.forget(dataset=dataset_name, data_id=found_id, memory_only=True)
                    resolved += 1
                except Exception as e:
                    logger.warning("forget_stale: could not forget data_id=%s: %s", found_id, e)
                    unresolved += 1
            return {
                "status": "completed",
                "dataset": dataset_name,
                "criteria": criteria,
                "deleted_count": resolved,
                "note": f"Matched {len(matches)} item(s) tagged status:{status_filter}; "
                        f"forgot {resolved}, could not resolve a data_id for {unresolved}.",
            }

        return {
            "status": "no_op",
            "dataset": dataset_name,
            "criteria": criteria,
            "deleted_count": 0,
            "note": "No recognized criteria (expected: everything, delete_dataset, data_id, or status).",
        }
    except Exception as e:
        logger.error("forget_stale failed: %s", e)
        return {
            "status": "failed",
            "dataset": dataset_name,
            "error": str(e),
            "deleted_count": 0,
        }


# ---------------------------------------------------------------------------
# promote_to_shared
# ---------------------------------------------------------------------------


async def promote_to_shared(
    to_dataset: str = "main_dataset",
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Promote exploratory memory into the shared team graph.

    Native path only: pass the same session_id that was used in the prior
    session-scoped remember_run(..., session_id=...) call. This bridges that
    session into the shared dataset via cognee.improve(dataset=..., session_ids=[...]).

    The older dataset-copy fallback has been removed because it duplicated
    Cognee's own session promotion semantics and created a second promotion
    model that the rest of the app no longer needs.
    """
    if session_id:
        logger.info("promote_to_shared: session bridge session_id=%s -> %s", session_id, to_dataset)
        try:
            result = await cognee.improve(dataset=to_dataset, session_ids=[session_id])
            return {
                "status": "promoted",
                "mode": "session_bridge",
                "session_id": session_id,
                "to_dataset": to_dataset,
                "raw_result": {str(k): str(v) for k, v in (result or {}).items()} if isinstance(result, dict) else str(result),
            }
        except Exception as e:
            logger.error("promote_to_shared (session bridge) failed: %s", e)
            return {"status": "failed", "session_id": session_id, "error": str(e)}

    return {
        "status": "unsupported",
        "to_dataset": to_dataset,
        "error": "session_id is required for promotion; the dataset-copy fallback was removed",
    }


# ---------------------------------------------------------------------------
# remember_agent_finding — subagent write-back into the shared graph
# ---------------------------------------------------------------------------


async def remember_agent_finding(
    agent_type: str,
    experiment_name: str,
    content: str,
    dataset_name: str = "main_dataset",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Write a subagent's finding/suggestion into the permanent graph.

    This is the write half of "graph as shared blackboard" (plan Section 7):
    a subagent's output becomes a real graph node — tagged
    experiment:<name>, agent:<type>, kind:agent_finding — that other
    subagents or a human researcher can later reach via recall(), instead of
    only existing as a row in a private Postgres agent_suggestions table
    that no graph query can see.

    Call query_memory(question, node_name=[f"experiment:{slug}"]) or recall()
    scoped the same way to read back what agents have found for an experiment.
    """
    node_set = [
        f"experiment:{_slug(experiment_name)}",
        f"agent:{_slug(agent_type)}",
        "kind:agent_finding",
    ]
    doc_lines = [
        f"## Agent Finding — {agent_type}",
        f"**Experiment:** {experiment_name}",
        f"**Timestamp:** {datetime.utcnow().isoformat()}",
        "",
        content,
    ]
    if metadata:
        doc_lines += ["", "### Metadata", json.dumps(metadata, default=str, indent=2)]
    document = "\n".join(doc_lines)

    logger.info("remember_agent_finding: agent=%s experiment=%s", agent_type, experiment_name)
    try:
        raw_result = await _remember_with_ontology(document, dataset_name, node_set)
        return {
            "status": "completed",
            "agent_type": agent_type,
            "experiment_name": experiment_name,
            "node_set": node_set,
            "cognee_result": raw_result,
        }
    except Exception as e:
        logger.error("remember_agent_finding failed: %s", e)
        return {"status": "failed", "agent_type": agent_type, "experiment_name": experiment_name, "error": str(e)}


# ---------------------------------------------------------------------------
# Artifact utilities (used by main.py and file watcher — no cognee dependency)
# ---------------------------------------------------------------------------


def scan_and_register_artifacts(
    output_dir: str,
    result_id: str,
) -> List[Dict[str, Any]]:
    """
    Walk output_dir, build Artifact node dicts for each file found.
    Returns a list of dicts suitable for the /orphans endpoint.
    """
    artifacts = []
    if not output_dir or not os.path.isdir(output_dir):
        return artifacts

    ext_to_type = {
        ".pt": "checkpoint", ".pth": "checkpoint", ".ckpt": "checkpoint",
        ".png": "plot", ".jpg": "plot", ".pdf": "plot", ".svg": "plot",
        ".log": "log", ".txt": "log",
        ".json": "eval_report", ".csv": "eval_report", ".yaml": "eval_report",
    }

    for root, _dirs, files in os.walk(output_dir):
        for fname in files:
            fpath = os.path.abspath(os.path.join(root, fname))
            ext = os.path.splitext(fname)[1].lower()
            atype = ext_to_type.get(ext, "other")
            size = 0
            try:
                size = os.path.getsize(fpath)
            except OSError:
                pass
            artifacts.append({
                "file_path": fpath,
                "artifact_type": atype,
                "result_id": result_id,
                "exists_on_disk": True,
                "size_bytes": size,
                "description": f"Auto-indexed {atype} from {fname}",
            })
    return artifacts
