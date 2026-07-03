# connectors/wandb_bridge.py
import os
import json
import hashlib
import uuid
import wandb

class WandbBridge:
    def __init__(self, project_path: str):
        self.api = wandb.Api()
        self.project_path = project_path
        # Create a staging folder at the root level of your project
        self.staging_dir = os.path.join(os.path.dirname(__file__), "..", "staging")
        self.staging_file = os.path.join(self.staging_dir, "wb_staging.json")
        
        os.makedirs(self.staging_dir, exist_ok=True)

    def _generate_deterministic_hash(self, parameters: dict) -> str:
        """Normalized configuration sorting prevents out-of-order string collisions."""
        normalized_str = json.dumps(parameters, sort_keys=True, default=str)
        return hashlib.sha256(normalized_str.encode('utf-8')).hexdigest()

    def _create_config_summary(self, params: dict) -> str:
        model = params.get("model", params.get("model_name", "Unknown Model"))
        opt = params.get("optimizer", "Unknown Optimizer")
        lr = params.get("lr", params.get("learning_rate", "N/A"))
        return f"Config Setup: Running {model} model with {opt} optimizer. Learning rate: {lr}."

    def _create_result_summary(self, state: str, metrics: dict, notes: str) -> str:
        loss = metrics.get("val_loss", metrics.get("loss", "N/A"))
        acc = metrics.get("val_accuracy", metrics.get("accuracy", "N/A"))
        summary = f"Run status: {state}. Final val loss: {loss}, val accuracy: {acc}."
        if notes:
            summary += f" Developer notes: {notes}"
        return summary

    def parse_project_runs(self):
        print(f"[*] Extracting tracking runs from W&B project: {self.project_path}...")
        try:
            runs = self.api.runs(self.project_path)
        except Exception as e:
            print(f"[-] W&B API Connection Failed: {e}.")
            print("[!] Make sure TARGET_PROJECT matches 'your_username/your_project_name'")
            return

        payload = {"configs": [], "results": [], "artifacts": []}

        for run in runs:
            config_id = str(uuid.uuid4())
            result_id = str(uuid.uuid4())
            
            # Extract Hyperparameters
            clean_config = {k: v for k, v in run.config.items() if not k.startswith("_")}
            c_hash = self._generate_deterministic_hash(clean_config)
            
            payload["configs"].append({
                "id": config_id,
                "parameters": clean_config,
                "summary_text": self._create_config_summary(clean_config),
                "config_hash": c_hash,
                "research_thread_id": run.group if run.group else "default_thread"
            })

            # Extract Metrics
            clean_metrics = {k: v for k, v in run.summary.items() if not k.startswith("_")}
            wall_clock = run.summary.get("_runtime", 0.0)
            
            payload["results"].append({
                "id": result_id,
                "config_id": config_id,
                "metrics": clean_metrics,
                "gpu_hours": round(wall_clock / 3600.0, 2) if wall_clock else 0.0,
                "wall_clock_seconds": float(wall_clock),
                "status": run.state,
                "summary_text": self._create_result_summary(run.state, clean_metrics, run.notes),
                "promoted": "promoted" in run.tags,
                "hard_examples": [] # Structural evaluation placeholder
            })

        with open(self.staging_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=4, default=str)

        print(f"[+] Extraction complete! Cached {len(payload['configs'])} runs to: {self.staging_file}")
        print("[*] This file is a staging cache, not memory yet. Run "
              "`python connectors/flush_staging_to_cognee.py` (with the cognee "
              "server up on port 8010) to actually ingest these runs into the graph.")

if __name__ == "__main__":
    # ⚠️ EDIT THIS LINE: Replace with your actual W&B account/entity name and a project name
    TARGET_PROJECT = "bananyadas-manipal/Groundhog"
    
    if "your_wandb_username" in TARGET_PROJECT:
        print("[!] Workspace Notice: Please open connectors/wandb_bridge.py and change TARGET_PROJECT to point to a real W&B project path.")
    else:
        bridge = WandbBridge(TARGET_PROJECT)
        bridge.parse_project_runs()