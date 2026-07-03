import os
import json
from datetime import datetime, UTC
from subagents.dataset_steward import DatasetSteward
from subagents.literature_agent import LiteratureAgent

def execute_subagent_pipeline():
    print("=== [Day 5] Triggering Groundhog Subagent Orchestration ===")
    steward = DatasetSteward()
    lit_agent = LiteratureAgent()
    
    steward_results = steward.analyze_dataset_integrity()
    lit_results = lit_agent.fetch_grounding_literature()
    
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "dataset_steward_evaluation": steward_results,
        "literature_agent_evaluation": lit_results
    }
    
    staging_dir = os.path.join(os.path.dirname(__file__), "staging")
    output_file = os.path.join(staging_dir, "subagent_insights.json")
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=4, default=str)
        
    print("\n[+] Subagent pipelines completed successfully!")
    print(f"    - Cached structural insights file to: {output_file}")
if __name__ == "__main__":
    execute_subagent_pipeline()
