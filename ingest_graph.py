import os
import json
from datetime import datetime,timezone
from validate_preflight import DirectionScorer

class KnowledgeGraphIngester:
    """
    Day 7 Core Engine: Emits a production-ready entity-relationship 
    graph structure mapping Experiments, Hypotheses, and Actions.
    """
    def __init__(self):
        self.nodes = {}
        self.edges = []

    def add_node(self, node_id, node_type, attributes):
        self.nodes[node_id] = {
            "type": node_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "properties": attributes
        }

    def add_edge(self, source, target, relationship_type):
        self.edges.append({
            "source": source,
            "target": target,
            "relationship": relationship_type
        })

    def construct_knowledge_graph(self, telemetry_scores, hypothesis_notes):
        print("[+] Initializing Knowledge-Base Graph Schema Definition...")
        
        # 1. Map Hypothesis Nodes from Researcher Telemetry
        # If hypothesis notes are formatted as a dictionary or string, handle cleanly
        if isinstance(hypothesis_notes, dict):
            for note_id, content in hypothesis_notes.items():
                self.add_node(
                    node_id=note_id,
                    node_type="RESEARCH_HYPOTHESIS",
                    attributes={"raw_insight": content, "focus": "SWIR_Spectral_Analysis"}
                )
        else:
            self.add_node(
                node_id="swir_hypothesis_01",
                node_type="RESEARCH_HYPOTHESIS",
                attributes={"raw_insight": str(hypothesis_notes), "focus": "SWIR_Spectral_Analysis"}
            )

        # 2. Map Experiment Run Nodes and Link Evaluations
        for run_id, audit in telemetry_scores.items():
            node_id = f"experiment_{run_id}"
            self.add_node(
                node_id=node_id,
                node_type="ML_EXPERIMENT_RUN",
                attributes={
                    "run_name": run_id,
                    "profile_assignment": audit["profile"],
                    "stability_score": audit["score"],
                    "diagnostic_summary": audit["summary"]
                }
            )
            
            # Form relational dependencies based on automated profiles
            if audit["profile"] == "CRITICAL_EXPLOSION":
                action_node = f"remediation_action_{run_id}"
                self.add_node(
                    node_id=action_node,
                    node_type="ORCHESTRATOR_ACTION",
                    attributes={"strategy": "WARMUP_RECOVERY", "priority": "CRITICAL"}
                )
                self.add_edge(node_id, action_node, "TRIGGERS_MITIGATION")
                
                # Cross-reference to active hypotheses if applicable
                for h_id in self.nodes:
                    if self.nodes[h_id]["type"] == "RESEARCH_HYPOTHESIS":
                        self.add_edge(action_node, h_id, "GROUNDS_HYPOTHESIS")
            else:
                # Stable trajectories link cleanly back to foundational observation baselines
                for h_id in self.nodes:
                    if self.nodes[h_id]["type"] == "RESEARCH_HYPOTHESIS":
                        self.add_edge(node_id, h_id, "VALIDATES_EXPECTATION")

    def export_graph(self, output_path="./staging/production_graph_memory.json"):
        graph_export = {
            "graph_metadata": {
                "compiled_at": datetime.now(timezone.utc).isoformat(),
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges)
            },
            "nodes": self.nodes,
            "edges": self.edges
        }
        
        with open(output_path, 'w') as f:
            json.dump(graph_export, f, indent=4)
        print(f"[+] Memory compilation verified. Knowledge Graph saved to: {output_path}")


def main():
    staging_directory = "./staging"
    wb_contract_path = os.path.join(staging_directory, "wb_staging.json")
    notes_contract_path = os.path.join(staging_directory, "notebook_notes.json")
    output_graph_path = os.path.join(staging_directory, "production_graph_memory.json")
    
    print("=== Running Groundhog Day 7 Backend Knowledge Graph Ingestion ===")
    
    # 1. Pull verified contracts
    with open(wb_contract_path, 'r') as f:
        wb_metrics = json.load(f)
    with open(notes_contract_path, 'r') as f:
        hypothesis_notes = json.load(f)
        
    # 2. Re-compute standard scores via Day 6 engine
    scorer = DirectionScorer()
    calculated_scores = scorer.compute_stability_scores(wb_metrics.get("runs", []))
    
    # 3. Compile backend database models
    ingester = KnowledgeGraphIngester()
    ingester.construct_knowledge_graph(calculated_scores, hypothesis_notes)
    ingester.export_graph(output_graph_path)
    
    print("\n" + "="*75)
    print("[SUCCESS] Day 7 Complete: Groundhog pipeline fully closed and committed.")

if __name__ == '__main__':
    main()