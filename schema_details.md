# Groundhog Graph Schema Details

This document outlines the 9 core `DataPoint` node types that make up the Groundhog memory graph. Each node type is designed with a deliberate separation between **structural** fields (used for exact lookups, foreign keys, and metrics) and **embeddable** fields (indexed by the LLM for semantic, fuzzy recall).

> **Update:** every run is now written into the graph as these **typed nodes with real edges** (via `cognee.tasks.storage.add_data_points`), not just a text blob. The relationship fields listed under "Edge Relationships" below become actual graph edges. This runs on local embeddings (no LLM/key needed), so the typed schema is enforced even if the semantic/LLM ingestion step is unavailable. See `memory._write_typed_nodes`.

---

## 1. Experiment
The top-level container grouping all runs under one overarching research goal.

*   **`name`** *(str)*: Name of the experiment (structural).
*   **`description`** *(str)*: **[Embeddable]** Captures the core research intent and motivation.
*   **`created_at`** *(datetime)*: Timestamp of creation (structural).
*   **`owner`** *(str)*: Name of the researcher or team (structural).

## 2. ResearchThread
A directional line of related runs pursuing one specific hypothesis within an experiment.

*   **`name`** *(str)*: Thread identifier (structural).
*   **`hypothesis_summary`** *(str)*: **[Embeddable]** The natural-language explanation of what is being tested.
*   **`status`** *(str)*: State of the thread (`active`, `abandoned`, `promoted`) (structural).
*   **`experiment_id`** *(str, optional)*: Foreign key linking to the parent Experiment (structural).

## 3. Config
A specific hyperparameter configuration for a single training run.

*   **`parameters`** *(dict)*: Raw dictionary of hyperparameters (e.g., model name, optimizer, lr). Stored structurally, NOT embedded, as raw JSON pollutes semantic space.
*   **`summary_text`** *(str)*: **[Embeddable]** A short, programmatic natural-language description of the config (e.g., "Config: model=ResNet50, optimizer=Adam, lr=0.001"). Crucial for semantic recall.
*   **`config_hash`** *(str)*: A deterministic SHA-256 hash of the normalized parameters. This is the primary key for the **Pre-flight Guard** exact-match duplicate detection.
*   **`research_thread_id`** *(str, optional)*: Foreign key linking to the parent thread (structural).

## 4. Dataset
A versioned dataset used in runs, tracking provenance and quality notes.

*   **`name`** *(str)*: Dataset identifier (structural).
*   **`version`** *(str)*: Version tag, defaults to "v1" (structural).
*   **`preprocessing_notes`** *(str)*: **[Embeddable]** Notes on how the data was cleaned or augmented.
*   **`split_rationale`** *(str)*: **[Embeddable]** Why a specific train/val/test split was chosen.
*   **`quality_issues`** *(str)*: **[Embeddable]** Known problems, biases, or caveats with the dataset.
*   **`parent_dataset_id`** *(str, optional)*: Foreign key linking to a parent dataset for transformation chains (structural).

## 5. Result
The outcome of a training run, pairing hard metrics with a narrative summary.

*   **`metrics`** *(dict)*: Raw dictionary of metrics (e.g., validation loss, accuracy). Structural only.
*   **`gpu_hours`** *(float, optional)*: Compute cost (structural).
*   **`wall_clock_seconds`** *(float, optional)*: Real-world time elapsed (structural).
*   **`config_id`** *(str, optional)*: Foreign key linking to the Config (structural).
*   **`dataset_id`** *(str, optional)*: Foreign key linking to the Dataset (structural).
*   **`status`** *(str)*: `completed`, `aborted`, or `failed`.
*   **`summary_text`** *(str)*: **[Embeddable]** A generated narrative combining the status, key metrics, and any researcher rationale. This allows users to search for negative results ("find runs where the loss exploded").
*   **`promoted`** *(bool)*: Flag indicating if the result was promoted to the shared team dataset (structural).

## 6. Artifact
A file produced by a run, such as a model checkpoint, plot, or evaluation report.

