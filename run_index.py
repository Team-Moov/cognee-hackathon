"""
run_index.py — Deterministic, restart-safe structured index for runs,
artifacts, and agent findings.

Why this exists
---------------
Cognee is a *semantic* memory (graph + vectors). It is excellent for fuzzy
recall ("find runs where the loss exploded") but it is the wrong tool for
"give me the exact list of the last 50 runs as structured JSON". The old code
did the latter by asking the LLM to *emit* a JSON array of runs from a
completion query (cognee_client.list_runs) — which is slow, costs tokens, and
hallucinates rows.

This module keeps a plain JSON-file index of the hard, structured facts of
every run/artifact/finding as it is ingested, so listing/lineage/orphan
endpoints are deterministic and instant, while Cognee stays responsible for the
semantic recall it is actually good at. The two are complementary, not
redundant.

Single-writer by design: only the Cognee gatekeeper process (main.py) writes
here, so a process-level lock is enough.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

_LOCK = threading.RLock()

_INDEX_PATH = os.getenv(
    "GROUNDHOG_INDEX_FILE",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "groundhog_index.json"),
)

_EMPTY: Dict[str, Any] = {"runs": [], "artifacts": [], "findings": []}


def _load() -> Dict[str, Any]:
    if not os.path.exists(_INDEX_PATH):
        return json.loads(json.dumps(_EMPTY))
    try:
        with open(_INDEX_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        for k in _EMPTY:
            data.setdefault(k, [])
        return data
    except (OSError, json.JSONDecodeError):
        return json.loads(json.dumps(_EMPTY))


def _save(data: Dict[str, Any]) -> None:
    tmp = _INDEX_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, default=str)
    os.replace(tmp, _INDEX_PATH)


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

def record_run(run: Dict[str, Any]) -> None:
    """Upsert a run by run_id (config_hash). Newest write wins."""
    run = dict(run)
    run.setdefault("timestamp", datetime.utcnow().isoformat())
    rid = run.get("run_id") or run.get("config_hash")
    with _LOCK:
        data = _load()
        data["runs"] = [r for r in data["runs"] if (r.get("run_id") or r.get("config_hash")) != rid]
        data["runs"].append(run)
        _save(data)


def list_runs(experiment: Optional[str] = None, status: Optional[str] = None,
              limit: int = 200) -> Dict[str, Any]:
    with _LOCK:
        data = _load()
    runs = data["runs"]
    if experiment:
        runs = [r for r in runs if (r.get("experiment") or "").lower() == experiment.lower()]
    if status:
        runs = [r for r in runs if (r.get("status") or "") == status]
    runs = sorted(runs, key=lambda r: r.get("timestamp", ""), reverse=True)[:limit]
    return {"runs": runs, "total": len(runs)}


def get_run(run_id: str) -> Optional[Dict[str, Any]]:
    with _LOCK:
        data = _load()
    for r in data["runs"]:
        if (r.get("run_id") or r.get("config_hash")) == run_id:
            return r
    return None


# ---------------------------------------------------------------------------
# Artifacts
# ---------------------------------------------------------------------------

def record_artifacts(artifacts: List[Dict[str, Any]]) -> None:
    if not artifacts:
        return
    with _LOCK:
        data = _load()
        by_path = {a["file_path"]: a for a in data["artifacts"]}
        for art in artifacts:
            by_path[art["file_path"]] = art
        data["artifacts"] = list(by_path.values())
        _save(data)


def list_artifacts() -> List[Dict[str, Any]]:
    with _LOCK:
        return _load()["artifacts"]


# ---------------------------------------------------------------------------
# Agent findings (blackboard)
# ---------------------------------------------------------------------------

def record_finding(finding: Dict[str, Any], dedup_key: Optional[str] = None) -> Dict[str, Any]:
    """
    Append an agent finding, giving it a stable `id` so it can be dismissed.

    If `dedup_key` is given, any prior *active* (non-dismissed) finding with the
    same dedup_key is dropped first, so an agent that re-runs on every event
    (config proposer, dataset steward, …) shows ONE current card per
    experiment instead of piling up duplicates. Full history still lives in the
    Cognee graph (remember_agent_finding) — only the dashboard cards are deduped.
    """
    finding = dict(finding)
    finding.setdefault("id", uuid.uuid4().hex)
    finding.setdefault("timestamp", datetime.utcnow().isoformat())
    finding.setdefault("dismissed", False)
    if dedup_key:
        finding["dedup_key"] = dedup_key
    with _LOCK:
        data = _load()
        if dedup_key:
            data["findings"] = [
                f for f in data["findings"]
                if not (f.get("dedup_key") == dedup_key and not f.get("dismissed"))
            ]
        data["findings"].append(finding)
        _save(data)
    return finding


def dismiss_finding(finding_id: str) -> bool:
    """Mark a finding dismissed (persisted). Returns True if one was found."""
    with _LOCK:
        data = _load()
        hit = False
        for f in data["findings"]:
            if f.get("id") == finding_id:
                f["dismissed"] = True
                hit = True
        if hit:
            _save(data)
        return hit


def list_findings(experiment: Optional[str] = None, limit: int = 200,
                  include_dismissed: bool = False) -> Dict[str, Any]:
    with _LOCK:
        data = _load()
    findings = data["findings"]
    if experiment:
        findings = [f for f in findings if (f.get("experiment") or "").lower() == experiment.lower()]
    if not include_dismissed:
        findings = [f for f in findings if not f.get("dismissed")]
    findings = sorted(findings, key=lambda f: f.get("timestamp", ""), reverse=True)[:limit]
    return {"suggestions": findings, "total": len(findings)}
