# seed_wandb.py
import wandb
import time
import random

ENTITY = "bananyadas-manipal"
PROJECT = "Groundhog"

def run_simulation():
    print(f"[*] Simulating and uploading 3 historical runs to W&B ({ENTITY}/{PROJECT})...")

    # --- RUN 1: The Successful Baseline ---
    print("\n[1/3] Uploading Run 1: Baseline ResNet50...")
    run1 = wandb.init(
        entity=ENTITY,
        project=PROJECT,
        name="resnet50_baseline",
        notes="Standard baseline run. Model converged nicely with steady validation improvements.",
        tags=["baseline", "promoted"],
        config={"model": "ResNet50", "optimizer": "AdamW", "lr": 0.001, "batch_size": 32}
    )
    # Simulate epochs logging metrics
    for epoch in range(5):
        wandb.log({
            "epoch": epoch,
            "loss": 0.5 / (epoch + 1),
            "val_loss": 0.55 / (epoch + 1),
            "val_accuracy": 0.75 + (epoch * 0.04)
        })
        time.sleep(0.5)
    run1.finish()

    # --- RUN 2: The Catastrophic Failure ---
    print("\n[2/3] Uploading Run 2: High LR Explosion...")
    run2 = wandb.init(
        entity=ENTITY,
        project=PROJECT,
        name="resnet50_lr_explosion",
        notes="Testing aggressive learning rate. Loss completely exploded by epoch 3. Do not repeat.",
        tags=["failed", "high-lr"],
        config={"model": "ResNet50", "optimizer": "AdamW", "lr": 0.1, "batch_size": 32}
    )
    for epoch in range(3):
        loss_val = 0.5 if epoch == 0 else (5.0 if epoch == 1 else 99.9)
        wandb.log({
            "epoch": epoch,
            "loss": loss_val,
            "val_loss": loss_val * 1.1,
            "val_accuracy": 0.20
        })
        time.sleep(0.5)
    # Mark it as a failed run state
    run2.finish() 

    # --- RUN 3: The Slow Convergence (Aborted) ---
    print("\n[3/3] Uploading Run 3: SGD Test...")
    run3 = wandb.init(
        entity=ENTITY,
        project=PROJECT,
        name="resnet50_sgd_slow",
        notes="Trying SGD. Convergence is painfully slow compared to AdamW. Killing run early.",
        tags=["aborted", "sgd"],
        config={"model": "ResNet50", "optimizer": "SGD", "lr": 0.001, "batch_size": 32}
    )
    for epoch in range(2):
        wandb.log({
            "epoch": epoch,
            "loss": 0.49,
            "val_loss": 0.51,
            "val_accuracy": 0.52
        })
        time.sleep(0.5)
    run3.finish()

    print("\n[+] Seeding complete! Check your website dashboard.")

if __name__ == "__main__":
    run_simulation()