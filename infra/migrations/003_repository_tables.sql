-- Migration: 003_repository_tables.sql
-- Creates tables for GitHub repository connections and issue generation runs.

CREATE TABLE github_repositories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    github_repo_id BIGINT NOT NULL,
    owner VARCHAR(255) NOT NULL,
    name VARCHAR(255) NOT NULL,
    full_name VARCHAR(512) NOT NULL,  -- owner/name
    description TEXT,
    is_private BOOLEAN NOT NULL DEFAULT false,
    default_branch VARCHAR(255) NOT NULL DEFAULT 'main',
    html_url TEXT NOT NULL,
    is_connected BOOLEAN NOT NULL DEFAULT true,
    connected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(user_id, github_repo_id)
);

CREATE INDEX idx_github_repos_user_id ON github_repositories(user_id);
CREATE INDEX idx_github_repos_full_name ON github_repositories(full_name);
CREATE INDEX idx_github_repos_connected ON github_repositories(user_id, is_connected);

CREATE TABLE repository_issue_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repository_id UUID NOT NULL REFERENCES github_repositories(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    prompt TEXT NOT NULL,
    model VARCHAR(100),
    status VARCHAR(50) NOT NULL DEFAULT 'pending',  -- pending, running, completed, failed
    total_issues INTEGER,
    created_issues INTEGER DEFAULT 0,
    error_message TEXT,
    work_item_snapshot JSONB,  -- snapshot of generated work items
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_issue_runs_repo_id ON repository_issue_runs(repository_id);
CREATE INDEX idx_issue_runs_user_id ON repository_issue_runs(user_id);
CREATE INDEX idx_issue_runs_status ON repository_issue_runs(status);

-- auto-update trigger for github_repositories.updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_github_repositories_updated_at
    BEFORE UPDATE ON github_repositories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
