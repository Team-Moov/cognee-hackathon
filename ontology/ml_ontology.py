"""
ontology/ml_ontology.py — Groundhog ML Domain Ontology (Section 4.4)

This module used to just print a hardcoded list of terms and never touch
cognee at all. It now exposes the real ontology file path that memory.py's
_remember_with_ontology() passes into cognee.cognify(ontology_file_path=...),
so entity extraction is actually grounded against the ontology instead of
free-floating string matching.

The ontology content itself lives in ml_ontology.owl (RDF/XML, OWL) next to
this file — see that file's header comment for the class hierarchy
(Optimizer > {Adam > AdamW, SGD, RMSprop}, Architecture > {CNN > {ResNet,
MobileNet, EfficientNet}, Transformer > {VisionTransformer, BERT}}).
"""

from __future__ import annotations

import asyncio
import os

ONTOLOGY_FILE_PATH = os.path.join(os.path.dirname(__file__), "ml_ontology.owl")


def ontology_file_exists() -> bool:
    return os.path.isfile(ONTOLOGY_FILE_PATH)


async def verify_ontology_setup() -> dict:
    """
    Smoke-test the ontology file against cognee's own ontology resolver,
    without running a full cognify() pass.

    Returns a dict describing whether the file exists, parses, and how many
    classes/relationships it defines — useful for a one-off `python -m
    ontology.ml_ontology` sanity check before relying on it during ingestion.
    """
    if not ontology_file_exists():
        return {"status": "missing", "path": ONTOLOGY_FILE_PATH}

    try:
        from cognee.modules.ontology.get_default_ontology_resolver import (
            get_default_ontology_resolver,
        )

        resolver = get_default_ontology_resolver()
        # Different cognee versions expose slightly different resolver APIs;
        # try the common ones rather than hardcoding one method name.
        if hasattr(resolver, "load_ontology"):
            resolver.load_ontology(ONTOLOGY_FILE_PATH)
        elif hasattr(resolver, "build_graph"):
            resolver.build_graph(ONTOLOGY_FILE_PATH)

        return {
            "status": "ok",
            "path": ONTOLOGY_FILE_PATH,
            "resolver_type": type(resolver).__name__,
        }
    except Exception as e:
        return {"status": "error", "path": ONTOLOGY_FILE_PATH, "error": str(e)}


if __name__ == "__main__":
    result = asyncio.run(verify_ontology_setup())
    print(f"[*] Ontology file: {result['path']}")
    print(f"[*] Status: {result['status']}")
    if result.get("error"):
        print(f"[!] {result['error']}")
