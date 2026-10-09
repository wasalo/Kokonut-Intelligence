-- ============================================================
-- 215_stakeholder_consent.sql - Canonical consent event stream
-- ============================================================
-- Explicit consent is required for use. Legacy consent tables remain intact;
-- this table is the canonical, party-linked decision surface.

CREATE TABLE IF NOT EXISTS stakeholder_consent (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    party_id UUID NOT NULL REFERENCES party(id) ON DELETE CASCADE,
    event_type VARCHAR(20) NOT NULL CHECK (event_type IN ('grant', 'withdraw', 'deny', 'expire')),
    data_category VARCHAR(100) NOT NULL,
    purpose VARCHAR(255) NOT NULL,
    scope_type VARCHAR(30) NOT NULL DEFAULT 'network'
        CHECK (scope_type IN ('network', 'organization', 'location', 'farm', 'cooperative', 'value_stream', 'initiative', 'decision')),
    scope_id UUID,
    recipient_party_id UUID REFERENCES party(id) ON DELETE SET NULL,
    recipient_type VARCHAR(50) NOT NULL DEFAULT 'system',
    recipient_name VARCHAR(255),
    consent_method VARCHAR(50) NOT NULL DEFAULT 'digital_form'
        CHECK (consent_method IN ('digital_form', 'verbal_recorded', 'paper_scan', 'mobile_app', 'api', 'in_person', 'system_migration')),
    legal_basis VARCHAR(100) NOT NULL DEFAULT 'consent',
    consent_version VARCHAR(30) NOT NULL DEFAULT '1.0',
    effective_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ,
    reason TEXT,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_system VARCHAR(100) NOT NULL DEFAULT 'stakeholder_registry',
    source_record_id VARCHAR(255),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by UUID,
    CHECK (expires_at IS NULL OR expires_at > effective_at),
    CHECK (event_type = 'grant' OR NULLIF(TRIM(COALESCE(reason, '')), '') IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_stakeholder_consent_party
    ON stakeholder_consent(party_id, data_category, purpose, effective_at DESC);
CREATE INDEX IF NOT EXISTS idx_stakeholder_consent_recipient
    ON stakeholder_consent(recipient_party_id, recipient_type, effective_at DESC);
CREATE INDEX IF NOT EXISTS idx_stakeholder_consent_scope
    ON stakeholder_consent(scope_type, scope_id);
CREATE INDEX IF NOT EXISTS idx_stakeholder_consent_expiry
    ON stakeholder_consent(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_stakeholder_consent_source
    ON stakeholder_consent(source_system, source_record_id);

CREATE OR REPLACE VIEW v_effective_stakeholder_consent AS
SELECT DISTINCT ON (
    sc.party_id, sc.data_category, sc.purpose, sc.scope_type, sc.scope_id,
    sc.recipient_party_id, sc.recipient_type
)
    sc.id AS consent_event_id,
    sc.party_id,
    p.display_name AS party_name,
    sc.event_type,
    sc.data_category,
    sc.purpose,
    sc.scope_type,
    sc.scope_id,
    sc.recipient_party_id,
    rp.display_name AS recipient_party_name,
    sc.recipient_type,
    sc.recipient_name,
    sc.consent_method,
    sc.legal_basis,
    sc.consent_version,
    sc.effective_at,
    sc.expires_at,
    CASE
        WHEN sc.event_type = 'grant' AND sc.expires_at IS NOT NULL AND sc.expires_at <= NOW() THEN 'expired'
        WHEN sc.event_type = 'grant' THEN 'granted'
        WHEN sc.event_type = 'withdraw' THEN 'withdrawn'
        WHEN sc.event_type = 'deny' THEN 'denied'
        ELSE 'expired'
    END AS effective_status,
    (
        sc.event_type = 'grant'
        AND (sc.expires_at IS NULL OR sc.expires_at > NOW())
    ) AS consented,
    sc.reason,
    sc.evidence,
    sc.source_system,
    sc.source_record_id,
    sc.created_at
FROM stakeholder_consent sc
JOIN party p ON p.id = sc.party_id
LEFT JOIN party rp ON rp.id = sc.recipient_party_id
ORDER BY
    sc.party_id, sc.data_category, sc.purpose, sc.scope_type, sc.scope_id,
    sc.recipient_party_id, sc.recipient_type, sc.effective_at DESC, sc.created_at DESC;

CREATE OR REPLACE VIEW v_stakeholder_consent_audit AS
SELECT
    sc.id AS consent_event_id,
    sc.party_id,
    p.display_name AS party_name,
    sc.event_type,
    sc.data_category,
    sc.purpose,
    sc.recipient_type,
    sc.recipient_name,
    sc.effective_at,
    sc.expires_at,
    sc.reason,
    sc.source_system,
    sc.source_record_id,
    sc.created_at
FROM stakeholder_consent sc
JOIN party p ON p.id = sc.party_id
ORDER BY sc.created_at DESC;

CREATE OR REPLACE VIEW v_mappable_legacy_consent AS
SELECT
    'farmer_consent'::VARCHAR(50) AS source_type,
    fc.id AS source_id,
    pi.party_id,
    fc.data_category,
    fc.consent_scope AS purpose,
    fc.status,
    fc.granted_at AS effective_at,
    fc.expires_at,
    fc.consent_method,
    fc.legal_basis,
    fc.evidence_ref
FROM farmer_consent fc
JOIN party_identifier pi
  ON pi.identifier_type = 'farmer_profile_id'
 AND pi.identifier_value = fc.farmer_id
 AND pi.verification_status = 'verified'
UNION ALL
SELECT
    'data_sharing_consent',
    dsc.id,
    pi.party_id,
    dsc.data_type,
    dsc.purpose,
    CASE WHEN dsc.status = 'active' AND dsc.consent_given THEN 'granted' ELSE dsc.status END,
    dsc.consent_date,
    CASE WHEN dsc.retention_days IS NOT NULL THEN dsc.consent_date + (dsc.retention_days || ' days')::interval ELSE NULL END,
    'legacy_data_sharing',
    dsc.legal_basis,
    NULL
FROM data_sharing_consent dsc
JOIN party_identifier pi
  ON pi.identifier_type = 'farmer_profile_id'
 AND pi.identifier_value = dsc.farmer_id::text
 AND pi.verification_status = 'verified';

COMMENT ON TABLE stakeholder_consent IS 'Append-only canonical consent grants, withdrawals, denials, and expiries linked to party';
COMMENT ON VIEW v_effective_stakeholder_consent IS 'Latest consent decision per party, purpose, recipient, and scope; absence is not consent';
COMMENT ON VIEW v_mappable_legacy_consent IS 'Legacy consent records that can be imported only after verified party identity mapping';
