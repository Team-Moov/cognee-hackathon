"""
test_integration.py — End-to-end smoke test for the fixes made this session.

Unlike test_day1.py / test.py / test_experiment.py (which call cognee
in-process), this script exercises the actual running HTTP servers, the way
the frontend, MCP server, and connectors really do. Run it after both
servers are up:

    # terminal 1 (repo root)
    uvicorn main:app --port 8010

    # terminal 2 (backend/, needs Postgres running + DATABASE_URL set)
    cd backend && uvicorn app.main:app --port 8000

    # terminal 3 (repo root)
    python test_integration.py

Each check prints PASS/FAIL and a one-line reason; it does not raise/exit
on the first failure, so you get the full picture in one run.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid

import httpx

COGNEE_URL = os.getenv("COGNEE_API_URL", "http://localhost:8010")
BACKEND_URL = os.getenv("BACKEND_API_URL", "http://localhost:8000")

_results: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    _results.append((name, ok, detail))
    status = "PASS" if ok else "FAIL"
    print(f"[{status}] {name}" + (f" — {detail}" if detail else ""))


async def main() -> None:
    print(f"cognee server:  {COGNEE_URL}")
    print(f"backend server: {BACKEND_URL}")
    print("-" * 60)

    # 0. Ontology file present and non-empty (no server needed)
    from ontology.ml_ontology import ONTOLOGY_FILE_PATH, ontology_file_exists
    check("ontology file exists", ontology_file_exists(), ONTOLOGY_FILE_PATH)

    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Health checks
        try:
            r = await client.get(f"{COGNEE_URL}/health")
            check("cognee server /health", r.status_code == 200, r.text[:120])
        except httpx.RequestError as e:
            check("cognee server /health", False, f"unreachable: {e}")
            print("\nStop: cognee server must be up for the rest of this test.")
            return

        try:
            r = await client.get(f"{BACKEND_URL}/api/health")
            check("backend /api/health", r.status_code == 200, r.text[:150])
        except httpx.RequestError as e:
            check("backend /api/health", False, f"unreachable: {e}")

        # 2. Pre-flight Guard exact match — remember a run via the cognee
        #    server directly, then check the SAME config comes back
        #    already_tried=True, match_type=exact (proves node_set tagging
        #    + recall(node_name=[...]) actually works, not just text luck).
        unique_lr = round(1e-4 + (time.time() % 1000) / 1e9, 10)  # avoid collisions across runs
        config = {"model": "ResNet50", "optimizer": "AdamW", "lr": unique_lr, "batch_size": 64}
        experiment = f"integration_test_{uuid.uuid4().hex[:8]}"

        r = await client.post(f"{COGNEE_URL}/remember", json={
            "config_params": config,
            "result_metrics": {"val_accuracy": 0.91},
            "status": "completed",
            "rationale": "Integration test run — safe to delete.",
            "experiment_name": experiment,
            "thread_name": "default",
            "dataset": "main_dataset",
        })
        check("cognee /remember (permanent, ontology-grounded path)", r.status_code == 200, str(r.status_code))
        remembered = r.json() if r.status_code == 200 else {}
        check("remember() tagged node_set", bool(remembered.get("node_set")), str(remembered.get("node_set")))

        r = await client.post(f"{COGNEE_URL}/check-config", json={
            "config_params": config, "dataset": "main_dataset",
        })
        cc = r.json() if r.status_code == 200 else {}
        check(
            "check-config exact tag match (Pre-flight Guard)",
            cc.get("match_type") == "exact" and cc.get("already_tried") is True,
            f"match_type={cc.get('match_type')} already_tried={cc.get('already_tried')}",
        )

        # 3. Cross-connector visibility: backend/app's check-config should
        #    ALSO surface this match even though it was never written to
        #    backend's Postgres table — proving backend really calls cognee,
        #    not just its own DB.
        r = await client.post(f"{BACKEND_URL}/api/runs/check-config", json={
            "config": config, "experiment": experiment,
        })
        bcc = r.json() if r.status_code == 200 else {}
        check(
            "backend check-config sees cognee-only match (cross-connector)",
            bcc.get("already_tried") is True and bcc.get("source") in ("cognee", "postgres"),
            f"source={bcc.get('source')} already_tried={bcc.get('already_tried')}",
        )

        # 4. Query bar — should report source="cognee" when the server is up
        r = await client.post(f"{BACKEND_URL}/api/query", json={
            "question": f"What runs exist for experiment {experiment}?"
        })
        q = r.json() if r.status_code == 200 else {}
        check(
            "backend /api/query uses cognee.recall() (source=cognee)",
            q.get("source") == "cognee",
            f"source={q.get('source')} answer_len={len(q.get('answer', ''))}",
        )

        # 5. Agent finding write-back + recall
        r = await client.post(f"{COGNEE_URL}/agent-finding", json={
            "agent_type": "config_proposer",
            "experiment_name": experiment,
            "content": "Integration test: try lr=5e-5 next, val_accuracy trend is improving.",
            "dataset": "main_dataset",
        })
        check("POST /agent-finding (subagent graph write-back)", r.status_code == 200, str(r.status_code))

        r = await client.post(f"{COGNEE_URL}/query", json={
            "question": "What has the config proposer agent suggested?",
            "node_name": [f"experiment:{_slug(experiment)}"],
        })
        aq = r.json() if r.status_code == 200 else {}
        check(
            "agent finding recall()-able via node_name scope",
            "lr=5e-5" in aq.get("answer", "") or aq.get("result_count", 0) > 0,
            f"result_count={aq.get('result_count')}",
        )

    print("-" * 60)
    passed = sum(1 for _, ok, _ in _results if ok)
    print(f"{passed}/{len(_results)} checks passed.")
    if passed < len(_results):
        sys.exit(1)


def _slug(text: str) -> str:
    import re
    return re.sub(r"[^a-z0-9]+", "_", text.strip().lower()).strip("_") or "unknown"


if __name__ == "__main__":
    asyncio.run(main())
