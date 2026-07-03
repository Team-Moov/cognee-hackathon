import os
import json
import wandb
import numpy as np

class DatasetSteward:
    def __init__(self):
        self.api = wandb.Api()
        self.entity = os.getenv("WANDB_ENTITY") or self.api.default_entity
        self.project = os.getenv("WANDB_PROJECT")

    def analyze_dataset_integrity(self):
        # If environment variables are missing or blank, prompt immediately
        if not self.entity:
            self.entity = input("[?] Enter your W&B Entity/Username: ").strip()
        if not self.project:
            self.project = input("[?] Enter your W&B Project Name: ").strip()

        while True:
            path = f"{self.entity}/{self.project}"
            print(f"\n[*] Dataset Steward attempting analysis on cloud path: '{path}'...")
            try:
                runs = list(self.api.runs(path))
                break  # Success, break out of confirmation loop
            except Exception as e:
                print(f"\n[!] Connection Error: Could not access project '{self.project}' under entity '{self.entity}'.")
                try:
                    real_projects = [p.name for p in self.api.projects(self.entity)]
                    print(f"    Available projects found on your profile: {real_projects}")
                except Exception:
                    print("    Could not auto-fetch available projects from profile. Check your internet connection or API key.")
                
                print("\n--- Adjust W&B Connection Parameters ---")
                self.entity = input(f"[?] Enter Entity [{self.entity}]: ").strip() or self.entity
                self.project = input(f"[?] Enter Project [{self.project}]: ").strip() or self.project

        if not runs:
            print(f"[!] Warning: Project '{path}' accessed successfully but contains 0 runs.")
            return {
                "subagent": "DatasetSteward",
                "computed_target_path": path,
                "monitored_population_size": 0,
                "drift_detected": False,
                "computed_statistical_anomaly_score": 0.0,
                "steward_critique": ["Target workspace contains no active telemetry matrix data lines."]
            }
            
        losses = []
        accuracies = []
        run_metadata = []

        for run in runs:
            loss = run.summary.get("epoch_loss") or run.summary.get("train/loss") or run.summary.get("loss")
            acc = run.summary.get("val_accuracy") or run.summary.get("val/acc") or run.summary.get("accuracy")
            
            if loss is not None and acc is not None:
                losses.append(float(loss))
                accuracies.append(float(acc))
                run_metadata.append({"id": run.id, "loss": float(loss), "acc": float(acc)})

        warnings = []
        drift_detected = False
        anomaly_score = 0.0

        if len(run_metadata) > 2:
            mean_loss = np.mean(losses)
            std_loss = np.std(losses)
            
            for rm in run_metadata:
                z_loss = (rm["loss"] - mean_loss) / (std_loss if std_loss > 0 else 1.0)
                if z_loss < -1.0:
                    drift_detected = True
                    warnings.append(f"Run [{rm['id']}] flagged as structural statistical outlier.")
            anomaly_score = float(np.var(accuracies))
        else:
            warnings.append(f"Baseline Warning: Workspace context has less than 3 valid tracking runs.")

        return {
            "subagent": "DatasetSteward",
            "computed_target_path": path,
            "monitored_population_size": len(run_metadata),
            "drift_detected": drift_detected,
            "computed_statistical_anomaly_score": min(round(anomaly_score, 4), 1.0),
            "steward_critique": warnings
        }
