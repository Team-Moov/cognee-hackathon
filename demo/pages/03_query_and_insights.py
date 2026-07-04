"""
Page 3 — ask the memory, and read what it learned.

Two layers of memory:
  - query(): free-form semantic recall over the Cognee graph ("what was the
    best run and why?").
  - /insights: deterministic derived knowledge (which hyperparameter mattered,
    best config per dataset) computed from the run history.

Run this after page 1 so there are runs to reason over.
"""

import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from demo._bootstrap import init, BACKEND
import groundhog

EXPERIMENT = "blobs3_lr_sweep"

QUESTIONS = [
    "What learning rates have been tried on the blobs3 dataset and which gave the best val_accuracy?",
    "What is the best run so far and what was its configuration?",
]


def _get_insights(pid):
    url = f"{BACKEND.rstrip('/')}/api/insights?project_id={pid}"
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read().decode())


def main():
    pid = init(experiment=EXPERIMENT)

    print("=== Semantic recall (groundhog.query) ===")
    for q in QUESTIONS:
        print(f"\nQ: {q}")
        print(f"A: {groundhog.query(q)}")

    print("\n=== Derived insights (memory that learns) ===")
    ins = _get_insights(pid)
    print(f"n_runs={ins.get('n_runs')} n_completed={ins.get('n_completed')}")
    print(f"summary: {ins.get('summary')}")
    for s in ins.get("parameter_sensitivity", [])[:5]:
        print(f"  - {s['parameter']}: impact={s['sensitivity']} best={s['best_value']} "
              f"({s['metric']} {s['direction']})")
    for d in ins.get("best_per_dataset", []):
        print(f"  best on {d['dataset']}: {d['metric']}={d['metric_value']}  cfg={d['best_config']}")


if __name__ == "__main__":
    main()
