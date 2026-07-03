"""
shared/schema.py — compatibility shim.

The canonical Groundhog graph schema lives in the repo-root ``schema.py``. This
module used to be an empty placeholder; it now simply re-exports the real schema
so ``from shared.schema import Experiment`` and ``from schema import Experiment``
refer to the exact same DataPoint classes (one source of truth, no drift).
"""

from __future__ import annotations

import os
import sys

# Ensure the repo root (which holds the canonical schema.py) is importable even
# when this subpackage is imported in isolation.
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from schema import (  # noqa: E402,F401
    Experiment,
    ResearchThread,
    Config,
    Dataset,
    Result,
    Artifact,
    Hypothesis,
    Decision,
    AgentAction,
    EDGE_BELONGS_TO,
    EDGE_PRODUCED,
    EDGE_DERIVED_FROM,
    EDGE_FOLLOWED_BY,
    ALL_EDGE_TYPES,
)
