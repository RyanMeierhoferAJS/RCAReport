-- Migration: Ideas + PDP Actions
-- Run in Supabase SQL editor

-- ── Ideas ──────────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS ideas (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    description     TEXT,
    category        TEXT DEFAULT 'general',   -- product, process, research, personal, general
    status          TEXT DEFAULT 'raw',       -- raw, refined, parked, shipped
    project         TEXT,
    source_capture_id UUID REFERENCES captures(id),
    embedding       vector(1536),
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ideas_status_idx ON ideas (status);
CREATE INDEX IF NOT EXISTS ideas_embedding_idx ON ideas
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

-- ── PDP Actions ────────────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS pdp_actions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title           TEXT NOT NULL,
    description     TEXT,
    category        TEXT DEFAULT 'general',  -- leadership, technical, commercial, personal
    objective       TEXT,                    -- formal PDP wording
    evidence        TEXT[] DEFAULT '{}',     -- accumulated evidence items
    status          TEXT DEFAULT 'not_started', -- not_started, in_progress, on_track, at_risk, exceeded, complete
    target_date     DATE,
    review_date     DATE,
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS pdp_status_idx ON pdp_actions (status);

-- ── Semantic search RPC for ideas ──────────────────────────────────────────

CREATE OR REPLACE FUNCTION semantic_search_ideas(
    query_embedding vector(1536),
    similarity_threshold float DEFAULT 0.45,
    match_count int DEFAULT 10
)
RETURNS TABLE (
    id UUID, title TEXT, description TEXT, category TEXT, status TEXT, project TEXT,
    similarity float
)
LANGUAGE sql STABLE
AS $$
    SELECT id, title, description, category, status, project,
           1 - (embedding <=> query_embedding) AS similarity
    FROM   ideas
    WHERE  1 - (embedding <=> query_embedding) > similarity_threshold
    ORDER  BY embedding <=> query_embedding
    LIMIT  match_count;
$$;
