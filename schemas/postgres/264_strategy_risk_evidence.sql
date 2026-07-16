-- ============================================================
-- 264_strategy_risk_evidence.sql
-- CRISP and mitigation evidence for strategic investments.
-- ============================================================

ALTER TABLE strategy_investment_case
    ADD COLUMN IF NOT EXISTS location_id UUID REFERENCES location(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS crisp_assessment_id UUID REFERENCES crisp_risk_assessment(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS risk_mitigation_id UUID REFERENCES risk_mitigation_register(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS risk_as_of TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS risk_methodology_version VARCHAR(50),
    ADD COLUMN IF NOT EXISTS risk_confidence VARCHAR(30),
    ADD COLUMN IF NOT EXISTS risk_evidence_status VARCHAR(20) NOT NULL DEFAULT 'missing'
        CHECK (risk_evidence_status IN ('missing', 'provisional', 'verified', 'stale'));

CREATE INDEX IF NOT EXISTS idx_strategy_investment_risk
    ON strategy_investment_case(crisp_assessment_id, risk_mitigation_id, risk_evidence_status);

CREATE OR REPLACE VIEW v_strategy_investment_risk_evidence AS
SELECT sic.id AS investment_id,
       sic.strategy_plan_id,
       sic.location_id,
       sic.risk_score,
       sic.risk_evidence_status,
       sic.risk_as_of,
       sic.risk_methodology_version,
       cra.id AS crisp_assessment_id,
       cra.composite_score AS crisp_composite_score,
       cra.rating AS crisp_rating,
       cra.confidence_level AS crisp_confidence,
       cra.status AS crisp_status,
       rmr.id AS mitigation_id,
       rmr.status AS mitigation_status,
       rmr.residual_risk_level
FROM strategy_investment_case sic
LEFT JOIN crisp_risk_assessment cra ON cra.id = sic.crisp_assessment_id
LEFT JOIN risk_mitigation_register rmr ON rmr.id = sic.risk_mitigation_id;

COMMENT ON COLUMN strategy_investment_case.risk_score IS 'Computed risk snapshot; source evidence is stored in crisp_assessment_id and risk_mitigation_id';
