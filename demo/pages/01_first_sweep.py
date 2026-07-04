"""
Page 1 — the first sweep.

Trains a real softmax classifier across a small learning-rate sweep and records
each run into Groundhog memory with the FULL picture:
  - config (the hyperparameters)
  - metrics (real val_accuracy / val_loss from training)
  - dataset (name / version / preprocessing / split / quality)  <- proper input
  - output_dir (scanned into Artifact nodes)                    <- proper output
  - hypothesis + rationale (the "why")

Run it, then run page 2 to watch the Pre-flight Guard block a repeat, and
page 3 to see the insights the memory derived from these runs.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from demo._bootstrap import init, OUTPUT_ROOT
from demo.train_lib import train_and_evaluate, DATASET_INFO
import groundhog

EXPERIMENT = "blobs3_lr_sweep"
SWEEP = [0.5, 0.1, 0.03, 0.005]        # learning rates to try
BASE = {"model": "softmax", "optimizer": "sgd", "batch_size": 32,
        "weight_decay": 0.0, "epochs": 20}


def main():
    pid = init(experiment=EXPERIMENT)
    print(f"[page1] recording {len(SWEEP)} runs into project {pid}\n")

    for lr in SWEEP:
        config = {**BASE, "lr": lr}

        # Pre-flight Guard — skip configs already run (noise/alias tolerant).
        if groundhog.check(config, experiment=EXPERIMENT).get("already_tried"):
            print(f"  lr={lr:<6} already tried — skipping (Pre-flight Guard)")
            continue

        out_dir = os.path.join(OUTPUT_ROOT, EXPERIMENT, f"lr_{lr}")
        metrics = train_and_evaluate(config, out_dir=out_dir)

        groundhog.remember(
            config=config,
            metrics=metrics,
            experiment=EXPERIMENT,
            dataset=DATASET_INFO,
            output_dir=out_dir,          # model_weights.npz, metrics.json, ... -> Artifacts
            hypothesis=f"lr={lr} balances convergence speed vs. overshoot on blobs3",
            rationale=f"lr sweep point lr={lr}",
            gpu_hours=0.0,
        )
        print(f"  lr={lr:<6} -> val_acc={metrics['val_accuracy']} "
              f"val_loss={metrics['val_loss']}  (artifacts in {out_dir})")

    print("\n[page1] done. Run 02_preflight_guard.py, then 03_query_and_insights.py")


if __name__ == "__main__":
    main()
