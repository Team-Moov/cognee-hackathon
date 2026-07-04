# connectors/jupyter_magic.py
import os
import json
import uuid
from datetime import datetime
from IPython.core.magic import Magics, magics_class, line_magic, cell_magic

@magics_class
class GroundhogMagics(Magics):
    def __init__(self, shell):
        super(GroundhogMagics, self).__init__(shell)
        self.staging_dir = os.path.join(os.path.dirname(__file__), "..", "staging")
        self.notes_file = os.path.join(self.staging_dir, "notebook_notes.json")
        os.makedirs(self.staging_dir, exist_ok=True)

    def _append_to_notes(self, entry_type: str, data: dict):
        """Appends structured metadata notes to the local staging cache."""
        current_notes = {"hypotheses": [], "decisions": [], "cell_observations": []}
        
        if os.path.exists(self.notes_file):
            try:
                with open(self.notes_file, "r", encoding="utf-8") as f:
                    current_notes = json.load(f)
            except Exception:
                pass # Fall back to clean structure if file is corrupted

        current_notes[entry_type].append(data)

        with open(self.notes_file, "w", encoding="utf-8") as f:
            json.dump(current_notes, f, indent=4, default=str)

    @line_magic
    def groundhog_hypothesis(self, line):
        """Usage: %groundhog_hypothesis Changing weight decay to 0.01 to see if overfitting stops."""
        if not line.strip():
            print("[-] Error: Please provide a hypothesis statement.")
            return
        
        # Try to sync instantly via the SDK if initialized
        try:
            import groundhog
            if groundhog.config().get("project_id"):
                groundhog.remember(
                    config={"_type": "notebook_hypothesis"},
                    metrics={},
                    rationale=f"Hypothesis: {line.strip()}",
                    hypothesis=line.strip(),
                    experiment="notebook_scratch",
                    thread="default_thread"
                )
                print(f"[+] Groundhog instantly logged hypothesis to project '{groundhog.config().get('project_id')}': '{line.strip()}'")
                return
        except (ImportError, RuntimeError):
            pass

        # Fallback to offline staging
        payload = {
            "id": str(uuid.uuid4()),
            "statement": line.strip(),
            "timestamp": datetime.utcnow().isoformat(),
            "status": "PROPOSED",
            "research_thread_id": "default_thread"
        }
        self._append_to_notes("hypotheses", payload)
        print(f"[+] Groundhog cached hypothesis (SDK not initialized): '{line.strip()}'")

    @line_magic
    def groundhog_decision(self, line):
        """Usage: %groundhog_decision Aborting SGD runs. Learning rate convergence is too flat."""
        if not line.strip():
            print("[-] Error: Please provide a decision rationale.")
            return

        # Try to sync instantly via the SDK if initialized
        try:
            import groundhog
            if groundhog.config().get("project_id"):
                groundhog.remember(
                    config={"_type": "notebook_decision"},
                    metrics={},
                    rationale=line.strip(),
                    experiment="notebook_scratch",
                    thread="default_thread"
                )
                print(f"[+] Groundhog instantly logged decision to project '{groundhog.config().get('project_id')}': '{line.strip()}'")
                return
        except (ImportError, RuntimeError):
            pass

        # Fallback to offline staging
        payload = {
            "id": str(uuid.uuid4()),
            "description": "Notebook analytical intervention",
            "rationale": line.strip(),
            "timestamp": datetime.utcnow().isoformat(),
            "research_thread_id": "default_thread"
        }
        self._append_to_notes("decisions", payload)
        print(f"[+] Groundhog cached decision intervention (SDK not initialized): '{line.strip()}'")

    @cell_magic
    def groundhog_watch(self, line, cell):
        """
        Usage: 
        %%groundhog_watch
        model.fit(X_train, y_train)
        """
        print("[*] Groundhog profiling cell execution context...")
        start_time = datetime.utcnow()
        
        # Execute the original code inside the user's namespace
        result = self.shell.run_cell(cell)
        
        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        # Try to sync instantly via the SDK if initialized
        try:
            import groundhog
            if groundhog.config().get("project_id"):
                groundhog.remember(
                    config={"_type": "notebook_cell_execution"},
                    metrics={"duration_seconds": duration},
                    status="completed" if result.success else "failed",
                    rationale=f"Notebook cell executed:\n{cell[:500]}",
                    experiment="notebook_scratch",
                    thread="cell_observations"
                )
                print(f"[+] Cell execution logged ({round(duration, 3)}s). Synced directly to project '{groundhog.config().get('project_id')}'.")
                return
        except (ImportError, RuntimeError):
            pass

        # Fallback to offline staging
        payload = {
            "id": str(uuid.uuid4()),
            "code_executed": cell,
            "duration_seconds": duration,
            "success": result.success,
            "timestamp": start_time.isoformat()
        }
        self._append_to_notes("cell_observations", payload)
        print(f"[+] Cell execution logged ({round(duration, 3)}s). Cached to offline staging.")


def load_ipython_extension(ipython):
    """Special entrypoint function called implicitly by %load_ext"""
    ipython.register_magics(GroundhogMagics)
    print("\n=======================================================")
    print("[+] Groundhog Researcher Insight Engine Registered.")
    print("    Available macros:")
    print("      - %groundhog_hypothesis <statement>")
    print("      - %groundhog_decision <rationale>")
    print("      - %%groundhog_watch  (Place at top of code cells)")
    print("    Note: Initialize the SDK (`groundhog.init(project_id=...)`) first")
    print("    so these magics instantly sync to your live Cognee memory graph.")
    print("=======================================================\n")