-- ============================================================
-- 311_relationship_reference_policy.sql
-- Governance registry for intentionally polymorphic relationships.
-- ============================================================

CREATE TABLE IF NOT EXISTS relationship_reference_policy (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    table_name VARCHAR(150) NOT NULL,
    type_column VARCHAR(100) NOT NULL,
    id_column VARCHAR(100) NOT NULL,
    allowed_type_values TEXT[] NOT NULL,
    enforcement_status VARCHAR(30) NOT NULL DEFAULT 'inventory_only'
        CHECK (enforcement_status IN ('inventory_only', 'registry_validated', 'typed_table_planned', 'typed_table_complete')),
    replacement_target VARCHAR(150),
    owning_domain VARCHAR(80) NOT NULL,
    rationale TEXT NOT NULL,
    review_due DATE,
    status VARCHAR(20) NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'retired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (table_name, type_column, id_column)
);

INSERT INTO relationship_reference_policy (
    table_name, type_column, id_column, allowed_type_values,
    enforcement_status, replacement_target, owning_domain, rationale
)
VALUES
    ('party_relationship', 'scope_type', 'scope_id',
     ARRAY['network', 'organization', 'location', 'farm', 'cooperative', 'value_stream', 'initiative', 'decision'],
     'registry_validated', 'typed scope registry', 'stakeholders',
     'Stakeholder relationships may be scoped to several governed domain entities.'),
    ('strategy_advantage_link', 'entity_type', 'entity_id',
     ARRAY['capability', 'market_segment', 'stakeholder', 'metric'],
     'typed_table_planned', 'strategy advantage typed links', 'strategy',
     'Strategy advantage links retain a typed target until domain-specific link tables are complete.'),
    ('strategy_evidence_link', 'source_type', 'source_id',
     ARRAY['pestel_factor', 'swot_factor', 'competitive_signal', 'competitive_force', 'scenario', 'threat_signal', 'stakeholder_outcome', 'crisp_assessment', 'metric_value', 'capability', 'market_segment', 'external_document'],
     'registry_validated', 'evidence source registry', 'evidence',
     'Evidence sources span governed analytical and external-document entities.')
ON CONFLICT (table_name, type_column, id_column) DO UPDATE SET
    allowed_type_values = EXCLUDED.allowed_type_values,
    enforcement_status = EXCLUDED.enforcement_status,
    replacement_target = EXCLUDED.replacement_target,
    owning_domain = EXCLUDED.owning_domain,
    rationale = EXCLUDED.rationale,
    updated_at = NOW();

CREATE INDEX IF NOT EXISTS idx_relationship_reference_policy_status
    ON relationship_reference_policy(status, enforcement_status, owning_domain);

COMMENT ON TABLE relationship_reference_policy IS
    'Explicit inventory and retirement plan for relationships that cannot yet use direct foreign keys';
