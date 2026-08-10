-- JobSignal AI operational Lakebase schema.
-- The job feed itself is a read-only synced table generated from the Spark Gold table.

CREATE SCHEMA IF NOT EXISTS jobsignal_app;

CREATE TABLE IF NOT EXISTS jobsignal_app.profiles (
    profile_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    display_name TEXT NOT NULL,
    headline TEXT,
    target_roles JSONB NOT NULL DEFAULT '[]'::jsonb,
    preferred_locations JSONB NOT NULL DEFAULT '[]'::jsonb,
    remote_only BOOLEAN NOT NULL DEFAULT TRUE,
    min_salary INTEGER,
    resume_text TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS jobsignal_app.skills (
    skill_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    profile_id BIGINT NOT NULL REFERENCES jobsignal_app.profiles(profile_id) ON DELETE CASCADE,
    skill_name TEXT NOT NULL,
    normalized_skill TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(profile_id, normalized_skill)
);

CREATE TABLE IF NOT EXISTS jobsignal_app.job_embeddings (
    embedding_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL CHECK (chunk_index >= 0),
    chunk_text TEXT NOT NULL,
    embedding VECTOR(384) NOT NULL,
    model_name TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(job_id, chunk_index, model_name)
);

CREATE INDEX IF NOT EXISTS job_embeddings_hnsw_idx
ON jobsignal_app.job_embeddings
USING hnsw (embedding vector_cosine_ops);

CREATE TABLE IF NOT EXISTS jobsignal_app.saved_jobs (
    saved_job_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    profile_id BIGINT NOT NULL REFERENCES jobsignal_app.profiles(profile_id) ON DELETE CASCADE,
    job_id TEXT NOT NULL,
    notes TEXT,
    saved_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(profile_id, job_id)
);

CREATE TABLE IF NOT EXISTS jobsignal_app.applications (
    application_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    profile_id BIGINT NOT NULL REFERENCES jobsignal_app.profiles(profile_id) ON DELETE CASCADE,
    job_id TEXT NOT NULL,
    company_snapshot TEXT,
    title_snapshot TEXT,
    stage TEXT NOT NULL DEFAULT 'saved'
        CHECK (stage IN ('saved','applied','interviewing','rejected','offer','withdrawn')),
    follow_up_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(profile_id, job_id)
);

CREATE TABLE IF NOT EXISTS jobsignal_app.interview_notes (
    note_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    application_id BIGINT NOT NULL REFERENCES jobsignal_app.applications(application_id) ON DELETE CASCADE,
    note_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS jobsignal_app.contacts (
    contact_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    profile_id BIGINT NOT NULL REFERENCES jobsignal_app.profiles(profile_id) ON DELETE CASCADE,
    job_id TEXT,
    name TEXT NOT NULL,
    company TEXT,
    role TEXT,
    contact_url TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS jobsignal_app.agent_action_log (
    action_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    profile_id BIGINT REFERENCES jobsignal_app.profiles(profile_id) ON DELETE SET NULL,
    tool_name TEXT NOT NULL,
    arguments JSONB NOT NULL DEFAULT '{}'::jsonb,
    result JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
