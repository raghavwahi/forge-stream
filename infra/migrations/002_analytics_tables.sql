-- Analytics: usage events and daily aggregated stats

CREATE TABLE usage_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id     UUID REFERENCES users(id) ON DELETE SET NULL,
    event_type  VARCHAR(100) NOT NULL,
    provider    VARCHAR(50),
    model       VARCHAR(100),
    tokens_used INTEGER,
    latency_ms  INTEGER,
    metadata    JSONB NOT NULL DEFAULT '{}',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_usage_events_user_id    ON usage_events(user_id);
CREATE INDEX idx_usage_events_event_type ON usage_events(event_type);
CREATE INDEX idx_usage_events_created_at ON usage_events(created_at);

CREATE TABLE daily_usage_stats (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    date            DATE NOT NULL,
    total_events    INTEGER NOT NULL DEFAULT 0,
    total_tokens    INTEGER NOT NULL DEFAULT 0,
    events_by_type  JSONB NOT NULL DEFAULT '{}',
    UNIQUE(user_id, date)
);

CREATE INDEX idx_daily_usage_stats_user_date ON daily_usage_stats(user_id, date);
