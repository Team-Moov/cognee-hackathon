> **Historical note:** This file was written before the Cognee-only backend migration. The Postgres-specific recommendations below are no longer current; the active backend now routes through Cognee directly.

The genuinely Cognee-based code (memory.py's five wrapper functions, the DataPoint schema, the file watcher) is complete and well-written, but it's an orphaned module nobody calls. For a "Best Use of Cognee" track, this was the fire to put out first — at the time, a judge running the app would have seen no Cognee activity at all.

What's genuinely solid, either way
Frontend (frontend/src): real React app, 6 pages (Dashboard, Pre-flight Guard, Lineage Explorer, Query, Files, Agents), clean Tailwind UI, actually calls real endpoints — not a mockup.
Cognee wrapper layer (memory.py): remember_run, check_config, query_memory, improve_memory, forget_stale, promote_to_shared are real implementations against real cognee.add/cognify/search/prune calls, with hash-based exact match + GRAPH_COMPLETION semantic fallback.
Typed schema (schema.py): all 9 node types from the plan exist as proper DataPoint subclasses with index_fields, validators, edge constants.
Postgres backend: legitimately functional CRUD, recursive-CTE ancestor/descendant lineage queries, full-text search, all real (not mocked).
5 subagents (backend/app/agents/): all real Groq LLM calls with structured JSON prompts (config proposer, triage, dataset steward, literature, report), fanned out concurrently by a real orchestrator — but reading Postgres rows, not the graph.
MCP server: real SSE-transport MCP server with 4 correctly-schemed tools, but it's a thin proxy to the Postgres API, not Cognee.
What's hardcoded / stubbed / disconnected
ontology/ml_ontology.py — pure theater. It just print()s a hardcoded list of 8 ML terms and never calls any Cognee API. Section 4.4 of the plan ("highest-leverage feature for Best Use of Cognee") is 0% implemented.
forget_stale (memory.py:429-481) — for anything except full-dataset deletion, it just logs "would forget X" and increments a placeholder counter; no actual node-level pruning happens.
W&B bridge (connectors/wandb_bridge.py) — pulls real W&B data but writes to staging/wb_staging.json, which nothing ever reads. Same for the Jupyter magic (connectors/jupyter_magic.py) writing to staging/notebook_notes.json. Both connectors from the plan's Tier 1 are dead ends.
pgvector/HNSW semantic search — explicitly disabled in schema.sql and query.py:34 ("disabled until embedding column is added"); the "local deterministic embedding" in utils.py:95-114 (hash-based pseudo-embedding) is computed but never actually used for retrieval in the query path.
promote_to_shared and private/shared dataset split exist in memory.py but have no UI, no endpoint hooked to the live backend, and no caller.
Test files (test.py, test_day1.py, test_experiment.py) — worth verifying they still pass; they predate the Postgres pivot and likely test the Cognee path only.
Given you're ~2 days from the July 5 deadline and judged on Track 1 (Best Use of Cognee Open Source)
The core risk is that the polished, demoable half of the project doesn't touch Cognee at all, while the Cognee half is real but invisible. I'd recommend picking one of two paths rather than trying to do everything:

Rewire the Postgres backend's three highest-visibility endpoints to call memory.py instead of asyncpg — /check-config, /query, /remember — keeping Postgres only for things Cognee doesn't need (agent_suggestions, UI-only lineage cache). This is the smallest change that makes the demo genuinely Cognee-backed.
Actually wire the ontology into Cognee (a real cognee.add() of the ontology text + a query showing "AdamW extends Adam" reasoning) — this is a few hours of work and currently the single highest-leverage missing piece per your own plan.  


I pulled the actual Cognee source (GitHub `topoteretes/cognee`, PyPI latest = **1.2.2**) rather than relying on assumptions in your code, and it changes the picture significantly. Your `requirements.txt` pins are loose (`cognee` unpinned at root, `cognee>=0.1.17` in backend), so whatever gets installed today is almost certainly a modern 1.x build — which ships a **much higher-level, purpose-built API that already does most of what your plan describes**, sitting on top of the low-level primitives `memory.py` currently hand-rolls.

## The two API layers in cognee

**Layer 1 — primitives** (what `memory.py` uses today): `cognee.add()`, `cognee.cognify()`, `cognee.search(query_type=SearchType...)`, `cognee.prune`. Your code manually re-implements config-hashing, exact/similarity matching, and "forget" logic on top of these.

**Layer 2 — the actual memory API** (`cognee/api/v1/{remember,recall,improve,forget}`): four top-level async functions literally named `remember`/`recall`/`improve`/`forget` — this is not your plan's metaphor for `add+cognify+search+prune`, it's Cognee's own real SDK surface, purpose-built to be that. Using it directly (instead of reimplementing it) is the single biggest "Best Use of Cognee" win available to you:

```python
import cognee

# remember() = add() + cognify() + improve(), in one call
result = await cognee.remember(document_text, dataset_name="main_dataset", node_set=["exp_resnet_sweep"])

# recall() = auto-routing search with an actual classifier picking SearchType for you
hits = await cognee.recall("Have we tried AdamW at lr=2e-5?", datasets=["main_dataset"], query_type=SearchType.GRAPH_COMPLETION)

# improve() = graph enrichment (triplet embeddings, indexing) — NOT the same as re-running cognify()
await cognee.improve(dataset="main_dataset")

# forget() = one unified deletion primitive with real granularity
await cognee.forget(dataset="main_dataset", data_id=some_uuid, memory_only=True)  # keep raw file, wipe graph+vectors
await cognee.forget(dataset="main_dataset")                                       # wipe whole dataset
await cognee.forget(everything=True)                                             # nuke everything the user owns
```

Compare to what you have: `improve_memory()` in [memory.py:400-422](memory.py:400) just calls `cognee.cognify()` again — that's not enrichment, it's re-running ingestion. And `forget_stale()` ([memory.py:429-481](memory.py:429)) only does full-dataset prune; anything partial is a logged no-op with a fake counter. The real `forget()` gives you exact per-item, memory-only, or full-dataset deletion natively.

## Features that map directly onto gaps I flagged earlier

**1. Ontology grounding (currently 0% real — [ontology/ml_ontology.py](ontology/ml_ontology.py) just prints a list)**
Cognee has genuine ontology support: `cognify(ontology_file_path="ml_ontology.owl")` — it consumes a real OWL file and grounds entity extraction against it during ingestion. To actually claim this feature you need to: author an OWL file (Optimizer ⊃ {Adam, AdamW, SGD}, Architecture ⊃ {CNN, Transformer, ResNet}, with an `AdamW subClassOf Adam` style relation), then pass `ontology_file_path=` into your `cognify()` call in `remember_run()`. This is maybe 2-3 hours of work and directly satisfies Section 4.4 for real.

**2. Private/shared memory + promote ([memory.py:488-550](memory.py:488), currently unwired)**
Cognee's `session_id` parameter on `remember()`/`recall()` is essentially this feature, already built: pass `session_id="researcher_alice_scratch"` for cheap, fast, private exploratory writes; they auto-bridge into the permanent graph in the background via `improve()` when `self_improvement=True`. An explicit "promote" action becomes: write to session during exploration, then call `cognee.remember(final_data, dataset_name="main_dataset")` (no session_id) when the researcher decides to keep it. Far less code than a custom private/shared dataset split.

**3. Experiment/ResearchThread scoping**
Use `node_set=["experiment_resnet_sweep", "thread_lr_search"]` on `add`/`remember`, and `node_name=[...]` on `recall` to scope queries to one experiment or thread. This replaces any need for separate Cognee datasets per experiment — it's the built-in tagging/filtering mechanism.

**4. Lineage Explorer / provenance**
Cognee ships `get_memory_provenance_graph()` / `visualize_memory_provenance()` as real built-in functions. Worth checking whether these can replace (or at least back) your hand-rolled Postgres recursive-CTE lineage instead of maintaining a parallel adjacency table.

**5. `@observe` pipeline tracing (Section 4.5)**
Cognee already has `enable_tracing()` / `get_last_trace()` / `get_all_traces()` at the top level — built-in observability, no custom decorator needed.

## What this means for your two-backend problem

Given what I found earlier — the live app runs on Postgres with zero cognee calls, while `memory.py` is a correct-but-orphaned Cognee wrapper — my recommendation is now sharper: **don't just rewire the Postgres endpoints to call the old `memory.py`; rewrite `memory.py` itself to call `cognee.remember/recall/improve/forget` directly.** It's less code than what's there now, and it's a much stronger "Best Use of Cognee" story than manually reimplementing hash-matching and Jaccard-similarity on top of `add()`/`search()`.

Want me to draft the rewritten `memory.py` against this real API (remember/recall/improve/forget + node_set scoping + ontology file), so you can drop it in and rewire the three hot endpoints?

Sources:
- [topoteretes/cognee (GitHub)](https://github.com/topoteretes/cognee)
- [cognee/skill.md](https://github.com/topoteretes/cognee/blob/main/cognee/skill.md)
- [cognee/api/v1/remember/remember.py](https://github.com/topoteretes/cognee/blob/main/cognee/api/v1/remember/remember.py)
- [cognee/api/v1/recall/recall.py](https://github.com/topoteretes/cognee/blob/main/cognee/api/v1/recall/recall.py)
- [cognee/api/v1/improve/improve.py](https://github.com/topoteretes/cognee/blob/main/cognee/api/v1/improve/improve.py)
- [cognee/api/v1/forget/forget.py](https://github.com/topoteretes/cognee/blob/main/cognee/api/v1/forget/forget.py)
- [cognee/api/v1/cognify/cognify.py](https://github.com/topoteretes/cognee/blob/main/cognee/api/v1/cognify/cognify.py)
- [PyPI: cognee](https://pypi.org/project/cognee/) 


Short answer: **use the native functions for the actual memory mechanics, but keep a thin domain wrapper around them** — don't call `cognee.remember()`/`recall()`/`improve()`/`forget()` raw from your routes, and don't reimplement their internals either. Here's the dividing line.

## Use natively (don't reimplement)

- `improve()` — call it as-is after N runs. Don't re-call `cognify()` and call it "improve" like [memory.py:410](memory.py:410) does now — that's a different operation.
- `forget()` — call it as-is with `data_id` / `dataset` / `memory_only` / `everything`. Don't hand-roll partial-delete placeholders like [memory.py:429-481](memory.py:429).
- `recall()`'s auto-routing — let `auto_route=True` pick the `SearchType` for most queries (NL query bar, "catch me up") instead of hardcoding `GRAPH_COMPLETION` everywhere. It's a real classifier, not a stub.

## Provision/wrap (domain logic cognee has no concept of)

This is where you still need a `groundhog_memory.py`-style adapter, for four reasons specific to your use case:

**1. Config-hash exact match — Pre-flight Guard's core feature.**
`recall()` is semantic/graph search; it has no "give me the row where config_hash == X" primitive. Your current approach ([memory.py:266-285](memory.py:266)) hopes the hash string literally appears in the GRAPH_COMPLETION output text — fragile. Better: use `node_set=[f"confighash:{config_hash}"]` when you `remember()` a run, then for the exact-match check call `recall(query_text=..., node_name=[f"confighash:{config_hash}"], query_type=SearchType.CHUNKS)`. That's a real graph-node tag lookup, not string-matching luck — still "native" in the sense of using `node_set`/`node_name`, but the hashing scheme and tag convention is yours to design.

**2. Document assembly.** Your run dicts (config_params, result_metrics, rationale, dataset info) need to become either (a) one well-structured text blob for `remember()`, or (b) `DataPoint` objects (`Config`, `Result`, `Dataset`, etc. from your [schema.py](schema.py)) passed via `add_data_points()`. This translation is 100% your domain code — cognee can't know your run schema.

**3. Ontology wiring.** `ontology_file_path` isn't in `remember()`'s kwarg router (`_COGNIFY_ONLY` doesn't include it), so for ontology-grounded ingestion you call `cognee.add()` + `cognee.cognify(ontology_file_path="ml_ontology.owl")` directly rather than through `remember()`. That's a deliberate exception to "always use remember()."

**4. Response shaping.** Your FastAPI contract (`RememberResponse`, `CheckConfigResponse`, etc., locked in [main.py](main.py:144-284)) needs specific fields (`config_hash`, `similarity_score`, `already_tried`). `RememberResult`/`recall()`'s return types don't match 1:1, so something has to translate.

## What to actually change

Keep `memory.py`'s six function names and signatures (they're already the right shape for your API/MCP layers) but rewrite the **bodies**:

- `remember_run()` → build the doc/DataPoints, then call native `cognee.remember(doc, dataset_name=..., node_set=[f"experiment:{exp}", f"confighash:{hash}"])` instead of manual `add()`+`cognify()`.
- `check_config()` → tag-based lookup via `node_name=[f"confighash:{hash}"]` first (exact), fall back to `recall(auto_route=True)` for similarity.
- `improve_memory()` → thin passthrough to `cognee.improve(dataset=...)`.
- `forget_stale()` → thin passthrough to `cognee.forget(dataset=..., data_id=..., memory_only=...)`, translating your `criteria` dict into real params instead of logging placeholders.
- `promote_to_shared()` → becomes: session-scoped `remember(..., session_id=alice_scratch)` during exploration, then `remember(final_doc, dataset_name="main_dataset")` (no session_id) to promote — using cognee's session mechanism instead of hand-rolled dataset copying.

Want me to write this rewritten `memory.py` now?