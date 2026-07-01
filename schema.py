"""
schema.py — Groundhog Graph Schema

All node types as DataPoint subclasses. Each field is annotated with whether
it is embeddable (indexed for semantic search) or structural-only.

Embeddable fields: text written by humans / models that carries semantic
signal useful for fuzzy recall (hypothesis statements, rationale, notes, etc.)

Structural-only fields: IDs, hashes, numeric metrics, dicts — stored in the
graph/relational layer but NOT embedded. Embedding raw JSON is noise.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import Field, field_validator

try:
    from cognee.infrastructure.engine.models.DataPoint import DataPoint
except ImportError:
    # Fallback for slightly different SDK versions
    from cognee.base_data_point import DataPoint  # type: ignore


# ---------------------------------------------------------------------------
# Experiment — top-level container for a research project
# ---------------------------------------------------------------------------

class Experiment(DataPoint):
    """Top-level container grouping all runs under one research goal."""

    name: str
    description: str  # embeddable — captures research intent
    created_at: datetime = Field(default_factory=datetime.utcnow)
    owner: str  # researcher or team name, structural

    # index_fields tells Cognee which fields to vectorize
    metadata: dict = {"index_fields": ["description"]}


# ---------------------------------------------------------------------------
# ResearchThread — a directional line of related runs
# ---------------------------------------------------------------------------

class ResearchThread(DataPoint):
    """A directional line of related runs pursuing one hypothesis."""

    name: str
    hypothesis_summary: str  # embeddable — the "what we're testing" text
    status: str = "active"  # active | abandoned | promoted — structural enum
    experiment_id: Optional[str] = None  # UUID string, structural FK

    metadata: dict = {"index_fields": ["hypothesis_summary"]}

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"active", "abandoned", "promoted"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}, got '{v}'")
        return v


# ---------------------------------------------------------------------------
# Config — a specific hyperparameter set for one run
# ---------------------------------------------------------------------------

class Config(DataPoint):
    """
    A hyperparameter configuration for a single run.

    parameters: raw dict — stored structurally, NOT embedded (raw JSON is noise)
    summary_text: LLM-generated or programmatic NL description — embedded
    config_hash: deterministic SHA-256 of normalized parameters — structural,
                 used for exact-match Pre-flight Guard lookups
    """

    parameters: Dict[str, Any]  # raw dict — structural only
    summary_text: str  # NL description of the config — embeddable
    config_hash: str  # SHA-256 hex — structural, exact-match key
    research_thread_id: Optional[str] = None  # structural FK

    metadata: dict = {"index_fields": ["summary_text"]}


# ---------------------------------------------------------------------------
# Dataset — a dataset version used in runs
# ---------------------------------------------------------------------------

class Dataset(DataPoint):
    """A versioned dataset with provenance and quality notes."""

    name: str
    version: str = "v1"
    preprocessing_notes: str = ""  # embeddable — how data was cleaned
    split_rationale: str = ""      # embeddable — why this train/val/test split
    quality_issues: str = ""       # embeddable — known problems / caveats
    parent_dataset_id: Optional[str] = None  # nullable FK for transform chains

    metadata: dict = {
        "index_fields": ["preprocessing_notes", "split_rationale", "quality_issues"]
    }


# ---------------------------------------------------------------------------
# Result — outcome of a training run
# ---------------------------------------------------------------------------

class Result(DataPoint):
    """
    Outcome of one run, including both metrics and a narrative summary.

    metrics: raw dict — structural only (embedding {"val_loss": 0.42} is noise)
    summary_text: NL description of what happened — embeddable, supports
                  negative-result recall ("runs where loss exploded")
    """

    metrics: Dict[str, Any]  # structural only
    gpu_hours: Optional[float] = None  # structural
    wall_clock_seconds: Optional[float] = None  # structural
    config_id: Optional[str] = None   # structural FK
    dataset_id: Optional[str] = None  # structural FK
    status: str = "completed"  # completed | aborted | failed — structural
    summary_text: str = ""  # embeddable — NL narrative of what happened
    promoted: bool = False  # structural flag set by promote_to_shared

    metadata: dict = {"index_fields": ["summary_text"]}

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"completed", "aborted", "failed"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}, got '{v}'")
        return v


# ---------------------------------------------------------------------------
# Artifact — a produced file linked to a result
# ---------------------------------------------------------------------------

class Artifact(DataPoint):
    """A file produced by a run — checkpoint, plot, log, eval report."""

    file_path: str  # absolute path on disk — structural
    artifact_type: str  # checkpoint | plot | log | eval_report — structural
    result_id: Optional[str] = None  # structural FK
    description: str = ""  # embeddable — human or auto NL description
    exists_on_disk: bool = True  # structural, updated by orphan detection

    metadata: dict = {"index_fields": ["description"]}

    @field_validator("artifact_type")
    @classmethod
    def validate_type(cls, v: str) -> str:
        allowed = {"checkpoint", "plot", "log", "eval_report", "other"}
        if v not in allowed:
            raise ValueError(f"artifact_type must be one of {allowed}, got '{v}'")
        return v


# ---------------------------------------------------------------------------
# Hypothesis — idea motivating a run or direction
# ---------------------------------------------------------------------------

class Hypothesis(DataPoint):
    """A testable hypothesis motivating a line of experimentation."""

    statement: str  # embeddable — the core claim being tested
    research_thread_id: Optional[str] = None  # structural FK
    status: str = "open"  # open | supported | refuted — structural

    metadata: dict = {"index_fields": ["statement"]}

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        allowed = {"open", "supported", "refuted"}
        if v not in allowed:
            raise ValueError(f"status must be one of {allowed}, got '{v}'")
        return v


# ---------------------------------------------------------------------------
# Decision — a choice made along the way
# ---------------------------------------------------------------------------

class Decision(DataPoint):
    """
    A deliberate choice made by a researcher or agent.

    rationale is the most important embeddable field in the whole schema —
    "why we made this call" is the information most likely to save future
    researchers from repeating the same mistake.
    """

    description: str   # embeddable — what was decided
    rationale: str     # embeddable — WHY it was decided (highest value field)
    made_by: str = "unknown"  # human or agent name — structural
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    research_thread_id: Optional[str] = None  # structural FK

    metadata: dict = {"index_fields": ["description", "rationale"]}


# ---------------------------------------------------------------------------
# AgentAction — an entry from agents.md or an external write
# ---------------------------------------------------------------------------

class AgentAction(DataPoint):
    """
    Records an action taken by a human or agent — decided, abandoned,
    promoted, noted.
    """

    action_type: str  # decided | abandoned | promoted | noted — structural
    parameters: Dict[str, Any] = Field(default_factory=dict)  # structural
    rationale: str = ""  # embeddable — why this action was taken
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str = "unknown"  # human | agent-name — structural

    metadata: dict = {"index_fields": ["rationale"]}

    @field_validator("action_type")
    @classmethod
    def validate_action_type(cls, v: str) -> str:
        allowed = {"decided", "abandoned", "promoted", "noted"}
        if v not in allowed:
            raise ValueError(f"action_type must be one of {allowed}, got '{v}'")
        return v


# ---------------------------------------------------------------------------
# Edge type constants (used in memory.py for graph traversal)
# ---------------------------------------------------------------------------

EDGE_BELONGS_TO = "belongs_to"       # Config/Result/Decision → Experiment or ResearchThread
EDGE_PRODUCED = "produced"           # Config+run → Result; Result → Artifact
EDGE_DERIVED_FROM = "derived_from"   # Config → prior Config it was adapted from
EDGE_FOLLOWED_BY = "followed_by"     # chronological sequencing of Decisions/AgentActions

ALL_EDGE_TYPES = [EDGE_BELONGS_TO, EDGE_PRODUCED, EDGE_DERIVED_FROM, EDGE_FOLLOWED_BY]
