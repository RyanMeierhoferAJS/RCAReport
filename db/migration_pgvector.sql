-- PIA — pgvector semantic search migration
-- Run this in your Supabase SQL editor AFTER the main schema

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add embedding columns to core tables
ALTER TABLE tasks         ADD COLUMN IF NOT EXISTS embedding vector(1536);
ALTER TABLE decisions     ADD COLUMN IF NOT EXISTS embedding vector(1536);
ALTER TABLE career_events ADD COLUMN IF NOT EXISTS embedding vector(1536);
ALTER TABLE notes         ADD COLUMN IF NOT EXISTS embedding vector(1536);

-- HNSW indexes for fast cosine similarity search
CREATE INDEX IF NOT EXISTS tasks_embedding_idx         ON tasks         USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS decisions_embedding_idx     ON decisions     USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS career_events_embedding_idx ON career_events USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS notes_embedding_idx         ON notes         USING hnsw (embedding vector_cosine_ops);

-- ── Semantic search functions ─────────────────────────────────────────────────

CREATE OR REPLACE FUNCTION semantic_search_tasks(
    query_embedding vector(1536),
    similarity_threshold float DEFAULT 0.45,
    match_count int DEFAULT 10
)
RETURNS TABLE(
    id uuid, title text, description text, priority text,
    status text, due_date date, project text, owner text, similarity float
)
LANGUAGE sql STABLE AS $$
    SELECT t.id, t.title, t.description, t.priority,
           t.status, t.due_date, t.project, t.owner,
           1 - (t.embedding <=> query_embedding) AS similarity
    FROM tasks t
    WHERE t.embedding IS NOT NULL
      AND 1 - (t.embedding <=> query_embedding) > similarity_threshold
    ORDER BY t.embedding <=> query_embedding
    LIMIT match_count;
$$;

CREATE OR REPLACE FUNCTION semantic_search_decisions(
    query_embedding vector(1536),
    similarity_threshold float DEFAULT 0.45,
    match_count int DEFAULT 10
)
RETURNS TABLE(
    id uuid, title text, description text, reason text,
    alternatives text[], project text, decided_at timestamptz, similarity float
)
LANGUAGE sql STABLE AS $$
    SELECT d.id, d.title, d.description, d.reason,
           d.alternatives, d.project, d.decided_at,
           1 - (d.embedding <=> query_embedding) AS similarity
    FROM decisions d
    WHERE d.embedding IS NOT NULL
      AND 1 - (d.embedding <=> query_embedding) > similarity_threshold
    ORDER BY d.embedding <=> query_embedding
    LIMIT match_count;
$$;

CREATE OR REPLACE FUNCTION semantic_search_career(
    query_embedding vector(1536),
    similarity_threshold float DEFAULT 0.45,
    match_count int DEFAULT 10
)
RETURNS TABLE(
    id uuid, type text, title text, description text,
    value_pounds numeric, project text, event_date date, similarity float
)
LANGUAGE sql STABLE AS $$
    SELECT c.id, c.type, c.title, c.description,
           c.value_pounds, c.project, c.event_date,
           1 - (c.embedding <=> query_embedding) AS similarity
    FROM career_events c
    WHERE c.embedding IS NOT NULL
      AND 1 - (c.embedding <=> query_embedding) > similarity_threshold
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
$$;

CREATE OR REPLACE FUNCTION semantic_search_notes(
    query_embedding vector(1536),
    similarity_threshold float DEFAULT 0.45,
    match_count int DEFAULT 10
)
RETURNS TABLE(
    id uuid, content text, tags text[], entities text[],
    project text, created_at timestamptz, similarity float
)
LANGUAGE sql STABLE AS $$
    SELECT n.id, n.content, n.tags, n.entities,
           n.project, n.created_at,
           1 - (n.embedding <=> query_embedding) AS similarity
    FROM notes n
    WHERE n.embedding IS NOT NULL
      AND 1 - (n.embedding <=> query_embedding) > similarity_threshold
    ORDER BY n.embedding <=> query_embedding
    LIMIT match_count;
$$;
