import subprocess
import sys
import time
import os

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

def start_process(name, cmd, cwd=ROOT_DIR):
    print(f"[*] Starting {name}...")
    # Use Popen to run in background
    return subprocess.Popen(
        cmd,
        cwd=cwd,
        shell=True, # Required for npm on Windows
        stdout=sys.stdout,
        stderr=sys.stderr
    )

def main():
    print("=======================================")
    print("      Starting Groundhog Services      ")
    print("=======================================\n")
    
    procs = []
    try:
        # 1. Start Cognee Memory Server (Port 8010)
        procs.append(start_process("Cognee Server", f"{sys.executable} main.py"))
        
        # Give it a second to bind
        time.sleep(2)
        
        # 2. Start Backend API Gateway (Port 8000)
        backend_dir = os.path.join(ROOT_DIR, "backend")
        procs.append(start_process("Backend API", f"{sys.executable} -m uvicorn app.main:app --port 8000", cwd=backend_dir))
        
        # 3. Start Frontend Dashboard (Port 5173)
        frontend_dir = os.path.join(ROOT_DIR, "frontend")
        procs.append(start_process("Frontend", "npm run dev", cwd=frontend_dir))

        print("\n[+] All services started! Groundhog UI is available at: http://localhost:5173")
        print("[+] W&B sync loop will run automatically in the backend for enabled projects.")
        print("[*] Press Ctrl+C to shut everything down cleanly.\n")

        # Keep main thread alive
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n[*] Shutting down Groundhog services...")
        for p in procs:
            p.terminate()
        for p in procs:
            p.wait()
        print("[+] Shutdown complete.")

if __name__ == "__main__":
    main()
