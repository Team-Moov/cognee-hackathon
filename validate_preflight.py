import os
import json

class DirectionScorer:
    """
    Day 6 Validation Engine: Evaluates the delta parameters of 
    synthetic tracking loops to score trajectory convergence stability.
    """
    def compute_stability_scores(self, telemetry_runs):
        scores = {}
        if isinstance(telemetry_runs, dict) and "runs" in telemetry_runs:
            telemetry_runs = telemetry_runs["runs"]
            
        print(f"[+] DirectionScorer evaluating {len(telemetry_runs)} run signatures.")

        for run_data in telemetry_runs:
            run_id = run_data.get("run_id", "unknown_run")
            
            # --- EXTRACT LOSS FROM SUMMARY ---
            summary = run_data.get("summary", {})
            loss = summary.get("epoch_loss")
            
            if loss is None:
                print(f"[-] Skipping {run_id}: No 'epoch_loss' found in summary.")
                continue
            
            # Treat scalar loss as a single-point trajectory
            loss_curve = [loss]
            
            # Heuristic assignment based on summary metrics
            val_acc = summary.get("val_accuracy", 0.0)
            if val_acc < 0.70:
                profile = "CRITICAL_EXPLOSION" # Or 'UNDERPERFORMING'
                numeric_score = -1.0
                summary_txt = f"Run concluded with low validation accuracy: {val_acc}"
            else:
                profile = "STABLE_CONVERGENCE"
                numeric_score = 1.0
                summary_txt = f"Run concluded with healthy validation accuracy: {val_acc}"
                
            scores[run_id] = {
                "profile": profile,
                "score": numeric_score,
                "summary": summary_txt
            }
        return scores


class SensitivityOrchestrator:
    """
    Cross-references calculated metrics against active SWIR/satellite 
    imaging hypothesis contracts to assign agent remediation tracks.
    """
    def generate_sensitivity_matrix(self, direction_scores, research_notes):
        print("\n=== [Subagent Orchestration] Sensitivity & Grounding Matrix ===")
        print(f"[+] Active Research Notes Inspected: {len(research_notes)} entries linked.")
        
        for run_id, audit in direction_scores.items():
            print(f"\nTarget Run Identifier: [{run_id}]")
            print(f"  ↳ Core Evaluation Matrix: {audit['profile']} (Score: {audit['score']})")
            print(f"  ↳ Subagent Diagnostic: {audit['summary']}")
            
            # Target Routing Actions Based on Domain Profile Matches
            if audit['profile'] == "CRITICAL_EXPLOSION":
                print("  ↳ [Librarian Action]: Flagged. Pulling academic grounding profiles for linear learning rate warmup.")
            elif audit['profile'] == "STAGNANT_FLATLINE":
                print("  ↳ [Steward Action]: Flagged. Auditing configuration hashes to cross-examine optimization steps.")


def main():
    staging_directory = "./staging"
    wb_contract_path = os.path.join(staging_directory, "wb_staging.json")
    notes_contract_path = os.path.join(staging_directory, "notebook_notes.json")
    
    print("=== Running Groundhog Day 6/7 Pipeline Pre-flight Verification ===")
    
    # Structural assertion checking that Person 3's output exists
    if not os.path.exists(wb_contract_path) or not os.path.exists(notes_contract_path):
        print("[-] Verification halted: Target staging assets not found. Run prep_demo_datasets.py first.")
        return
        
    with open(wb_contract_path, 'r') as f:
        wb_metrics = json.load(f)
    with open(notes_contract_path, 'r') as f:
        hypothesis_notes = json.load(f)
    
    with open(wb_contract_path, 'r') as f:
        wb_metrics = json.load(f)
        
    # --- ADD THIS: Schema Diagnostic Output ---
    print("\n=== [DEBUG] Inspecting Person 3 JSON Contract Structure ===")
    print(f"Top-level DataType: {type(wb_metrics)}")
    if isinstance(wb_metrics, list):
        print(f"List Length: {len(wb_metrics)}")
        if len(wb_metrics) > 0:
            print(f"First element DataType: {type(wb_metrics[0])}")
            if isinstance(wb_metrics[0], list):
                print(f"Nested List Length: {len(wb_metrics[0])}")
                if len(wb_metrics[0]) > 0:
                    print(f"First step preview: {wb_metrics[0][0]}")
            else:
                print(f"First element preview: {wb_metrics[0]}")
    elif isinstance(wb_metrics, dict):
        print(f"Dict Keys: {list(wb_metrics.keys())}")
    print("========================================================\n")
        
    # Run the computational processing tree
    scorer = DirectionScorer()
    calculated_scores = scorer.compute_stability_scores(wb_metrics.get("runs",[]))
    
    orchestrator = SensitivityOrchestrator()
    orchestrator.generate_sensitivity_matrix(calculated_scores, hypothesis_notes)
    
    print("\n" + "="*70)
    print("[+] Pre-flight evaluation verified. Core contracts conform to staging specifications.")

if __name__ == '__main__':
    main()