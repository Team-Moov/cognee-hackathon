import wandb
import time

print("[*] Initializing live connection to push baseline metrics to W&B cloud...")
run = wandb.init(project="Groundhog", name="demo-run-01")

# Simulate a quick live logging loop
for epoch in range(1, 6):
    wandb.log({
        "epoch": epoch,
        "epoch_loss": 0.04 if epoch == 5 else 0.3 / epoch,
        "val_accuracy": 0.65 if epoch == 5 else 0.5 + (epoch * 0.05)
    })
    time.sleep(0.5)

# Sync the final summaries explicitly
run.summary["epoch_loss"] = 0.04
run.summary["val_accuracy"] = 0.65
run.finish()
print("[+] Seed run successfully uploaded to your cloud dashboard!")
