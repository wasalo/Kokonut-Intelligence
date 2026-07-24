-- Durable freshness alert state, history, and delivery attempts.
ALTER TABLE data_freshness_config
    ADD COLUMN IF NOT EXISTS alert_cooldown_minutes INTEGER NOT NULL DEFAULT 60,
    ADD COLUMN IF NOT EXISTS escalation_cooldown_minutes INTEGER NOT NULL DEFAULT 15;

ALTER TABLE data_freshness_config
    DROP CONSTRAINT IF EXISTS chk_freshness_alert_cooldowns;
ALTER TABLE data_freshness_config
    ADD CONSTRAINT chk_freshness_alert_cooldowns CHECK (
        alert_cooldown_minutes > 0 AND escalation_cooldown_minutes > 0
    );

CREATE TABLE IF NOT EXISTS data_freshness_alert_state (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source_system VARCHAR(100) NOT NULL,
    location_id UUID REFERENCES location(id) ON DELETE CASCADE,
    current_status VARCHAR(20) NOT NULL,
    last_event_type VARCHAR(20),
    last_event_status VARCHAR(20),
    last_event_at TIMESTAMPTZ,
    last_delivered_at TIMESTAMPTZ,
    alert_count INTEGER NOT NULL DEFAULT 0 CHECK (alert_count >= 0),
    escalation_count INTEGER NOT NULL DEFAULT 0 CHECK (escalation_count >= 0),
    recovery_count INTEGER NOT NULL DEFAULT 0 CHECK (recovery_count >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_system, location_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_freshness_alert_state_scope
    ON data_freshness_alert_state (source_system, COALESCE(location_id, '00000000-0000-0000-0000-000000000000'::uuid));
CREATE INDEX IF NOT EXISTS idx_freshness_alert_state_status
    ON data_freshness_alert_state (current_status);

CREATE TABLE IF NOT EXISTS data_freshness_alert_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    state_id UUID NOT NULL REFERENCES data_freshness_alert_state(id) ON DELETE CASCADE,
    check_id UUID REFERENCES data_freshness_check(id) ON DELETE SET NULL,
    source_system VARCHAR(100) NOT NULL,
    location_id UUID REFERENCES location(id) ON DELETE CASCADE,
    event_type VARCHAR(20) NOT NULL CHECK (event_type IN ('alert', 'escalation', 'recovery')),
    previous_status VARCHAR(20),
    status VARCHAR(20) NOT NULL,
    gap_minutes INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_freshness_alert_history_scope
    ON data_freshness_alert_history (source_system, location_id, created_at DESC);

CREATE TABLE IF NOT EXISTS data_freshness_alert_delivery_attempt (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    alert_id UUID NOT NULL REFERENCES data_freshness_alert_history(id) ON DELETE CASCADE,
    channel VARCHAR(50) NOT NULL,
    outcome VARCHAR(20) NOT NULL CHECK (outcome IN ('delivered', 'failed')),
    error_message TEXT,
    attempted_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_freshness_delivery_alert
    ON data_freshness_alert_delivery_attempt (alert_id, attempted_at DESC);
