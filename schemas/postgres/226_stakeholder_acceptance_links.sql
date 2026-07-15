-- ============================================================
-- 226_stakeholder_acceptance_links.sql
-- ============================================================

ALTER TABLE nature_stewardship_obligation ADD COLUMN IF NOT EXISTS evidence_maturity INTEGER REFERENCES evidence_maturity_level(level);

CREATE OR REPLACE VIEW v_public_ecological_stewardship AS
SELECT o.id AS obligation_id, o.proxy_party_id, p.display_name AS proxy_name,
       o.title, o.obligation_type, o.metric_key, o.target_value, o.target_unit,
       o.target_date, o.status, o.evidence,
       'Proxy interests are documented ecological obligations; no consent or vote is claimed.' AS limitation
FROM nature_stewardship_obligation o
JOIN party p ON p.id = o.proxy_party_id
WHERE o.status IN ('approved', 'in_progress', 'met')
  AND p.privacy_level = 'public'
  AND COALESCE(o.evidence_maturity, 0) >= 4;

CREATE TABLE IF NOT EXISTS technology_alternative_stakeholder_outcome (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alternative_id UUID NOT NULL REFERENCES technology_alternative(id) ON DELETE CASCADE,
    party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    outcome_id UUID REFERENCES value_stream_stakeholder_outcome(id) ON DELETE SET NULL,
    expected_benefit TEXT,
    expected_harm_reduction TEXT,
    access_effects JSONB NOT NULL DEFAULT '[]'::jsonb,
    equity_effects JSONB NOT NULL DEFAULT '[]'::jsonb,
    estimated_value NUMERIC,
    estimated_value_unit VARCHAR(50),
    uncertainty NUMERIC(5,4) CHECK (uncertainty BETWEEN 0 AND 1),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    reviewed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'reviewed', 'approved', 'rejected')),
    CHECK (party_id IS NOT NULL OR outcome_id IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS stakeholder_bottleneck_priority (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    stage_id UUID NOT NULL REFERENCES value_stream_stage(id) ON DELETE CASCADE,
    party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    outcome_id UUID REFERENCES value_stream_stakeholder_outcome(id) ON DELETE SET NULL,
    process_key VARCHAR(100),
    priority VARCHAR(20) NOT NULL DEFAULT 'medium' CHECK (priority IN ('low', 'medium', 'high', 'critical')),
    harm_if_unresolved TEXT,
    value_at_risk NUMERIC,
    value_unit VARCHAR(50),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    reviewed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'reviewed', 'active', 'resolved')),
    CHECK (party_id IS NOT NULL OR outcome_id IS NOT NULL)
);

CREATE OR REPLACE VIEW v_party_financing_eligibility_inputs AS
SELECT p.id AS party_id, p.display_name,
       COUNT(e.id) FILTER (WHERE e.status = 'active' AND e.dimension IN ('identity', 'credential')) AS identity_evidence_count,
       COUNT(e.id) FILTER (WHERE e.status = 'active' AND e.dimension = 'payment' AND e.direction = 'supporting') AS payment_support_count,
       COUNT(e.id) FILTER (WHERE e.status = 'active' AND e.direction = 'contradicting') AS contradicting_evidence_count,
       COUNT(r.id) FILTER (WHERE r.status IN ('open', 'monitoring')) AS open_risk_count,
       MAX(e.uncertainty) AS maximum_uncertainty,
       TRUE AS human_review_required,
       'Advisory inputs only; no automatic financing, insurance, or exclusion decision is made.' AS limitation
FROM party p
LEFT JOIN party_trust_evidence e ON e.subject_party_id = p.id
LEFT JOIN relationship_risk_indicator r ON r.subject_party_id = p.id
GROUP BY p.id, p.display_name;

CREATE OR REPLACE VIEW v_party_relationship_recommendations AS
SELECT p.id AS party_id, p.display_name,
       CASE
         WHEN COUNT(r.id) FILTER (WHERE r.status IN ('open', 'monitoring') AND r.severity IN ('high', 'critical')) > 0 THEN 'human_review'
         WHEN COUNT(e.id) FILTER (WHERE e.status = 'active' AND e.direction = 'supporting') > 0 THEN 'consider_with_review'
         ELSE 'insufficient_evidence'
       END AS recommendation,
       COUNT(e.id) FILTER (WHERE e.status = 'active') AS evidence_count,
       MAX(e.uncertainty) AS maximum_uncertainty,
       TRUE AS human_review_required,
       'Recommendation is explainable and advisory; inspect evidence timeline and appeals before action.' AS limitation
FROM party p
LEFT JOIN party_trust_evidence e ON e.subject_party_id = p.id
LEFT JOIN relationship_risk_indicator r ON r.subject_party_id = p.id
GROUP BY p.id, p.display_name;

COMMENT ON VIEW v_party_financing_eligibility_inputs IS 'Explainable financing and insurance inputs, not an eligibility decision';
COMMENT ON VIEW v_party_relationship_recommendations IS 'Human-reviewed relationship recommendations, not an opaque reputation score';
