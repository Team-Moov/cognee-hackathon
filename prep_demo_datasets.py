import os
import json
from datetime import datetime, UTC

def prepare_demo_datasets():
    print("=== [Day 6/7 Pre-flight] Building Realist Synthetic ML Runs ===")
    staging_dir = os.path.join(os.path.dirname(__file__), "staging")
    os.makedirs(staging_dir, exist_ok=True)

    # 1. Synthesize W&B Metrics Data (wb_staging.json)
    # Includes an anomaly run to test the Dataset Steward's warning threshold rules!
    wb_data = {
        "runs": [
            {
                "run_id": "run_stable_baseline_01",
                "config_hash": "a4f89c2b3e81109a",
                "hyperparameters": {"learning_rate": 0.001, "batch_size": 32, "optimizer": "AdamW"},
                "summary": {"epoch_loss": 0.15, "val_accuracy": 0.89, "gpu_hours": 4.2}
            },
            {
                "run_id": "run_overfitted_variant_02",
                "config_hash": "f9e210cd45ba6789",
                "hyperparameters": {"learning_rate": 0.05, "batch_size": 128, "optimizer": "SGD"},
                "summary": {"epoch_loss": 0.04, "val_accuracy": 0.62, "gpu_hours": 1.5}
            }
        ]
    }

    # 2. Synthesize Researcher Hypothesis Logs (notebook_notes.json)
    notes_data = [
        {
            "timestamp": datetime.now(UTC).isoformat(),
            "cell_source": "%%log_hypothesis\nTesting if expanding spectral filters into SWIR bands fixes cloudy day misclassifications.",
            "statement": "Adding self-supervised SWIR mask tokens increases model stability on occluded samples.",
            "duration_ms": 450
        }
    ]

    # Write out the structural demo data targets
    with open(os.path.join(staging_dir, "wb_staging.json"), "w", encoding="utf-8") as f:
        json.dump(wb_data, f, indent=4)
    with open(os.path.join(staging_dir, "notebook_notes.json"), "w", encoding="utf-8") as f:
        json.dump(notes_data, f, indent=4)

    print("[+] Demo datasets prepared successfully inside the ./staging directory:")
    print("    - Generated staging/wb_staging.json (Contains baseline and overfitted runs)")
    print("    - Generated staging/notebook_notes.json (Contains active SWIR hypothesis logs)")

if __name__ == "__main__":
    prepare_demo_datasets()
