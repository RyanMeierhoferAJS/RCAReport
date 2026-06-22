-- PIA — Personal Intelligence Agent
-- Supabase PostgreSQL Schema
-- Run this in your Supabase SQL editor

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Raw captures: everything that comes in from Telegram
CREATE TABLE IF NOT EXISTS captures (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         TEXT NOT NULL DEFAULT 'ryan',
    raw_text        TEXT NOT NULL,
    telegram_msg_id BIGINT,
    telegram_chat_id BIGINT,
    media_type      TEXT DEFAULT 'text',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Tasks
CREATE TABLE IF NOT EXISTS tasks (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id          TEXT NOT NULL DEFAULT 'ryan',
    title            TEXT NOT NULL,
    description      TEXT,
    owner            TEXT DEFAULT 'Ryan',
    priority         TEXT CHECK (priority IN ('high', 'medium', 'low')) DEFAULT 'medium',
    status           TEXT CHECK (status IN ('open', 'in_progress', 'waiting', 'complete')) DEFAULT 'open',
    due_date         DATE,
    project          TEXT,
    source_capture_id UUID REFERENCES captures(id),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW(),
    completed_at     TIMESTAMPTZ,
    search_vector    tsvector GENERATED ALWAYS AS (
        to_tsvector('english',
            coalesce(title, '') || ' ' ||
            coalesce(description, '') || ' ' ||
            coalesce(project, '') || ' ' ||
            coalesce(owner, '')
        )
    ) STORED
);

CREATE INDEX IF NOT EXISTS tasks_search_idx ON tasks USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS tasks_status_idx  ON tasks(status);
CREATE INDEX IF NOT EXISTS tasks_user_idx    ON tasks(user_id);

-- Decisions
CREATE TABLE IF NOT EXISTS decisions (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id          TEXT NOT NULL DEFAULT 'ryan',
    title            TEXT NOT NULL,
    description      TEXT,
    reason           TEXT,
    alternatives     TEXT[],
    outcome          TEXT,
    project          TEXT,
    source_capture_id UUID REFERENCES captures(id),
    decided_at       TIMESTAMPTZ DEFAULT NOW(),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    search_vector    tsvector GENERATED ALWAYS AS (
        to_tsvector('english',
            coalesce(title, '') || ' ' ||
            coalesce(description, '') || ' ' ||
            coalesce(reason, '') || ' ' ||
            coalesce(project, '')
        )
    ) STORED
);

CREATE INDEX IF NOT EXISTS decisions_search_idx ON decisions USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS decisions_user_idx   ON decisions(user_id);

-- Career Journal
CREATE TABLE IF NOT EXISTS career_events (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id          TEXT NOT NULL DEFAULT 'ryan',
    type             TEXT CHECK (type IN (
                         'achievement', 'cost_avoidance', 'reliability_improvement',
                         'qualification', 'training_delivered', 'presentation',
                         'project_win', 'other'
                     )) NOT NULL DEFAULT 'achievement',
    title            TEXT NOT NULL,
    description      TEXT,
    value_pounds     NUMERIC,
    project          TEXT,
    source_capture_id UUID REFERENCES captures(id),
    event_date       DATE DEFAULT CURRENT_DATE,
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    search_vector    tsvector GENERATED ALWAYS AS (
        to_tsvector('english',
            coalesce(title, '') || ' ' ||
            coalesce(description, '') || ' ' ||
            coalesce(project, '')
        )
    ) STORED
);

CREATE INDEX IF NOT EXISTS career_search_idx ON career_events USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS career_date_idx   ON career_events(event_date);
CREATE INDEX IF NOT EXISTS career_user_idx   ON career_events(user_id);

-- Notes (general knowledge, thoughts, ideas)
CREATE TABLE IF NOT EXISTS notes (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id          TEXT NOT NULL DEFAULT 'ryan',
    content          TEXT NOT NULL,
    tags             TEXT[],
    entities         TEXT[],
    project          TEXT,
    source_capture_id UUID REFERENCES captures(id),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    search_vector    tsvector GENERATED ALWAYS AS (
        to_tsvector('english',
            coalesce(content, '') || ' ' ||
            coalesce(project, '') || ' ' ||
            coalesce(array_to_string(tags, ' '), '') || ' ' ||
            coalesce(array_to_string(entities, ' '), '')
        )
    ) STORED
);

CREATE INDEX IF NOT EXISTS notes_search_idx ON notes USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS notes_user_idx   ON notes(user_id);

-- Projects
CREATE TABLE IF NOT EXISTS projects (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id        TEXT NOT NULL DEFAULT 'ryan',
    name           TEXT NOT NULL,
    description    TEXT,
    status         TEXT CHECK (status IN ('active', 'stalled', 'complete', 'on_hold')) DEFAULT 'active',
    next_milestone TEXT,
    last_activity  TIMESTAMPTZ DEFAULT NOW(),
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    updated_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, name)
);

INSERT INTO projects (name, description, status) VALUES
    ('Home Build',          'New home construction project',               'active'),
    ('ERIP',                'Energy Recovery and Intelligence Platform',   'active'),
    ('Vibration Platform',  'Online vibration monitoring system',          'active'),
    ('RCA Automation',      'Automated Root Cause Analysis generation',    'active'),
    ('Ultrasound Bot',      'Ultrasound inspection automation',            'active'),
    ('Track Car',           'Track car project',                           'active'),
    ('PIA',                 'Personal Intelligence Agent',                 'active')
ON CONFLICT (user_id, name) DO NOTHING;

-- Opportunities
CREATE TABLE IF NOT EXISTS opportunities (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id          TEXT NOT NULL DEFAULT 'ryan',
    title            TEXT NOT NULL,
    description      TEXT,
    type             TEXT CHECK (type IN ('business', 'app', 'passive_income', 'product', 'other')) DEFAULT 'other',
    value_estimate   NUMERIC,
    effort           TEXT CHECK (effort IN ('low', 'medium', 'high')),
    status           TEXT CHECK (status IN ('idea', 'evaluating', 'active', 'parked', 'killed')) DEFAULT 'idea',
    next_action      TEXT,
    source_capture_id UUID REFERENCES captures(id),
    created_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Weekly reports (stored for history)
CREATE TABLE IF NOT EXISTS weekly_reports (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     TEXT NOT NULL DEFAULT 'ryan',
    week_ending DATE NOT NULL,
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- Daily digests (stored for history)
CREATE TABLE IF NOT EXISTS daily_digests (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id     TEXT NOT NULL DEFAULT 'ryan',
    digest_date DATE NOT NULL DEFAULT CURRENT_DATE,
    content     TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
