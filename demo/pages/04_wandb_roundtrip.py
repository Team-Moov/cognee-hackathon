"""
Page 4 — Weights & Biases round-trip (both directions).

Groundhog integrates with W&B two ways:

  app -> W&B : when a project has W&B creds attached, every groundhog.remember()
               is ALSO mirrored to your W&B project (backend _mirror_to_wandb).
  W&B -> app : the wandb_sync connector pulls runs you logged directly in W&B
               back into the project's Cognee memory (incremental, watermarked).

Prerequisites — set these before running (the bootstrap attaches them to the
project automatically):

    setx WANDB_ENTITY   your-wandb-username     # optional (defaults to default entity)
    setx WANDB_PROJECT  groundhog-demo
    setx WANDB_API_KEY  <your key>

(or export them in bash). Then:  python demo/pages/04_wandb_roundtrip.py
"""

import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from demo._bootstrap import init, BACKEND
from demo.train_lib import train_and_evaluate, DATASET_INFO
import groundhog

EXPERIMENT = "blobs3_wandb"


def _project(pid, secrets=False):
    url = f"{BACKEND.rstrip('/')}/api/projects/{pid}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def main():
    pid = init(experiment=EXPERIMENT)
    proj = _project(pid)
    wb = proj.get("wandb", {})
    if not wb.get("project"):
        raise SystemExit(
            "[page4] No W&B project attached. Set WANDB_PROJECT + WANDB_API_KEY "
            "(and optionally WANDB_ENTITY) in your environment, then re-run.")

    print(f"[page4] W&B configured: entity={wb.get('entity')} project={wb.get('project')}\n")

    # --- direction 1: app -> W&B (remember auto-mirrors) ---
    config = {"model": "softmax", "optimizer": "sgd", "lr": 0.07,
              "batch_size": 32, "weight_decay": 0.0, "epochs": 20}
    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "outputs", EXPERIMENT)
    metrics = train_and_evaluate(config, out_dir=out_dir)
    resp = groundhog.remember(
        config=config, metrics=metrics, experiment=EXPERIMENT,
        dataset=DATASET_INFO, output_dir=out_dir,
        rationale="W&B round-trip demo run", gpu_hours=0.0,
    )
    # groundhog.remember returns the backend response including the wandb result
    print(f"[page4] app -> W&B mirror: {resp.get('wandb')}")
    print(f"        (metrics {metrics})\n")

    # --- direction 2: W&B -> app (pull runs back into memory) ---
    from connectors.wandb_sync import sync_once
    n = sync_once(BACKEND, pid, wb.get("entity"), wb.get("project"),
                  os.getenv("WANDB_API_KEY"))
    print(f"\n[page4] W&B -> app sync ingested {n} run(s) into project {pid}")


if __name__ == "__main__":
    main()
