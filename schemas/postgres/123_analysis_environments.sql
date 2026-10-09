-- ============================================================
-- 123_analysis_environments.sql — Sandboxed analysis environments
-- ============================================================

CREATE TABLE IF NOT EXISTS analysis_environment (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL,
    env_type VARCHAR(50) NOT NULL
        CHECK (env_type IN ('metric_computation', 'crisp_scoring', 'agent_execution', 'sandbox')),
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'paused', 'destroyed')),
    config JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    destroyed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_analysis_env_location
    ON analysis_environment (location_id, status);
CREATE INDEX IF NOT EXISTS idx_analysis_env_type
    ON analysis_environment (env_type, status);

CREATE TABLE IF NOT EXISTS analysis_run (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    environment_id UUID NOT NULL REFERENCES analysis_environment(id) ON DELETE CASCADE,
    module_path VARCHAR(200) NOT NULL,
    input_params JSONB DEFAULT '{}',
    output_result JSONB,
    status VARCHAR(20) NOT NULL DEFAULT 'running'
        CHECK (status IN ('running', 'completed', 'failed', 'timeout', 'cancelled')),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    duration_ms INTEGER,
    resource_usage JSONB,
    error_message TEXT
);

CREATE INDEX IF NOT EXISTS idx_analysis_run_env
    ON analysis_run (environment_id, started_at DESC);
CREATE INDEX IF NOT EXISTS idx_analysis_run_status
    ON analysis_run (status, started_at);

CREATE TABLE IF NOT EXISTS analysis_sandbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    environment_id UUID NOT NULL REFERENCES analysis_environment(id) ON DELETE CASCADE,
    allowed_tables TEXT[] DEFAULT '{}',
    denied_tables TEXT[] DEFAULT '{}',
    max_query_rows INTEGER NOT NULL DEFAULT 10000,
    max_execution_seconds INTEGER NOT NULL DEFAULT 300,
    network_access BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
