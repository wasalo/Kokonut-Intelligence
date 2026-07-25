-- 351_platform_upgrade.sql — platform release and upgrade history

CREATE TABLE IF NOT EXISTS platform_upgrade (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_version VARCHAR(50) NOT NULL,
    target_git_sha VARCHAR(40) NOT NULL,
    previous_version VARCHAR(50),
    previous_git_sha VARCHAR(40),
    migration_before VARCHAR(512),
    migration_after VARCHAR(512),
    backup_id VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'started'
        CHECK (status IN ('started', 'succeeded', 'failed', 'rolled_back')),
    operator VARCHAR(255) NOT NULL,
    failure_reason TEXT,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS one_active_platform_upgrade
    ON platform_upgrade ((status))
    WHERE status = 'started';

CREATE INDEX IF NOT EXISTS idx_platform_upgrade_started_at
    ON platform_upgrade (started_at DESC);
