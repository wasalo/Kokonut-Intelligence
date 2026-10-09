-- Migration 200: Partner Lifecycle
-- Phase 7D of BMC Sprint
--
-- Tables:
--   partner_lifecycle    – Partner lifecycle stages
--   partner_evaluation   – Partner evaluations and assessments
--   partner_scorecard    – Partner performance scorecards

BEGIN;

-- ============================================================
-- 1. partner_lifecycle
-- ============================================================
CREATE TABLE IF NOT EXISTS partner_lifecycle (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    partner_id UUID NOT NULL REFERENCES partner(id) ON DELETE CASCADE,
    location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    stage VARCHAR(50) NOT NULL DEFAULT 'prospect'
        CHECK (stage IN ('prospect', 'negotiation', 'pilot', 'active', 'review',
                         'renewal', 'suspended', 'exited')),
    stage_entered_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    stage_notes TEXT,
    assigned_to UUID,
    next_review_date DATE,
    contract_start_date DATE,
    contract_end_date DATE,
    partnership_type VARCHAR(100),
    strategic_importance VARCHAR(20) DEFAULT 'medium'
        CHECK (strategic_importance IN ('low', 'medium', 'high', 'critical')),
    metadata JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'active'
        CHECK (status IN ('active', 'inactive', 'archived')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID
);

CREATE INDEX IF NOT EXISTS idx_pl_partner ON partner_lifecycle(partner_id);
CREATE INDEX IF NOT EXISTS idx_pl_location ON partner_lifecycle(location_id);
CREATE INDEX IF NOT EXISTS idx_pl_stage ON partner_lifecycle(stage);
CREATE INDEX IF NOT EXISTS idx_pl_status ON partner_lifecycle(status);

-- ============================================================
-- 2. partner_evaluation
-- ============================================================
CREATE TABLE IF NOT EXISTS partner_evaluation (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lifecycle_id UUID NOT NULL REFERENCES partner_lifecycle(id) ON DELETE CASCADE,
    partner_id UUID NOT NULL REFERENCES partner(id) ON DELETE CASCADE,
    evaluation_type VARCHAR(50) NOT NULL
        CHECK (evaluation_type IN ('initial', 'quarterly', 'annual', 'ad_hoc', 'exit')),
    technical_score NUMERIC(5,2) DEFAULT 0
        CHECK (technical_score >= 0 AND technical_score <= 100),
    financial_score NUMERIC(5,2) DEFAULT 0
        CHECK (financial_score >= 0 AND financial_score <= 100),
    reliability_score NUMERIC(5,2) DEFAULT 0
        CHECK (reliability_score >= 0 AND reliability_score <= 100),
    compliance_score NUMERIC(5,2) DEFAULT 0
        CHECK (compliance_score >= 0 AND compliance_score <= 100),
    overall_score NUMERIC(5,2) DEFAULT 0
        CHECK (overall_score >= 0 AND overall_score <= 100),
    strengths TEXT[],
    weaknesses TEXT[],
    recommendations TEXT,
    evaluated_by UUID,
    evaluation_date DATE DEFAULT CURRENT_DATE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pe_lifecycle ON partner_evaluation(lifecycle_id);
CREATE INDEX IF NOT EXISTS idx_pe_partner ON partner_evaluation(partner_id);
CREATE INDEX IF NOT EXISTS idx_pe_type ON partner_evaluation(evaluation_type);

-- ============================================================
-- 3. partner_scorecard
-- ============================================================
CREATE TABLE IF NOT EXISTS partner_scorecard (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lifecycle_id UUID NOT NULL REFERENCES partner_lifecycle(id) ON DELETE CASCADE,
    partner_id UUID NOT NULL REFERENCES partner(id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    deliveries_on_time_pct NUMERIC(5,2) DEFAULT 0
        CHECK (deliveries_on_time_pct >= 0 AND deliveries_on_time_pct <= 100),
    quality_score NUMERIC(5,2) DEFAULT 0
        CHECK (quality_score >= 0 AND quality_score <= 100),
    responsiveness_score NUMERIC(5,2) DEFAULT 0
        CHECK (responsiveness_score >= 0 AND responsiveness_score <= 100),
    cost_competitiveness NUMERIC(5,2) DEFAULT 0
        CHECK (cost_competitiveness >= 0 AND cost_competitiveness <= 100),
    innovation_score NUMERIC(5,2) DEFAULT 0
        CHECK (innovation_score >= 0 AND innovation_score <= 100),
    overall_score NUMERIC(5,2) DEFAULT 0
        CHECK (overall_score >= 0 AND overall_score <= 100),
    incidents INTEGER DEFAULT 0,
    notes TEXT,
    graded_by UUID,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(lifecycle_id, period_start, period_end)
);

CREATE INDEX IF NOT EXISTS idx_ps_lifecycle ON partner_scorecard(lifecycle_id);
CREATE INDEX IF NOT EXISTS idx_ps_partner ON partner_scorecard(partner_id);
CREATE INDEX IF NOT EXISTS idx_ps_period ON partner_scorecard(period_start, period_end);

-- ============================================================
-- Views
-- ============================================================

-- Partner lifecycle summary
CREATE OR REPLACE VIEW v_partner_lifecycle_summary AS
SELECT
    pl.stage,
    COUNT(*) AS partner_count,
    AVG(pl.strategic_importance::NUMERIC) AS avg_importance,
    COUNT(*) FILTER (WHERE pl.next_review_date <= CURRENT_DATE) AS overdue_reviews
FROM partner_lifecycle pl
WHERE pl.status = 'active'
GROUP BY pl.stage;

-- Partner scorecard summary
CREATE OR REPLACE VIEW v_partner_scorecard_summary AS
SELECT
    ps.partner_id,
    p.name AS partner_name,
    ps.period_start,
    ps.period_end,
    ps.overall_score,
    ps.deliveries_on_time_pct,
    ps.quality_score,
    ps.responsiveness_score,
    RANK() OVER (PARTITION BY ps.period_end ORDER BY ps.overall_score DESC) AS rank
FROM partner_scorecard ps
JOIN partner p ON p.id = ps.partner_id
ORDER BY ps.period_end DESC, ps.overall_score DESC;

COMMIT;
