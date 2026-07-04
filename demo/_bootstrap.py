"""
_bootstrap.py — shared setup for the demo notebook + pages.

Mirrors the real researcher flow: create a Groundhog project once (→ get a
project_id), then every notebook/script points the SDK at that id so all runs
land in one isolated memory. The project_id is cached in `.demo_project.json`
so the notebook and every page under pages/ share the SAME project.

It also (optionally) attaches W&B credentials to the project when the
WANDB_ENTITY / WANDB_PROJECT / WANDB_API_KEY environment variables are set, so
the W&B round-trip page can push app runs out to W&B and sync W&B runs back in.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "sdk"))   # import groundhog
sys.path.insert(0, ROOT)                          # import demo.train_lib

BACKEND = os.getenv("GROUNDHOG_API_URL", "http://localhost:8000")
_PROJ_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".demo_project.json")

PROJECT_NAME = "Blobs3 SGD Demo"
SIGNIFICANT_KEYS = ["model", "optimizer", "lr", "batch_size", "weight_decay", "epochs"]
OUTPUT_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outputs")


def _http(method: str, path: str, payload=None, timeout: float = 30.0):
    url = BACKEND.rstrip("/") + path
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


def _saved_project_id():
    if os.path.exists(_PROJ_FILE):
        try:
            return json.load(open(_PROJ_FILE, encoding="utf-8")).get("project_id")
        except Exception:
            return None
    return None


def _project_exists(pid: str) -> bool:
    try:
        _http("GET", f"/api/projects/{pid}")
        return True
    except urllib.error.HTTPError:
        return False
    except urllib.error.URLError as e:
        raise SystemExit(f"[demo] backend unreachable at {BACKEND} — is it running? ({e.reason})")


def ensure_project() -> str:
    """Reuse the cached project if it still exists, else create a fresh one."""
    pid = _saved_project_id()
    if pid and _project_exists(pid):
        return pid
    proj = _http("POST", "/api/projects", {
        "name": PROJECT_NAME, "significant_keys": SIGNIFICANT_KEYS,
    })
    pid = proj["project_id"]
    with open(_PROJ_FILE, "w", encoding="utf-8") as fh:
        json.dump({"project_id": pid, "name": PROJECT_NAME}, fh, indent=2)
    print(f"[demo] created project {pid}")
    return pid


def maybe_attach_wandb(pid: str) -> bool:
    """Attach W&B creds from env to the project (enables the round-trip page)."""
    entity = os.getenv("WANDB_ENTITY")
    project = os.getenv("WANDB_PROJECT")
    api_key = os.getenv("WANDB_API_KEY")
    if not (project and api_key):
        return False
    _http("POST", f"/api/projects/{pid}/wandb",
          {"entity": entity, "project": project, "api_key": api_key})
    print(f"[demo] attached W&B creds ({entity or '-'}/{project}) to {pid}")
    return True


def init(experiment: str | None = None):
    """Ensure the project exists and point the groundhog SDK at it."""
    import groundhog
    pid = ensure_project()
    maybe_attach_wandb(pid)
    groundhog.init(project_id=pid, base_url=BACKEND, experiment=experiment)
    return pid


if __name__ == "__main__":
    print("project_id:", init())
