"""
Page 2 — the Pre-flight Guard in action.

The whole point of Groundhog: don't burn compute re-running a config you already
ran. This page re-submits a config from page 1's sweep and shows the guard
catching it BEFORE training — including the prior result, so you can decide.

It also shows the guard being noise-tolerant: it re-checks the SAME experiment
with an extra noise field (`seed`, `gpu_id`) and a learning-rate alias, and the
guard still recognises it as already-tried (those keys aren't in the project's
significant_keys, so they don't change the config hash).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from demo._bootstrap import init
import groundhog

EXPERIMENT = "blobs3_lr_sweep"
ALREADY_RAN = {"model": "softmax", "optimizer": "sgd", "lr": 0.1,
               "batch_size": 32, "weight_decay": 0.0, "epochs": 20}
BRAND_NEW = {"model": "softmax", "optimizer": "adam", "lr": 0.001,
             "batch_size": 64, "weight_decay": 1e-4, "epochs": 40}


def _report(label, config):
    res = groundhog.check(config, experiment=EXPERIMENT)
    tried = res.get("already_tried")
    print(f"\n[{label}] already_tried={tried}  match_type={res.get('match_type')}")
    if tried:
        prior = (res.get("matching_runs") or [{}])[0]
        print(f"    prior metrics : {prior.get('metrics')}")
        print(f"    recommendation: {res.get('recommendation')}")
    else:
        print(f"    {res.get('recommendation')}")


def main():
    init(experiment=EXPERIMENT)

    # 1. exact repeat of a config from page 1 -> should be BLOCKED
    _report("exact repeat", ALREADY_RAN)

    # 2. same significant config + noise fields (seed/gpu_id) -> still BLOCKED
    _report("repeat + noise fields", {**ALREADY_RAN, "seed": 123, "gpu_id": 3, "output_dir": "/tmp/x"})

    # 3. a genuinely new config -> should be ALLOWED
    _report("new config", BRAND_NEW)


if __name__ == "__main__":
    main()
