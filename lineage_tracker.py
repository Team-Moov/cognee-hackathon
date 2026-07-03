import os
import json
import subprocess
from datetime import datetime, UTC

class LineageTracker:
    def __init__(self):
        self.staging_dir = os.path.join(os.path.dirname(__file__), "staging")
        self.output_file = os.path.join(self.staging_dir, "lineage_staging.json")
        os.makedirs(self.staging_dir, exist_ok=True)

    def get_git_metadata(self):
        try:
            # Query the live shell for the precise current commit hash
            commit = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
            branch = subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"]).decode("utf-8").strip()
            return {"commit_hash": commit, "active_branch": branch}
        except Exception:
            return {"commit_hash": "uninitialized_repository", "active_branch": "detached"}

    def scan_workspace_assets(self):
        # Dynamically calculate sizes and existence of local files to prevent hardcoded manifests
        assets = []
        target_dirs = ["./data", "./staging", "./checkpoints"]
        
        for directory in target_dirs:
            if os.path.exists(directory):
                for root, _, files in os.walk(directory):
                    for file in files:
                        path = os.path.join(root, file)
                        assets.append({
                            "file_name": file,
                            "file_path": path,
                            "size_bytes": os.path.getsize(path),
                            "last_modified": datetime.fromtimestamp(os.path.getmtime(path), UTC).isoformat()
                        })
        return assets

    def generate_live_lineage(self):
        print("[*] Gathering real-time workspace tracking metrics and git states...")
        
        git_state = self.get_git_metadata()
        active_assets = self.scan_workspace_assets()

        lineage_payload = {
            "tracking_timestamp": datetime.now(UTC).isoformat(),
            "environment_metadata": git_state,
            "detected_workspace_files": active_assets,
            "pipeline_stages": {
                "description": "Dynamic structural maps can be inferred by Person 1 via asset creation order timestamps.",
                "total_tracked_assets": len(active_assets)
            }
        }

        with open(self.output_file, "w", encoding="utf-8") as f:
            json.dump(lineage_payload, f, indent=4)

        print(f"[+] Dynamic lineage verification generated successfully at: {self.output_file}")

if __name__ == "__main__":
    LineageTracker().generate_live_lineage()