*   **`file_path`** *(str)*: Absolute path to the file on disk (structural).
*   **`artifact_type`** *(str)*: Classification (`checkpoint`, `plot`, `log`, `eval_report`, `other`).
*   **`result_id`** *(str, optional)*: Foreign key linking to the run Result (structural).
*   **`description`** *(str)*: **[Embeddable]** Human or auto-generated description of the artifact.
*   **`exists_on_disk`** *(bool)*: Boolean updated by the orphan detection system to flag broken references (structural).

## 7. Hypothesis
An idea motivating a run or research direction.

*   **`statement`** *(str)*: **[Embeddable]** The core claim being tested (e.g., "Replacing ReLU with GeLU will improve convergence").
*   **`research_thread_id`** *(str, optional)*: Foreign key linking to the active thread (structural).
*   **`status`** *(str)*: `open`, `supported`, or `refuted`.

## 8. Decision
A deliberate choice made by a researcher or an autonomous agent during the project.

*   **`description`** *(str)*: **[Embeddable]** What decision was made.
*   **`rationale`** *(str)*: **[Embeddable]** *WHY* it was decided. This is arguably the highest-value field in the schema for preventing repeated mistakes.
*   **`made_by`** *(str)*: Human or agent name (structural).
*   **`timestamp`** *(datetime)*: When the decision was made (structural).
*   **`research_thread_id`** *(str, optional)*: Foreign key (structural).

## 9. AgentAction
Records an action taken by a human or agent (decided, abandoned, promoted, noted).

*   **`action_type`** *(str)*: `decided`, `abandoned`, `promoted`, or `noted`.
*   **`parameters`** *(dict)*: Structured dictionary of action parameters.
*   **`rationale`** *(str)*: **[Embeddable]** Why this action was taken.
*   **`timestamp`** *(datetime)*: When it occurred.
*   **`source`** *(str)*: Human or agent-name.

---

## Edge Relationships

These nodes are connected in the graph via the following edges. Each is a
`SkipValidation[Any]` **relationship field** on the DataPoint that, when
populated with another DataPoint instance and written via `add_data_points`,
becomes a real typed edge (the field name is the edge label):

| Edge (field) | On | Points to | Meaning |
|---|---|---|---|
| `belongs_to` | Config, Result, ResearchThread | ResearchThread / Experiment | run/config/thread grouping |
| `produced_by` | Result → Config, Artifact → Result | Config / Result | Result was produced by a Config; Artifact by a Result |
| `used_dataset` | Result | Dataset | which dataset the run used |
| `derived_from` | Config, Dataset | prior Config / parent Dataset | lineage — adapted from a prior config / transformation chain |

The subgraph written per run is:

```
Experiment ◄─belongs_to─ ResearchThread ◄─belongs_to─ Config
Result ─produced_by► Config    Result ─used_dataset► Dataset    Result ─belongs_to► ResearchThread
Artifact ─produced_by► Result   (one per output file scanned from output_dir)
```

`Decision` / `AgentAction` sequencing (`followed_by`) and the config
`derived_from` chain power the Lineage Explorer, which also reads a deterministic
config chain from `groundhog_index.json`.

---

## What each run now captures

Beyond config + metrics, a `remember()` call records the **full picture**, fed
end-to-end through the SDK → backend → Cognee server:

- **Dataset used** → `Dataset` node (name, version, preprocessing, split rationale, quality issues)
- **Output files** → `Artifact` nodes (checkpoint / plot / log / eval_report), scanned from `output_dir`, with orphan detection via `/orphans`
- **Cost** → `gpu_hours` + `wall_clock_seconds` on `Result`
- **Hypothesis** → `Hypothesis` node / run field
- **Lineage** → `derived_from` edge to the prior config

## Config hashing (Pre-flight Guard)

`config_hash` is a SHA-256 of the **canonicalised** config: noise keys (`seed`,
`output_dir`, `gpu_id`, `run_name`, `num_workers`, timestamps, …) are stripped
and key aliases normalised (`lr` → `learning_rate`, `model_name` → `model`, …)
before hashing. A project may declare `significant_keys` to hash on an explicit
allowlist. This makes exact-match Pre-flight detection robust to the messy
configs researchers actually run. See `memory.canonical_config`.
