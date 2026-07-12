-- ============================================================
-- 117_task_scheduler.sql — Database-driven task scheduler
-- ============================================================

CREATE TABLE IF NOT EXISTS scheduled_task (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    module_path VARCHAR(300) NOT NULL,
    cron_expression VARCHAR(50) NOT NULL,
    priority VARCHAR(20) NOT NULL DEFAULT 'normal'
        CHECK (priority IN ('critical', 'high', 'normal', 'low')),
    timeout_seconds INTEGER NOT NULL DEFAULT 3600,
    max_retries INTEGER NOT NULL DEFAULT 3,
    retry_delay_seconds INTEGER NOT NULL DEFAULT 60,
    depends_on UUID[] DEFAULT '{}',
    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    last_status VARCHAR(20),
    last_duration_ms INTEGER,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_scheduled_task_next_run
    ON scheduled_task (next_run_at, priority)
    WHERE is_enabled = TRUE;

CREATE TABLE IF NOT EXISTS task_run (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id UUID NOT NULL REFERENCES scheduled_task(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed', 'timeout', 'cancelled')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    worker_id VARCHAR(100),
    stdout TEXT,
    stderr TEXT
);

CREATE INDEX IF NOT EXISTS idx_task_run_task_id
    ON task_run (task_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_task_run_status
    ON task_run (status, started_at);

CREATE TABLE IF NOT EXISTS task_resource (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resource_name VARCHAR(100) NOT NULL UNIQUE,
    resource_type VARCHAR(50) NOT NULL,
    max_concurrent INTEGER NOT NULL DEFAULT 1,
    current_running INTEGER NOT NULL DEFAULT 0,
    max_wait_seconds INTEGER NOT NULL DEFAULT 300,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Seed default resources
INSERT INTO task_resource (resource_name, resource_type, max_concurrent) VALUES
    ('db_connection', 'database', 5),
    ('clickhouse_connection', 'database', 3),
    ('network_api', 'network', 10),
    ('cpu_intensive', 'compute', 2)
ON CONFLICT (resource_name) DO NOTHING;
