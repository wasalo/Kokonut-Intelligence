-- 136_advisory_engine.sql
-- Advisory / Recommendation Engine for precision agriculture decisions
-- Precision Agriculture Phase 2: Advisory Engine

BEGIN;

-- ============================================================
-- ADVISORY RULES
-- ============================================================

CREATE TABLE IF NOT EXISTS advisory_rule (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    rule_type VARCHAR(50) NOT NULL CHECK (rule_type IN (
        'threshold', 'composite', 'schedule', 'anomaly_response', 'forecast_based'
    )),
    domain VARCHAR(100) NOT NULL CHECK (domain IN (
        'irrigation', 'fertilization', 'pest_management', 'harvest',
        'soil_health', 'planting', 'crop_protection', 'general'
    )),
    priority INTEGER DEFAULT 50 CHECK (priority BETWEEN 0 AND 100),
    conditions JSONB NOT NULL DEFAULT '{}',
    recommendation_template TEXT NOT NULL,
    severity VARCHAR(20) DEFAULT 'info' CHECK (severity IN ('info', 'warning', 'critical')),
    auto_generate BOOLEAN DEFAULT FALSE,
    requires_approval BOOLEAN DEFAULT TRUE,
    cooldown_hours INTEGER DEFAULT 24,
    max_per_day INTEGER DEFAULT 5,
    status VARCHAR(50) DEFAULT 'active' CHECK (status IN ('active', 'disabled', 'archived')),
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_advisory_rule_domain ON advisory_rule(domain, status);
CREATE INDEX IF NOT EXISTS idx_advisory_rule_active ON advisory_rule(status) WHERE status = 'active';

-- ============================================================
-- ADVISORY RECOMMENDATIONS
-- ============================================================

CREATE TABLE IF NOT EXISTS advisory_recommendation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    rule_id UUID REFERENCES advisory_rule(id) ON DELETE SET NULL,
    domain VARCHAR(100) NOT NULL,
    title VARCHAR(255) NOT NULL,
    summary TEXT NOT NULL,
    details JSONB DEFAULT '{}',
    urgency VARCHAR(20) NOT NULL DEFAULT 'this_week' CHECK (urgency IN (
        'immediate', 'within_24h', 'within_48h', 'this_week', 'advisory'
    )),
    severity VARCHAR(20) NOT NULL DEFAULT 'info' CHECK (severity IN ('info', 'warning', 'critical')),
    action_type VARCHAR(100),
    action_config JSONB DEFAULT '{}',
    estimated_cost_usd NUMERIC(10,2),
    estimated_impact TEXT,
    prescription_map_id UUID REFERENCES prescription_map(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN (
        'pending', 'accepted', 'dismissed', 'executed', 'expired'
    )),
    executed_at TIMESTAMPTZ,
    executed_by UUID,
    dismissed_reason TEXT,
    feedback TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_advisory_rec_location ON advisory_recommendation(location_id, status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_advisory_rec_domain ON advisory_recommendation(domain, status);
CREATE INDEX IF NOT EXISTS idx_advisory_rec_urgency ON advisory_recommendation(urgency, severity DESC, created_at DESC);

-- ============================================================
-- ADVISORY LOG (audit trail)
-- ============================================================

CREATE TABLE IF NOT EXISTS advisory_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recommendation_id UUID NOT NULL REFERENCES advisory_recommendation(id) ON DELETE CASCADE,
    action VARCHAR(50) NOT NULL,
    old_status VARCHAR(50),
    new_status VARCHAR(50),
    performed_by UUID,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_advisory_log_rec ON advisory_log(recommendation_id, created_at);

-- ============================================================
-- VIEWS
-- ============================================================

CREATE OR REPLACE VIEW v_pending_recommendations AS
SELECT
    ar.id,
    ar.location_id,
    ar.domain,
    ar.title,
    ar.summary,
    ar.urgency,
    ar.severity,
    ar.action_type,
    ar.action_config,
    ar.estimated_cost_usd,
    ar.estimated_impact,
    ar.created_at,
    ar.expires_at,
    l.name AS location_name,
    ar.rule_id,
    ar2.name AS rule_name
FROM advisory_recommendation ar
JOIN location l ON l.id = ar.location_id
LEFT JOIN advisory_rule ar2 ON ar2.id = ar.rule_id
WHERE ar.status = 'pending'
  AND (ar.expires_at IS NULL OR ar.expires_at > NOW())
ORDER BY
    CASE ar.severity WHEN 'critical' THEN 1 WHEN 'warning' THEN 2 ELSE 3 END,
    CASE ar.urgency WHEN 'immediate' THEN 1 WHEN 'within_24h' THEN 2
         WHEN 'within_48h' THEN 3 WHEN 'this_week' THEN 4 ELSE 5 END,
    ar.created_at DESC;

CREATE OR REPLACE VIEW v_advisory_stats AS
SELECT
    ar.location_id,
    l.name AS location_name,
    ar.domain,
    COUNT(*) FILTER (WHERE ar.status = 'pending') AS pending_count,
    COUNT(*) FILTER (WHERE ar.status = 'accepted') AS accepted_count,
    COUNT(*) FILTER (WHERE ar.status = 'executed') AS executed_count,
    COUNT(*) FILTER (WHERE ar.status = 'dismissed') AS dismissed_count,
    COUNT(*) FILTER (WHERE ar.severity = 'critical') AS critical_count,
    COUNT(*) FILTER (WHERE ar.severity = 'warning') AS warning_count,
    SUM(COALESCE(ar.estimated_cost_usd, 0)) FILTER (WHERE ar.status IN ('accepted', 'executed')) AS total_estimated_cost,
    MAX(ar.created_at) AS latest_recommendation_at
FROM advisory_recommendation ar
JOIN location l ON l.id = ar.location_id
GROUP BY ar.location_id, l.name, ar.domain;

COMMIT;
