-- ============================================================
-- 237_coordination_learning_accounting.sql
-- ============================================================
-- Links coordination to governed capability, process, technology,
-- training, insight-transfer, and stakeholder-outcome evidence.

CREATE TABLE IF NOT EXISTS coordination_learning_link (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alliance_id UUID NOT NULL REFERENCES coordination_alliance(id) ON DELETE CASCADE,
    link_type VARCHAR(30) NOT NULL CHECK (link_type IN (
        'capability_maturity', 'process_improvement', 'technology_alternative',
        'training', 'insight_transfer', 'stakeholder_outcome'
    )),
    capability_id UUID REFERENCES business_capability(id) ON DELETE SET NULL,
    process_improvement_id UUID REFERENCES process_improvement(id) ON DELETE SET NULL,
    technology_alternative_id UUID REFERENCES technology_alternative(id) ON DELETE SET NULL,
    training_session_id UUID REFERENCES training_session(id) ON DELETE SET NULL,
    insight_transfer_id UUID REFERENCES insight_transfer(id) ON DELETE SET NULL,
    stakeholder_outcome_id UUID REFERENCES stakeholder_outcome(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    baseline_value NUMERIC,
    current_value NUMERIC,
    target_value NUMERIC,
    unit VARCHAR(50),
    status VARCHAR(20) NOT NULL DEFAULT 'proposed'
        CHECK (status IN ('proposed', 'active', 'verified', 'retired')),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    observed_at TIMESTAMPTZ,
    created_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (baseline_value IS NULL OR current_value IS NULL OR unit IS NOT NULL),
    CHECK (num_nonnulls(capability_id, process_improvement_id, technology_alternative_id,
                        training_session_id, insight_transfer_id, stakeholder_outcome_id) = 1)
);

CREATE TABLE IF NOT EXISTS coordination_metric_observation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alliance_id UUID NOT NULL REFERENCES coordination_alliance(id) ON DELETE CASCADE,
    metric_key VARCHAR(60) NOT NULL CHECK (metric_key IN (
        'capability_gap_closed', 'knowledge_transfer_completion_rate',
        'reciprocal_contribution_ratio', 'stakeholder_outcome_improvement',
        'coordination_lead_time_days', 'unresolved_coordination_risk',
        'benefit_distribution_equity', 'dependency_concentration',
        'partner_substitution_resilience'
    )),
    value NUMERIC NOT NULL,
    numerator NUMERIC,
    denominator NUMERIC,
    unit VARCHAR(40) NOT NULL,
    as_of TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    methodology TEXT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'draft'
        CHECK (status IN ('draft', 'verified', 'rejected')),
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    observed_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    verified_by_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    verified_at TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status <> 'verified' OR verified_by_party_id IS NOT NULL),
    CHECK (status <> 'verified' OR verified_at IS NOT NULL),
    CHECK (denominator IS NULL OR denominator >= 0)
);

CREATE INDEX IF NOT EXISTS idx_coord_learning_alliance
    ON coordination_learning_link(alliance_id, link_type, status);
CREATE INDEX IF NOT EXISTS idx_coord_learning_capability
    ON coordination_learning_link(capability_id);
CREATE INDEX IF NOT EXISTS idx_coord_learning_outcome
    ON coordination_learning_link(stakeholder_outcome_id);
CREATE INDEX IF NOT EXISTS idx_coord_metric_alliance
    ON coordination_metric_observation(alliance_id, metric_key, as_of DESC);

CREATE OR REPLACE VIEW v_coordination_learning AS
SELECT cl.id,
       cl.alliance_id,
       ca.name AS alliance_name,
       cl.link_type,
       cl.title,
       cl.description,
       cl.baseline_value,
       cl.current_value,
       cl.target_value,
       cl.unit,
       cl.status,
       cl.observed_at,
       COALESCE(bc.name, pi.initiative_name, ta.name, ts.session_topic,
                it.source_event_type, so.outcome_name) AS linked_record_name
FROM coordination_learning_link cl
JOIN coordination_alliance ca ON ca.id = cl.alliance_id
LEFT JOIN business_capability bc ON bc.id = cl.capability_id
LEFT JOIN process_improvement pi ON pi.id = cl.process_improvement_id
LEFT JOIN technology_alternative ta ON ta.id = cl.technology_alternative_id
LEFT JOIN training_session ts ON ts.id = cl.training_session_id
LEFT JOIN insight_transfer it ON it.id = cl.insight_transfer_id
LEFT JOIN stakeholder_outcome so ON so.id = cl.stakeholder_outcome_id;

COMMENT ON TABLE coordination_learning_link IS 'Governed evidence links from coordination to capability, learning, process, technology, insight, and stakeholder outcomes; never ownership or reputation';
COMMENT ON TABLE coordination_metric_observation IS 'Explainable, reviewable coordination metric observations with methodology and evidence';
