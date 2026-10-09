-- Migration 199: Channel Orchestration + Customer Health
-- Phase 7C of BMC Sprint
--
-- Tables:
--   channel_config          – Channel configurations
--   channel_preference      – Per-segment channel preferences
--   channel_fallback_rule   – Multi-channel fallback chains
--   customer_interaction    – Touchpoint log
--   customer_health_score   – Automated engagement/health scoring

BEGIN;

-- ============================================================
-- 1. channel_config
-- ============================================================
CREATE TABLE IF NOT EXISTS channel_config (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE CASCADE,
    channel_name VARCHAR(100) NOT NULL,
    channel_type VARCHAR(50) NOT NULL
        CHECK (channel_type IN ('sms', 'whatsapp', 'mobile_app', 'email',
                                'voice_call', 'ussd', 'radio', 'community_screen',
                                'print', 'in_person', 'web_portal', 'api')),
    is_active BOOLEAN DEFAULT TRUE,
    config JSONB DEFAULT '{}',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(location_id, channel_name)
);

CREATE INDEX IF NOT EXISTS idx_cc_location ON channel_config(location_id);
CREATE INDEX IF NOT EXISTS idx_cc_type ON channel_config(channel_type);

-- ============================================================
-- 2. channel_preference
-- ============================================================
CREATE TABLE IF NOT EXISTS channel_preference (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE CASCADE,
    segment_type VARCHAR(50) NOT NULL
        CHECK (segment_type IN ('farmer', 'buyer', 'cooperative', 'community', 'all')),
    segment_id UUID,
    channel_type VARCHAR(50) NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    is_primary BOOLEAN DEFAULT FALSE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cp_location ON channel_preference(location_id);
CREATE INDEX IF NOT EXISTS idx_cp_segment ON channel_preference(segment_type, segment_id);
CREATE INDEX IF NOT EXISTS idx_cp_priority ON channel_preference(priority DESC);

-- ============================================================
-- 3. channel_fallback_rule
-- ============================================================
CREATE TABLE IF NOT EXISTS channel_fallback_rule (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID REFERENCES location(id) ON DELETE CASCADE,
    rule_name VARCHAR(255) NOT NULL,
    primary_channel VARCHAR(50) NOT NULL,
    fallback_channels JSONB NOT NULL DEFAULT '[]',
    trigger_condition VARCHAR(100) DEFAULT 'no_response'
        CHECK (trigger_condition IN ('no_response', 'delivery_failed', ' bounced', 'timeout', 'manual')),
    timeout_hours INTEGER DEFAULT 24,
    is_active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_cf_location ON channel_fallback_rule(location_id);
CREATE INDEX IF NOT EXISTS idx_cf_primary ON channel_fallback_rule(primary_channel);

-- ============================================================
-- 4. customer_interaction
-- ============================================================
CREATE TABLE IF NOT EXISTS customer_interaction (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    customer_type VARCHAR(50) NOT NULL
        CHECK (customer_type IN ('farmer', 'buyer', 'cooperative', 'community', 'partner')),
    customer_id UUID NOT NULL,
    interaction_type VARCHAR(100) NOT NULL
        CHECK (interaction_type IN ('message_sent', 'message_received', 'call_made',
                                    'call_received', 'meeting', 'order_placed',
                                    'order_delivered', 'feedback_given', 'training_attended',
                                    'support_ticket', 'visit', 'survey_completed', 'other')),
    channel_type VARCHAR(50),
    subject VARCHAR(255),
    content TEXT,
    sentiment VARCHAR(20) CHECK (sentiment IN ('positive', 'neutral', 'negative')),
    response_required BOOLEAN DEFAULT FALSE,
    response_by TIMESTAMPTZ,
    responded_at TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ci_location ON customer_interaction(location_id);
CREATE INDEX IF NOT EXISTS idx_ci_customer ON customer_interaction(customer_type, customer_id);
CREATE INDEX IF NOT EXISTS idx_ci_type ON customer_interaction(interaction_type);
CREATE INDEX IF NOT EXISTS idx_ci_created ON customer_interaction(created_at DESC);

-- ============================================================
-- 5. customer_health_score
-- ============================================================
CREATE TABLE IF NOT EXISTS customer_health_score (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    customer_type VARCHAR(50) NOT NULL
        CHECK (customer_type IN ('farmer', 'buyer', 'cooperative', 'community', 'partner')),
    customer_id UUID NOT NULL,
    health_score NUMERIC(5,2) DEFAULT 50
        CHECK (health_score >= 0 AND health_score <= 100),
    engagement_score NUMERIC(5,2) DEFAULT 0
        CHECK (engagement_score >= 0 AND engagement_score <= 100),
    satisfaction_score NUMERIC(5,2) DEFAULT 0
        CHECK (satisfaction_score >= 0 AND satisfaction_score <= 100),
    recency_score NUMERIC(5,2) DEFAULT 0
        CHECK (recency_score >= 0 AND recency_score <= 100),
    frequency_score NUMERIC(5,2) DEFAULT 0
        CHECK (frequency_score >= 0 AND frequency_score <= 100),
    breakdown JSONB DEFAULT '{}',
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(location_id, customer_type, customer_id)
);

CREATE INDEX IF NOT EXISTS idx_chs_location ON customer_health_score(location_id);
CREATE INDEX IF NOT EXISTS idx_chs_customer ON customer_health_score(customer_type, customer_id);
CREATE INDEX IF NOT EXISTS idx_chs_score ON customer_health_score(health_score DESC);

-- ============================================================
-- Views
-- ============================================================

-- Channel configuration summary
CREATE OR REPLACE VIEW v_channel_config_summary AS
SELECT
    cc.location_id,
    l.name AS location_name,
    COUNT(*) AS channel_count,
    COUNT(*) FILTER (WHERE cc.is_active) AS active_channels,
    ARRAY_AGG(DISTINCT cc.channel_type) AS channel_types
FROM channel_config cc
JOIN location l ON l.id = cc.location_id
WHERE cc.is_active = TRUE
GROUP BY cc.location_id, l.name;

-- Customer health summary per location
CREATE OR REPLACE VIEW v_customer_health_summary AS
SELECT
    chs.location_id,
    l.name AS location_name,
    chs.customer_type,
    COUNT(*) AS customer_count,
    AVG(chs.health_score) AS avg_health_score,
    COUNT(*) FILTER (WHERE chs.health_score >= 70) AS healthy_count,
    COUNT(*) FILTER (WHERE chs.health_score >= 40 AND chs.health_score < 70) AS at_risk_count,
    COUNT(*) FILTER (WHERE chs.health_score < 40) AS critical_count
FROM customer_health_score chs
JOIN location l ON l.id = chs.location_id
GROUP BY chs.location_id, l.name, chs.customer_type;

-- Interaction volume summary
CREATE OR REPLACE VIEW v_interaction_volume AS
SELECT
    ci.location_id,
    l.name AS location_name,
    ci.customer_type,
    DATE_TRUNC('month', ci.created_at) AS month,
    COUNT(*) AS interaction_count,
    COUNT(*) FILTER (WHERE ci.sentiment = 'positive') AS positive_count,
    COUNT(*) FILTER (WHERE ci.sentiment = 'negative') AS negative_count,
    COUNT(*) FILTER (WHERE ci.response_required AND ci.responded_at IS NOT NULL) AS responded_count,
    COUNT(*) FILTER (WHERE ci.response_required AND ci.responded_at IS NULL) AS pending_response_count
FROM customer_interaction ci
JOIN location l ON l.id = ci.location_id
GROUP BY ci.location_id, l.name, ci.customer_type, DATE_TRUNC('month', ci.created_at);

COMMIT;
