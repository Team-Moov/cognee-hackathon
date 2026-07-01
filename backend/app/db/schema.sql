-- Groundhog PostgreSQL schema
-- Requires: pgvector extension, pg_trgm extension (both bundled with most PG16 installs)

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- ── runs ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS runs (
    id              TEXT PRIMARY KEY,
    experiment      TEXT        NOT NULL DEFAULT 'unnamed',
    config          JSONB       NOT NULL DEFAULT '{}',
    config_hash     TEXT        NOT NULL DEFAULT '',
    config_summary  TEXT        NOT NULL DEFAULT '',
    metrics         JSONB       NOT NULL DEFAULT '{}',
    rationale       TEXT        NOT NULL DEFAULT '',
    git_commit      TEXT        NOT NULL DEFAULT 'unknown',
    gpu_hours       FLOAT,
    artifacts       JSONB       NOT NULL DEFAULT '[]',
    status          TEXT        NOT NULL DEFAULT 'completed',
    error_message   TEXT,
    -- pgvector: 768-dim Gemini text-embedding-004
    embedding       vector(768),
    -- tsvector: full-text search over rationale + config_summary
    ts              tsvector    GENERATED ALWAYS AS (
                        to_tsvector('english', coalesce(rationale,'') || ' ' || coalesce(config_summary,''))
                    ) STORED,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS runs_experiment_idx   ON runs (experiment);
CREATE INDEX IF NOT EXISTS runs_status_idx       ON runs (status);
CREATE INDEX IF NOT EXISTS runs_config_hash_idx  ON runs (config_hash);
CREATE INDEX IF NOT EXISTS runs_created_at_idx   ON runs (created_at DESC);
CREATE INDEX IF NOT EXISTS runs_ts_idx           ON runs USING GIN (ts);
-- HNSW cosine index for ANN vector search (build once, then reads are O(log n))
CREATE INDEX IF NOT EXISTS runs_embedding_hnsw   ON runs USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ── run lineage: directed adjacency list ──────────────────────────────────
-- Lets us do recursive CTE graph traversal for ancestor/descendant queries.
CREATE TABLE IF NOT EXISTS run_lineage (
    parent_run_id   TEXT        NOT NULL,
    child_run_id    TEXT        NOT NULL,
    edge_type       TEXT        NOT NULL DEFAULT 'derived_from',
    PRIMARY KEY (parent_run_id, child_run_id)
);
CREATE INDEX IF NOT EXISTS lineage_child_idx ON run_lineage (child_run_id);

-- ── lineage_graphs: stores the full nodes/edges JSON per run ──────────────
CREATE TABLE IF NOT EXISTS lineage_graphs (
    run_id          TEXT        PRIMARY KEY,
    nodes           JSONB       NOT NULL DEFAULT '[]',
    edges           JSONB       NOT NULL DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── agent_suggestions ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_suggestions (
    id              TEXT        PRIMARY KEY DEFAULT gen_random_uuid()::text,
    run_id          TEXT,
    experiment      TEXT,
    agent_type      TEXT        NOT NULL,
    payload         JSONB       NOT NULL DEFAULT '{}',
    severity        TEXT,
    dismissed       BOOLEAN     NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS suggestions_experiment_idx  ON agent_suggestions (experiment);
CREATE INDEX IF NOT EXISTS suggestions_dismissed_idx   ON agent_suggestions (dismissed);
CREATE INDEX IF NOT EXISTS suggestions_created_at_idx  ON agent_suggestions (created_at DESC);
