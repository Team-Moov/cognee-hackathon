"""
insights.py — derived ML knowledge from a project's run history.

This is the "memory that learns" layer. Raw runs answer "what did I try?";
these functions turn a pile of runs into *reusable conclusions* a researcher
(or an agent) can act on:

  - parameter_sensitivity: which hyperparameters actually move the metric, and
    the best value seen for each — so you tune what matters, not everything.
  - best_per_dataset: the best config found on each dataset — "what worked on
    something like this before".

Deterministic and dependency-free (no LLM, no numpy) so it's cheap to run every
N runs. The output is written back into the Cognee graph as insight nodes (see
main.generate_project_insights) so it becomes queryable memory, and is fed to
the config-proposer agent as context.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

# metric name → higher_is_better
_HIGHER_BETTER = {"val_accuracy", "val_acc", "accuracy", "acc", "f1", "f1_score", "map", "auc"}
_LOWER_BETTER = {"val_loss", "loss", "perplexity", "error", "wer"}
_ACC_ALIASES = ["val_accuracy", "val_acc", "accuracy", "acc", "f1_score", "map", "auc"]
_LOSS_ALIASES = ["val_loss", "loss", "perplexity", "error"]

# config keys that are noise, not hyperparameters (mirror memory.CONFIG_NOISE_KEYS spirit)
_NOISE = {"seed", "random_seed", "gpu_id", "device", "output_dir", "run_name", "name",
          "num_workers", "timestamp", "git_commit", "local_rank", "world_size"}


def primary_metric(metrics: Dict[str, Any]) -> Optional[Tuple[str, float, bool]]:
    """Return (label, value, higher_is_better) for the run's headline metric."""
    if not isinstance(metrics, dict):
        return None
    for k in _ACC_ALIASES:
        v = metrics.get(k)
        if isinstance(v, (int, float)):
            return (k, float(v), True)
    for k in _LOSS_ALIASES:
        v = metrics.get(k)
        if isinstance(v, (int, float)):
            return (k, float(v), False)
    return None


def _score(run: Dict[str, Any], higher_is_better: bool) -> Optional[float]:
    pm = primary_metric(run.get("metrics") or {})
    if not pm:
        return None
    _, value, hib = pm
    if hib != higher_is_better:
        return None
    return value


def _completed(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [r for r in runs if (r.get("status") or "completed") == "completed" and (r.get("metrics") or {})]


def _mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def parameter_sensitivity(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Rank hyperparameters by how much varying them moves the primary metric.

    For each config key with >=2 distinct values, group the runs' metric by the
    key's value and measure the spread of group means. A big spread = the
    parameter matters. Returns a list sorted most-sensitive first, each with the
    best value observed.
    """
    completed = _completed(runs)
    if len(completed) < 2:
        return []

    # decide metric direction from the majority of runs
    higher = sum(1 for r in completed if (primary_metric(r.get("metrics") or {}) or (None, 0, False))[2])
    higher_is_better = higher >= (len(completed) - higher)

    # collect (config_value -> [scores]) per key
    scored = [(r, _score(r, higher_is_better)) for r in completed]
    scored = [(r, s) for r, s in scored if s is not None]
    if len(scored) < 2:
        return []

    keys = set()
    for r, _s in scored:
        for k in (r.get("config") or {}):
            if not str(k).startswith("_") and str(k).lower() not in _NOISE:
                keys.add(k)

    out = []
    for key in keys:
        groups: Dict[str, List[float]] = {}
        for r, s in scored:
            if key in (r.get("config") or {}):
                val = str(r["config"][key])
                groups.setdefault(val, []).append(s)
        if len(groups) < 2:
            continue
        means = {v: _mean(xs) for v, xs in groups.items()}
        spread = max(means.values()) - min(means.values())
        best_val = (max if higher_is_better else min)(means, key=means.get)
        out.append({
            "parameter": key,
            "sensitivity": round(spread, 4),
            "best_value": best_val,
            "best_metric_mean": round(means[best_val], 4),
            "values_tried": sorted(groups.keys()),
            "metric": (primary_metric(scored[0][0].get("metrics") or {}) or ("metric",))[0],
            "direction": "higher_is_better" if higher_is_better else "lower_is_better",
        })
    out.sort(key=lambda d: d["sensitivity"], reverse=True)
    return out


def best_per_dataset(runs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Best run (by primary metric) per dataset — 'what worked on data like this'."""
    completed = _completed(runs)
    by_ds: Dict[str, List[Dict[str, Any]]] = {}
    for r in completed:
        ds = ((r.get("dataset") or {}).get("name")) or "unknown"
        by_ds.setdefault(ds, []).append(r)

    out = []
    for ds, rs in by_ds.items():
        if ds == "unknown" and len(by_ds) > 1:
            continue
        higher = sum(1 for r in rs if (primary_metric(r.get("metrics") or {}) or (None, 0, False))[2])
        hib = higher >= (len(rs) - higher)
        scored = [(r, _score(r, hib)) for r in rs]
        scored = [(r, s) for r, s in scored if s is not None]
        if not scored:
            continue
        best = (max if hib else min)(scored, key=lambda t: t[1])[0]
        pm = primary_metric(best.get("metrics") or {})
        out.append({
            "dataset": ds,
            "best_config": best.get("config", {}),
            "best_run_id": best.get("run_id"),
            "metric": pm[0] if pm else None,
            "metric_value": round(pm[1], 4) if pm else None,
        })
    return out


def build_insights(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Full derived-insight bundle for a project's runs."""
    completed = _completed(runs)
    sensitivity = parameter_sensitivity(runs)
    per_ds = best_per_dataset(runs)
    return {
        "n_runs": len(runs),
        "n_completed": len(completed),
        "parameter_sensitivity": sensitivity,
        "best_per_dataset": per_ds,
        "summary": _summary_text(sensitivity, per_ds, len(completed)),
    }


def _summary_text(sensitivity: List[Dict[str, Any]], per_ds: List[Dict[str, Any]], n: int) -> str:
    """A short natural-language digest — this is what gets embedded in the graph."""
    if n < 2:
        return "Not enough completed runs yet to derive insights (need at least 2)."
    parts = [f"Across {n} completed runs:"]
    if sensitivity:
        top = sensitivity[0]
        parts.append(
            f"The most impactful hyperparameter is '{top['parameter']}' "
            f"(moves {top['metric']} by ~{top['sensitivity']}); best value seen: "
            f"{top['best_value']}."
        )
        if len(sensitivity) > 1:
            low = sensitivity[-1]
            parts.append(f"'{low['parameter']}' had the least effect ({low['sensitivity']}).")
    for d in per_ds[:3]:
        if d.get("metric_value") is not None:
            parts.append(f"Best on {d['dataset']}: {d['metric']}={d['metric_value']}.")
    return " ".join(parts)
