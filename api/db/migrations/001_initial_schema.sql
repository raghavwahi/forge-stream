-- ForgeStream: Initial PostgreSQL schema for Supabase
-- Migration 001 – users, provider_configs, prompts, work_items, analytics

-- Enable pgcrypto for gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- ──────────────────────────────────────────────
-- ENUM types
-- ──────────────────────────────────────────────
CREATE TYPE user_role        AS ENUM ('admin', 'user');
CREATE TYPE provider_type    AS ENUM ('openai', 'claude', 'gemini', 'mistral', 'custom');
CREATE TYPE work_item_type   AS ENUM ('epic', 'story', 'bug');
CREATE TYPE work_item_status AS ENUM ('proposed', 'accepted', 'rejected');
CREATE TYPE analytics_event  AS ENUM (
    'generation',
    'regeneration',
    'acceptance',
    'rejection',
    'prompt_enhancement'
);

-- ──────────────────────────────────────────────
-- 1. users
-- ──────────────────────────────────────────────
CREATE TABLE users (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email                 TEXT UNIQUE NOT NULL,
    display_name          TEXT,
    role                  user_role NOT NULL DEFAULT 'user',
    github_token_enc      BYTEA,               -- encrypted GitHub PAT
                                              -- Encrypt with AES-256-GCM via pgcrypto or
                                              -- application-layer encryption before storage.
                                              -- Key management: use a dedicated secret manager
                                              -- (e.g. Vault, AWS KMS). Rotate keys by re-encrypting.
    password_hash         TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ──────────────────────────────────────────────
-- 2. provider_configs
-- ──────────────────────────────────────────────
CREATE TABLE provider_configs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    provider      provider_type NOT NULL,
    api_key_enc   BYTEA,                        -- encrypted API key (same scheme as github_token_enc)
    model_name    TEXT,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (user_id, provider)
);

-- ──────────────────────────────────────────────
-- 3. prompts
-- ──────────────────────────────────────────────
CREATE TABLE prompts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    original_input  TEXT NOT NULL,
    enhanced_input  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_prompts_user ON prompts (user_id);

-- ──────────────────────────────────────────────
-- 4. work_items
-- ──────────────────────────────────────────────
CREATE TABLE work_items (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prompt_id        UUID NOT NULL REFERENCES prompts (id) ON DELETE CASCADE,
    user_id          UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    item_type        work_item_type   NOT NULL,
    title            TEXT NOT NULL,
    description      TEXT,
    status           work_item_status NOT NULL DEFAULT 'proposed',
    github_issue_id  BIGINT,
    github_issue_url TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_work_items_user   ON work_items (user_id);
CREATE INDEX idx_work_items_prompt ON work_items (prompt_id);
CREATE INDEX idx_work_items_status ON work_items (status);

-- ──────────────────────────────────────────────
-- 5. analytics
-- ──────────────────────────────────────────────
CREATE TABLE analytics (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    event_type    analytics_event NOT NULL,
    -- ON DELETE SET NULL: analytics rows are preserved for historical
    -- reporting even when the referenced prompt or work_item is removed.
    prompt_id     UUID REFERENCES prompts (id)    ON DELETE SET NULL,
    work_item_id  UUID REFERENCES work_items (id) ON DELETE SET NULL,
    metadata      JSONB DEFAULT '{}',
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_analytics_user  ON analytics (user_id);
CREATE INDEX idx_analytics_event ON analytics (event_type);
CREATE INDEX idx_analytics_time  ON analytics (created_at);

-- ──────────────────────────────────────────────
-- Auto-update updated_at trigger
-- ──────────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_provider_configs_updated_at
    BEFORE UPDATE ON provider_configs
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_work_items_updated_at
    BEFORE UPDATE ON work_items
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();
