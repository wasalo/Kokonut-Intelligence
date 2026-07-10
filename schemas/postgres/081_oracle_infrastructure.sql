-- ============================================================
-- 081_oracle_infrastructure.sql — Oracle Infrastructure
-- ============================================================
-- Multi-source oracle aggregation, price feeds, actuator
-- commands, and climate data pipeline extensions.
-- ============================================================

-- 1. Extend price_observation with oracle consensus fields
ALTER TABLE price_observation ADD COLUMN IF NOT EXISTS confidence NUMERIC(5,4);
ALTER TABLE price_observation ADD COLUMN IF NOT EXISTS deviation_pct NUMERIC(8,4);
ALTER TABLE price_observation ADD COLUMN IF NOT EXISTS source_count INTEGER DEFAULT 1;
ALTER TABLE price_observation ADD COLUMN IF NOT EXISTS aggregation_method VARCHAR(50) DEFAULT 'single';
ALTER TABLE price_observation ADD COLUMN IF NOT EXISTS source_metadata JSONB DEFAULT '{}';

ALTER TABLE price_observation DROP CONSTRAINT IF EXISTS chk_price_obs_aggregation;
ALTER TABLE price_observation ADD CONSTRAINT chk_price_obs_aggregation CHECK (
    aggregation_method IS NULL OR aggregation_method IN (
        'single', 'median_consensus', 'weighted_average', 'on_chain_attested'
    )
);

-- 2. Extend alert_rule with actuation fields
ALTER TABLE alert_rule ADD COLUMN IF NOT EXISTS actuator_enabled BOOLEAN DEFAULT FALSE;
ALTER TABLE alert_rule ADD COLUMN IF NOT EXISTS actuator_type VARCHAR(50);
ALTER TABLE alert_rule ADD COLUMN IF NOT EXISTS actuator_command VARCHAR(100);
ALTER TABLE alert_rule ADD COLUMN IF NOT EXISTS actuator_topic VARCHAR(255);
ALTER TABLE alert_rule ADD COLUMN IF NOT EXISTS human_approval_required BOOLEAN DEFAULT TRUE;

ALTER TABLE alert_rule DROP CONSTRAINT IF EXISTS chk_alert_rule_actuator_type;
ALTER TABLE alert_rule ADD CONSTRAINT chk_alert_rule_actuator_type CHECK (
    actuator_type IS NULL OR actuator_type IN (
        'irrigation', 'pest_control', 'fertilization', 'notification', 'custom'
    )
);

-- 3. Extend sensor_alert with actuation tracking
ALTER TABLE sensor_alert ADD COLUMN IF NOT EXISTS actuation_sent BOOLEAN DEFAULT FALSE;
ALTER TABLE sensor_alert ADD COLUMN IF NOT EXISTS actuation_response JSONB;
ALTER TABLE sensor_alert ADD COLUMN IF NOT EXISTS actuation_status VARCHAR(50);

ALTER TABLE sensor_alert DROP CONSTRAINT IF EXISTS chk_sensor_alert_actuation;
ALTER TABLE sensor_alert ADD CONSTRAINT chk_sensor_alert_actuation CHECK (
    actuation_status IS NULL OR actuation_status IN (
        'pending', 'sent', 'acknowledged', 'executed', 'failed', 'requires_approval'
    )
);

-- 4. Oracle price feed attestation log
CREATE TABLE IF NOT EXISTS oracle_price_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    commodity VARCHAR(100) NOT NULL,
    currency VARCHAR(10) DEFAULT 'USD',
    price NUMERIC(15,6) NOT NULL,
    price_timestamp TIMESTAMPTZ NOT NULL,
    source VARCHAR(100) NOT NULL,
    source_count INTEGER DEFAULT 1,
    confidence NUMERIC(5,4),
    deviation_pct NUMERIC(8,4),
    aggregation_method VARCHAR(50) DEFAULT 'single',
    attestation_uid VARCHAR(66),
    attested_at TIMESTAMPTZ,
    chain VARCHAR(50) DEFAULT 'celo',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_oracle_price_commodity ON oracle_price_log(commodity);
CREATE INDEX IF NOT EXISTS idx_oracle_price_timestamp ON oracle_price_log(price_timestamp);
CREATE INDEX IF NOT EXISTS idx_oracle_price_source ON oracle_price_log(source);
CREATE INDEX IF NOT EXISTS idx_oracle_price_attestation ON oracle_price_log(attestation_uid);

-- 5. Actuation command log
CREATE TABLE IF NOT EXISTS actuation_log (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    sensor_alert_id UUID REFERENCES sensor_alert(id) ON DELETE SET NULL,
    actuator_type VARCHAR(50) NOT NULL,
    actuator_command VARCHAR(100) NOT NULL,
    actuator_topic VARCHAR(255),
    command_payload JSONB NOT NULL,
    trigger_source VARCHAR(100) NOT NULL,
    trigger_alert_severity VARCHAR(20),
    human_approval_required BOOLEAN DEFAULT TRUE,
    approved_by UUID,
    approved_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    response_received_at TIMESTAMPTZ,
    response_payload JSONB,
    status VARCHAR(50) DEFAULT 'pending',
    error_message TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_actuation_log_location ON actuation_log(location_id);
CREATE INDEX IF NOT EXISTS idx_actuation_log_alert ON actuation_log(sensor_alert_id);
CREATE INDEX IF NOT EXISTS idx_actuation_log_status ON actuation_log(status);
CREATE INDEX IF NOT EXISTS idx_actuation_log_type ON actuation_log(actuator_type);

ALTER TABLE actuation_log DROP CONSTRAINT IF EXISTS chk_actuation_log_status;
ALTER TABLE actuation_log ADD CONSTRAINT chk_actuation_log_status CHECK (
    status IN ('pending', 'approved', 'sent', 'acknowledged', 'executed', 'failed', 'cancelled')
);

ALTER TABLE actuation_log DROP CONSTRAINT IF EXISTS chk_actuation_log_type;
ALTER TABLE actuation_log ADD CONSTRAINT chk_actuation_log_type CHECK (
    actuator_type IN ('irrigation', 'pest_control', 'fertilization', 'notification', 'custom')
);
