"""
watcher.py — File Watcher Connector

Monitors a configurable directory for new/modified .yaml/.json files
matching a result-log shape. Runs as a background thread inside the
FastAPI process (single-process constraint from Section 2).

The watcher calls remember_run() from memory.py — it does NOT import cognee
directly, maintaining the single-gatekeeper architecture.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from threading import Thread
from typing import Any, Dict, Optional, Set

import yaml
from watchdog.events import FileCreatedEvent, FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

logger = logging.getLogger("groundhog.watcher")

# ---------------------------------------------------------------------------
# Field mapping: result-log file → remember_run input shape
# ---------------------------------------------------------------------------

def _adapt_file_to_run_data(raw: Dict[str, Any], file_path: str) -> Dict[str, Any]:
    """
    Map a result-log file's fields into the remember_run() input shape.

    The watcher won't have rationale text — generate a minimal one from metrics
    so summary_text embeddings are still useful.
    """
    config_params = (
        raw.get("config")
        or raw.get("hyperparameters")
        or raw.get("params")
        or {}
    )
    result_metrics = (
        raw.get("metrics")
        or raw.get("results")
        or raw.get("eval")
        or {}
    )
    status = raw.get("status", "completed")

    # Auto-generate rationale from metrics when none is provided
    metric_strs = [f"{k}={v}" for k, v in result_metrics.items()]
    auto_rationale = (
        f"Auto-ingested from file watcher. "
        f"File: {os.path.basename(file_path)}. "
        f"Metrics: {', '.join(metric_strs[:5]) or 'none recorded'}."
    )

    return {
        "config_params": config_params,
        "result_metrics": result_metrics,
        "status": status,
        "rationale": raw.get("rationale") or raw.get("notes") or auto_rationale,
        "experiment_name": raw.get("experiment") or raw.get("experiment_name") or "watcher_experiment",
        "experiment_description": raw.get("description") or "Auto-ingested by file watcher",
        "owner": raw.get("owner") or raw.get("researcher") or "watcher",
        "thread_name": raw.get("thread") or raw.get("research_thread") or "default",
        "hypothesis": raw.get("hypothesis") or "",
        "dataset_name_label": raw.get("dataset") or raw.get("dataset_name") or "unknown",
        "dataset_version": raw.get("dataset_version") or "v1",
        "preprocessing_notes": raw.get("preprocessing_notes") or "",
        "split_rationale": raw.get("split_rationale") or "",
        "quality_issues": raw.get("quality_issues") or "",
        "gpu_hours": raw.get("gpu_hours"),
        "wall_clock_seconds": raw.get("wall_clock_seconds") or raw.get("elapsed_seconds"),
        "output_dir": raw.get("output_dir") or os.path.dirname(file_path),
        "git_commit": raw.get("git_commit") or raw.get("commit") or "unknown",
    }


def _load_file(path: str) -> Optional[Dict[str, Any]]:
    """Load a YAML or JSON file, return None on parse error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            if path.endswith(".yaml") or path.endswith(".yml"):
                return yaml.safe_load(f) or {}
            else:
                return json.load(f)
    except Exception as e:
        logger.error("Failed to parse file %s: %s", path, e)
        return None


def _is_result_log(data: Dict[str, Any]) -> bool:
    """
    Heuristic: does this file look like an ML result log?
    Must have at least config/params/hyperparameters OR metrics/results.
    """
    has_config = any(k in data for k in ("config", "hyperparameters", "params"))
    has_metrics = any(k in data for k in ("metrics", "results", "eval"))
    return has_config or has_metrics


# ---------------------------------------------------------------------------
# Watchdog event handler
# ---------------------------------------------------------------------------

class ResultFileHandler(FileSystemEventHandler):
    """
    Handles file creation/modification events in the watched directory.
    Dispatches ingestion via the event loop shared with FastAPI.
    """

    def __init__(self, loop: asyncio.AbstractEventLoop, dataset_name: str = "main_dataset"):
        super().__init__()
        self.loop = loop
        self.dataset_name = dataset_name
        self._processed: Set[str] = set()  # deduplicate rapid events

    def _should_process(self, path: str) -> bool:
        ext = Path(path).suffix.lower()
        return ext in {".yaml", ".yml", ".json"}

    def on_created(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            self._ingest(event.src_path)

    def on_modified(self, event):
        if not event.is_directory and self._should_process(event.src_path):
            self._ingest(event.src_path)

    def _ingest(self, path: str):
        # Deduplicate: watchdog sometimes fires twice for one write
        key = f"{path}:{os.path.getmtime(path):.0f}"
        if key in self._processed:
            return
        self._processed.add(key)
        # Keep set bounded
        if len(self._processed) > 500:
            self._processed.clear()

        logger.info("Watcher: new file detected: %s", path)

        # Give the OS time to finish writing the file
        time.sleep(0.5)

        raw = _load_file(path)
        if raw is None:
            return
        if not _is_result_log(raw):
            logger.debug("Watcher: file does not look like a result log, skipping: %s", path)
            return

        run_data = _adapt_file_to_run_data(raw, path)
        # Schedule coroutine in the FastAPI event loop (thread-safe)
        future = asyncio.run_coroutine_threadsafe(
            _ingest_async(run_data, self.dataset_name, path),
            self.loop,
        )
        # Log completion / errors from the future
        def _on_done(fut):
            try:
                result = fut.result(timeout=120)
                logger.info(
                    "Watcher: ingested %s -> node_id=%s config_hash=%s",
                    os.path.basename(path),
                    result.get("node_id"),
                    result.get("config_hash", "")[:12],
                )
            except Exception as e:
                logger.error("Watcher: ingestion failed for %s: %s", path, e)

        future.add_done_callback(_on_done)


async def _ingest_async(run_data: Dict[str, Any], dataset_name: str, file_path: str) -> Dict[str, Any]:
    """Async wrapper called from the watcher thread via run_coroutine_threadsafe."""
    # Import here to avoid circular import at module level
    from memory import remember_run
    result = await remember_run(run_data, dataset_name=dataset_name)
    return result


# ---------------------------------------------------------------------------
# Watcher startup / shutdown
# ---------------------------------------------------------------------------

_observer: Optional[Observer] = None


def start_watcher(watch_dir: str, loop: asyncio.AbstractEventLoop, dataset_name: str = "main_dataset"):
    """
    Start the watchdog observer in a daemon thread.
    Called once at FastAPI startup.
    """
    global _observer

    watch_dir = os.path.abspath(watch_dir)
    os.makedirs(watch_dir, exist_ok=True)
    logger.info("Starting file watcher on: %s", watch_dir)

    handler = ResultFileHandler(loop=loop, dataset_name=dataset_name)
    _observer = Observer()
    _observer.schedule(handler, watch_dir, recursive=True)
    _observer.daemon = True
    _observer.start()
    logger.info("File watcher started (thread=%s)", _observer.name)


def stop_watcher():
    """Stop the watchdog observer gracefully. Called at FastAPI shutdown."""
    global _observer
    if _observer and _observer.is_alive():
        logger.info("Stopping file watcher...")
        _observer.stop()
        _observer.join(timeout=5)
        logger.info("File watcher stopped.")
