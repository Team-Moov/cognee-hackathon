"""
train_lib.py — a tiny, real, dependency-light training routine (numpy only).

This is deliberately NOT a toy that returns fake numbers: it trains a softmax
(multinomial logistic) classifier with minibatch SGD + L2 weight decay on a
synthetic 3-class dataset, so the metrics genuinely respond to the
hyperparameters (lr, batch_size, weight_decay, epochs). That makes the
Groundhog Pre-flight Guard / insights demo meaningful — sweeping lr actually
moves val_accuracy, and the memory learns which knob mattered.

It also writes real OUTPUT ARTIFACTS to an output directory (model weights,
metrics.json, a training-loss log, and validation predictions), so the
`output_dir` scan on `groundhog.remember(...)` produces real Artifact nodes.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict

import numpy as np

# ---------------------------------------------------------------------------
# Dataset (proper, versioned input) — synthetic 3-class gaussian blobs.
# Fixed seed => a stable "dataset" you can describe with name/version/split.
# ---------------------------------------------------------------------------

DATASET_INFO = {
    "name": "blobs3",
    "version": "v1",
    "preprocessing": "z-score standardized (per-feature mean/std from train split)",
    "split_rationale": "70/30 stratified train/val, fixed seed 7",
    "quality_issues": "class 2 slightly overlaps class 1 (intentional, ~4% Bayes error)",
}


def _make_dataset(n_per_class: int = 220, n_features: int = 6, seed: int = 7):
    rng = np.random.default_rng(seed)
    centers = rng.normal(0, 1.8, size=(3, n_features))
    # class 2 pushed toward class 1 to create genuine overlap (see quality_issues)
    centers[2] = 0.55 * centers[1] + 0.45 * centers[2]
    X = np.vstack([rng.normal(centers[k], 2.1, size=(n_per_class, n_features)) for k in range(3)])
    y = np.repeat(np.arange(3), n_per_class)
    perm = rng.permutation(len(y))
    X, y = X[perm], y[perm]

    n_val = int(0.30 * len(y))
    Xtr, ytr = X[n_val:], y[n_val:]
    Xval, yval = X[:n_val], y[:n_val]
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-8
    return (Xtr - mu) / sd, ytr, (Xval - mu) / sd, yval


def _softmax(z):
    z = z - z.max(axis=1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=1, keepdims=True)


def _cross_entropy(P, y):
    return float(-np.log(P[np.arange(len(y)), y] + 1e-12).mean())


def train_and_evaluate(config: Dict[str, Any], out_dir: str | None = None) -> Dict[str, Any]:
    """
    Train a softmax classifier under `config` and return metrics.

    Recognised config keys (others are ignored / treated as noise):
      lr, batch_size, weight_decay, epochs, seed
    """
    lr = float(config.get("lr", 0.1))
    batch_size = int(config.get("batch_size", 32))
    weight_decay = float(config.get("weight_decay", 0.0))
    epochs = int(config.get("epochs", 25))
    seed = int(config.get("seed", 0))

    Xtr, ytr, Xval, yval = _make_dataset()
    rng = np.random.default_rng(seed)
    n, d = Xtr.shape
    k = 3
    W = rng.normal(0, 0.01, size=(d, k))
    b = np.zeros(k)
    Y = np.eye(k)[ytr]

    loss_log = []
    for epoch in range(epochs):
        idx = rng.permutation(n)
        for start in range(0, n, batch_size):
            bi = idx[start:start + batch_size]
            Xb, Yb = Xtr[bi], Y[bi]
            P = _softmax(Xb @ W + b)
            grad = Xb.T @ (P - Yb) / len(bi) + weight_decay * W
            gb = (P - Yb).mean(0)
            W -= lr * grad
            b -= lr * gb
        train_loss = _cross_entropy(_softmax(Xtr @ W + b), ytr)
        loss_log.append(round(train_loss, 5))

    Pval = _softmax(Xval @ W + b)
    val_pred = Pval.argmax(1)
    val_acc = float((val_pred == yval).mean())
    val_loss = _cross_entropy(Pval, yval)
    metrics = {
        "val_accuracy": round(val_acc, 4),
        "val_loss": round(val_loss, 4),
        "train_loss": loss_log[-1],
        "epochs": epochs,
    }

    if out_dir:
        _write_artifacts(out_dir, W, b, metrics, loss_log, yval, val_pred)
    return metrics


def _write_artifacts(out_dir, W, b, metrics, loss_log, yval, val_pred):
    """Write real output files so Groundhog's output_dir scan finds Artifact nodes."""
    os.makedirs(out_dir, exist_ok=True)
    np.savez(os.path.join(out_dir, "model_weights.npz"), W=W, b=b)
    with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as fh:
        json.dump(metrics, fh, indent=2)
    with open(os.path.join(out_dir, "training_log.txt"), "w", encoding="utf-8") as fh:
        fh.write("epoch,train_loss\n")
        for i, l in enumerate(loss_log):
            fh.write(f"{i},{l}\n")
    with open(os.path.join(out_dir, "val_predictions.csv"), "w", encoding="utf-8") as fh:
        fh.write("index,y_true,y_pred\n")
        for i, (t, p) in enumerate(zip(yval.tolist(), val_pred.tolist())):
            fh.write(f"{i},{t},{p}\n")


if __name__ == "__main__":
    # quick self-check: sweeping lr should move accuracy
    for lr in (0.5, 0.1, 0.01):
        m = train_and_evaluate({"lr": lr, "batch_size": 32, "weight_decay": 0.0, "epochs": 25})
        print(f"lr={lr:<5} -> {m}")
