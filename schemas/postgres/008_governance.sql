-- ============================================================
-- 008_governance.sql — Audit, permissions, schema governance
-- ============================================================

-- Audit log
CREATE TABLE IF NOT EXISTS audit_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    user_id UUID,
    user_email VARCHAR(255),
    action VARCHAR(50) NOT NULL, -- create, update, delete, login, export, approve, reject, publish
    collection VARCHAR(100) NOT NULL,
    record_id UUID,
    old_data JSONB,
    new_data JSONB,
    ip_address INET,
    user_agent TEXT,
    metadata JSONB DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_collection ON audit_log(collection);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_record ON audit_log(collection, record_id);

-- Data ingestion log
CREATE TABLE IF NOT EXISTS ingestion_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_system VARCHAR(100) NOT NULL, -- baserow, csv, api, rpc, subgraph, manual
    source_table VARCHAR(100),
    source_id VARCHAR(255),
    target_table VARCHAR(100) NOT NULL,
    target_id UUID,
    operation VARCHAR(50) NOT NULL, -- insert, update, upsert, delete
    payload_hash VARCHAR(64),
    status VARCHAR(50) DEFAULT 'success', -- success, failed, partial
    error_message TEXT,
    rows_affected INTEGER,
    processing_time_ms INTEGER,
    schema_version VARCHAR(20),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ingestion_source ON ingestion_log(source_system);
CREATE INDEX IF NOT EXISTS idx_ingestion_target ON ingestion_log(target_table);
CREATE INDEX IF NOT EXISTS idx_ingestion_status ON ingestion_log(status);
CREATE INDEX IF NOT EXISTS idx_ingestion_date ON ingestion_log(created_at);

-- Schema migration history
CREATE TABLE IF NOT EXISTS schema_migration (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    version VARCHAR(20) NOT NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    sql_up TEXT NOT NULL,
    sql_down TEXT,
    checksum VARCHAR(64) NOT NULL,
    applied_at TIMESTAMPTZ DEFAULT NOW(),
    applied_by VARCHAR(100),
    execution_time_ms INTEGER,
    status VARCHAR(50) DEFAULT 'applied' -- applied, failed, rolled_back
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_migration_version ON schema_migration(version);

-- User roles (application-level, supplements Directus RBAC)
CREATE TABLE IF NOT EXISTS app_role (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    permissions JSONB DEFAULT '{}',
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- API keys for external access
CREATE TABLE IF NOT EXISTS api_key (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    key_hash VARCHAR(255) NOT NULL,
    key_prefix VARCHAR(10) NOT NULL,
    role_id UUID REFERENCES app_role(id),
    scopes TEXT[],
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID
);

-- Webhook registrations
CREATE TABLE IF NOT EXISTS webhook (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    url TEXT NOT NULL,
    secret VARCHAR(255),
    events TEXT[] NOT NULL, -- items.create, items.update, etc.
    collections TEXT[],
    is_active BOOLEAN DEFAULT TRUE,
    last_triggered_at TIMESTAMPTZ,
    failure_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Scheduled jobs
CREATE TABLE IF NOT EXISTS scheduled_job (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    job_type VARCHAR(100) NOT NULL, -- noi_calculation, forecast, snapshot, sync, cleanup
    cron_expression VARCHAR(100),
    parameters JSONB DEFAULT '{}',
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    status VARCHAR(50) DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Data export log
CREATE TABLE IF NOT EXISTS export_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID,
    export_type VARCHAR(50) NOT NULL, -- csv, json, parquet, sql, excel
    target_table VARCHAR(100),
    filters JSONB,
    row_count INTEGER,
    file_size_bytes BIGINT,
    file_url TEXT,
    status VARCHAR(50) DEFAULT 'pending', -- pending, generating, completed, failed
    created_at TIMESTAMPTZ DEFAULT NOW()
);
