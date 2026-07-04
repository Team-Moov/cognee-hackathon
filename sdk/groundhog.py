"""
groundhog — drop-in memory for ML experiments.

Paste ONE block into a notebook or any .py training project to connect your work
to a Groundhog project and record runs automatically:

    import groundhog
    groundhog.init(project_id="proj_myexp_ab12cd34")   # from the Groundhog UI

    # before a sweep — don't waste compute on a config you already ran
    if groundhog.check(config)["already_tried"]:
        print("already ran this — skipping")

    # after a run — record it (rationale is auto-harvested from your git commit)
    groundhog.remember(config=config, metrics={"val_accuracy": 0.91})

    # ask memory anything
    print(groundhog.query("what was the best val_accuracy so far?"))

Design notes:
  - Zero third-party dependencies (stdlib urllib only) so `pip install`-ing this
    into any environment is friction-free.
  - Works for notebooks AND plain .py projects — it's just function calls, no
    magic required (a Jupyter magic can wrap these, but scripts use them directly).
  - "Harvest the why": if you don't pass a rationale, it pulls your latest git
    commit message + hash from the working directory, so the reasoning is captured
    from where you already write it instead of asking you to retype it.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

__all__ = ["init", "remember", "check", "query", "config"]

_STATE: Dict[str, Any] = {
    "base_url": os.getenv("GROUNDHOG_API_URL", "http://localhost:8000"),
    "project_id": os.getenv("GROUNDHOG_PROJECT_ID"),
    "token": os.getenv("GROUNDHOG_TOKEN"),
    "experiment": None,
}


def init(project_id: Optional[str] = None, *, token: Optional[str] = None,
         base_url: Optional[str] = None, experiment: Optional[str] = None) -> Dict[str, Any]:
    """
    Connect this process to a Groundhog project. Call once at the top of your
    notebook/script. project_id comes from the Groundhog UI ("create project").
    """
    if project_id:
        _STATE["project_id"] = project_id
    if token:
        _STATE["token"] = token
    if base_url:
        _STATE["base_url"] = base_url
    if experiment:
        _STATE["experiment"] = experiment
    if not _STATE["project_id"]:
        raise ValueError("groundhog.init needs a project_id (create one in the Groundhog UI)")
    return {"project_id": _STATE["project_id"], "base_url": _STATE["base_url"],
            "experiment": _STATE["experiment"]}


# ---------------------------------------------------------------------------
# HTTP (stdlib only)
# ---------------------------------------------------------------------------

def _request(method: str, path: str, payload: Optional[Dict[str, Any]] = None,
             timeout: float = 180.0) -> Dict[str, Any]:
    url = _STATE["base_url"].rstrip("/") + path
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json"}
    if _STATE.get("token"):
        headers["Authorization"] = f"Bearer {_STATE['token']}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"groundhog: {method} {path} -> HTTP {e.code}: {e.read().decode('utf-8')[:200]}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"groundhog: cannot reach {url} — is the backend running? ({e.reason})")


# ---------------------------------------------------------------------------
# git rationale harvest
# ---------------------------------------------------------------------------

def _git(*args: str) -> Optional[str]:
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True, timeout=5)
        return out.stdout.strip() if out.returncode == 0 else None
    except Exception:
        return None


def _harvest_git() -> Dict[str, str]:
    """Pull commit hash + message from the working directory (the 'why')."""
    commit = _git("rev-parse", "HEAD") or "unknown"
    message = _git("log", "-1", "--pretty=%B") or ""
    return {"git_commit": commit, "message": message.strip()}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _require_init() -> str:
    pid = _STATE.get("project_id")
    if not pid:
        raise RuntimeError("call groundhog.init(project_id=...) first")
    return pid


def check(config: Dict[str, Any], *, experiment: Optional[str] = None) -> Dict[str, Any]:
    """
    Pre-flight Guard: has this config already been run in this project?
    Returns {already_tried, match_type, matching_runs, recommendation, ...}.
    """
    _require_init()
    return _request("POST", "/api/runs/check-config", {
        "config": config,
        "project_id": _STATE["project_id"],
        "experiment": experiment or _STATE.get("experiment"),
    }, timeout=45.0)


def remember(*, config: Dict[str, Any], metrics: Dict[str, Any],
             rationale: Optional[str] = None, status: str = "completed",
             experiment: Optional[str] = None, thread: str = "default",
             gpu_hours: Optional[float] = None, wall_clock_seconds: Optional[float] = None,
             dataset: Optional[Dict[str, Any]] = None,
             output_dir: Optional[str] = None,
             artifacts: Optional[List[Dict[str, str]]] = None,
             hypothesis: Optional[str] = None,
             derived_from: Optional[str] = None) -> Dict[str, Any]:
    """
    Record a run into this project's memory — the FULL picture, not just metrics:

      config, metrics, rationale (auto from git), status, cost (gpu_hours /
      wall_clock_seconds), the DATASET used (name/version/preprocessing/split/
      quality), OUTPUT FILES (output_dir is scanned into Artifact nodes), the
      HYPOTHESIS being tested, and DERIVED_FROM lineage (which prior config this
      was adapted from).

    Only `config` and `metrics` are required; everything else is optional and
    captured when provided. `output_dir` defaults to $GROUNDHOG_OUTPUT_DIR.
    """
    _require_init()
    git = _harvest_git()
    if not rationale:
        rationale = git["message"] or "(no rationale; add a git commit message to capture the why)"
    return _request("POST", "/api/runs/remember", {
        "project_id": _STATE["project_id"],
        "experiment": experiment or _STATE.get("experiment") or "unnamed",
        "thread": thread,
        "config": config,
        "metrics": metrics,
        "rationale": rationale,
        "status": status,
        "gpu_hours": gpu_hours,
        "wall_clock_seconds": wall_clock_seconds,
        "git_commit": git["git_commit"],
        "dataset": dataset,
        "output_dir": output_dir or os.getenv("GROUNDHOG_OUTPUT_DIR"),
        "artifacts": artifacts or [],
        "hypothesis": hypothesis,
        "derived_from": derived_from,
    })


def query(question: str) -> str:
    """Ask this project's memory a free-form question; returns the answer text."""
    _require_init()
    result = _request("POST", "/api/query", {
        "question": question,
        "project_id": _STATE["project_id"],
    }, timeout=90.0)
    return result.get("answer", "")


def config() -> Dict[str, Any]:
    """Return the current SDK state (project_id, base_url, experiment)."""
    return dict(_STATE)
