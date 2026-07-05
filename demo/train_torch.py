"""
train_torch.py — a real PyTorch CNN on FashionMNIST, GPU-aware.

Used by the GPU demo notebook to do 10 runs across a wide hyperparameter space
so Groundhog derives clear insights (which knob actually moves accuracy) and
tracks realistic GPU-hours from wall-clock on CUDA.

Nothing faked: it trains a small conv net on real FashionMNIST images, on the
GPU when one is available, and every run writes real artifacts (checkpoint,
metrics.json, per-epoch training log) that Groundhog scans into Artifact nodes.

Exposed hyperparameters (all recorded in the run config):
  lr, batch_size, optimizer, weight_decay, dropout, conv_channels, hidden_dim,
  activation, epochs, seed
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset
from torchvision import datasets, transforms

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA_DIR = os.path.join(_HERE, "data")

DATASET_INFO = {
    "name": "FashionMNIST",
    "version": "v1",
    "preprocessing": "ToTensor + normalize(mean=0.2860, std=0.3530)",
    "split_rationale": "subset: 15000 train / 3000 val (fixed seed) for fast 10-run sweeps",
    "quality_issues": "shirt/coat/pullover classes are visually confusable (inherent)",
}

_ACT = {"relu": nn.ReLU, "gelu": nn.GELU}
_TRAIN_SUBSET = 15000
_VAL_SUBSET = 3000


class SmallCNN(nn.Module):
    def __init__(self, channels: int, hidden_dim: int, dropout: float, activation: str):
        super().__init__()
        act = _ACT.get(activation, nn.ReLU)
        self.features = nn.Sequential(
            nn.Conv2d(1, channels, 3, padding=1), act(), nn.MaxPool2d(2),      # 28->14
            nn.Conv2d(channels, channels * 2, 3, padding=1), act(), nn.MaxPool2d(2),  # 14->7
        )
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(channels * 2 * 7 * 7, hidden_dim), act(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, 10),
        )

    def forward(self, x):
        return self.classifier(self.features(x))


def _loaders(batch_size: int, seed: int):
    tf = transforms.Compose([
        transforms.ToTensor(),
        transforms.Normalize((0.2860,), (0.3530,)),
    ])
    train_full = datasets.FashionMNIST(_DATA_DIR, train=True, download=True, transform=tf)
    val_full = datasets.FashionMNIST(_DATA_DIR, train=False, download=True, transform=tf)
    g = torch.Generator().manual_seed(seed)
    tr_idx = torch.randperm(len(train_full), generator=g)[:_TRAIN_SUBSET]
    va_idx = torch.randperm(len(val_full), generator=g)[:_VAL_SUBSET]
    train = Subset(train_full, tr_idx.tolist())
    val = Subset(val_full, va_idx.tolist())
    # num_workers=0 keeps it robust on Windows notebooks
    return (
        DataLoader(train, batch_size=batch_size, shuffle=True, num_workers=0),
        DataLoader(val, batch_size=256, shuffle=False, num_workers=0),
    )


def train_and_evaluate(config: Dict[str, Any], out_dir: str | None = None) -> Dict[str, Any]:
    lr = float(config.get("lr", 1e-3))
    batch_size = int(config.get("batch_size", 128))
    optimizer_name = str(config.get("optimizer", "adam")).lower()
    weight_decay = float(config.get("weight_decay", 0.0))
    dropout = float(config.get("dropout", 0.0))
    channels = int(config.get("conv_channels", 32))
    hidden_dim = int(config.get("hidden_dim", 128))
    activation = str(config.get("activation", "relu")).lower()
    epochs = int(config.get("epochs", 2))
    seed = int(config.get("seed", 0))

    torch.manual_seed(seed)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    train_loader, val_loader = _loaders(batch_size, seed)

    model = SmallCNN(channels, hidden_dim, dropout, activation).to(device)
    n_params = sum(p.numel() for p in model.parameters())
    if optimizer_name == "sgd":
        opt = torch.optim.SGD(model.parameters(), lr=lr, momentum=0.9, weight_decay=weight_decay)
    else:
        opt = torch.optim.Adam(model.parameters(), lr=lr, weight_decay=weight_decay)

    log = []
    t0 = time.time()
    n_images = 0
    for epoch in range(epochs):
        model.train()
        running = 0.0
        for xb, yb in train_loader:
            xb, yb = xb.to(device, non_blocking=True), yb.to(device, non_blocking=True)
            opt.zero_grad()
            loss = F.cross_entropy(model(xb), yb)
            loss.backward()
            opt.step()
            running += loss.item() * len(xb)
            n_images += len(xb)
        train_loss = running / _TRAIN_SUBSET
        log.append({"epoch": epoch, "train_loss": round(train_loss, 5)})
    if device.type == "cuda":
        torch.cuda.synchronize()
    wall = time.time() - t0

    # validation
    model.eval()
    correct, val_loss_sum = 0, 0.0
    with torch.no_grad():
        for xb, yb in val_loader:
            xb, yb = xb.to(device), yb.to(device)
            logits = model(xb)
            val_loss_sum += F.cross_entropy(logits, yb, reduction="sum").item()
            correct += (logits.argmax(1) == yb).sum().item()
    val_acc = correct / _VAL_SUBSET
    val_loss = val_loss_sum / _VAL_SUBSET

    metrics = {
        "val_accuracy": round(val_acc, 4),
        "val_loss": round(val_loss, 4),
        "train_loss": log[-1]["train_loss"],
        "epochs": epochs,
        "wall_clock_seconds": round(wall, 2),
        "gpu_hours": round(wall / 3600.0, 5) if device.type == "cuda" else 0.0,
        "throughput_img_s": round(n_images / wall, 1) if wall else 0.0,
        "n_params": n_params,
        "device": torch.cuda.get_device_name(0) if device.type == "cuda" else "cpu",
    }

    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
        torch.save(model.state_dict(), os.path.join(out_dir, "model.pt"))
        with open(os.path.join(out_dir, "metrics.json"), "w", encoding="utf-8") as fh:
            json.dump(metrics, fh, indent=2)
        with open(os.path.join(out_dir, "training_log.csv"), "w", encoding="utf-8") as fh:
            fh.write("epoch,train_loss\n")
            for r in log:
                fh.write(f"{r['epoch']},{r['train_loss']}\n")
    return metrics


if __name__ == "__main__":
    m = train_and_evaluate({"lr": 1e-3, "batch_size": 128, "optimizer": "adam", "epochs": 1})
    print(m)
