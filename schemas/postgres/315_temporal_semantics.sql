-- ============================================================
-- 315_temporal_semantics.sql
-- Explicit current-state and historical interval semantics.
-- ============================================================

CREATE EXTENSION IF NOT EXISTS btree_gist;

ALTER TABLE role_assignment
    ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS valid_until TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS supersedes_id UUID REFERENCES role_assignment(id) ON DELETE SET NULL;

UPDATE role_assignment
SET valid_from = COALESCE(valid_from, assigned_at),
    valid_until = COALESCE(valid_until, expires_at)
WHERE valid_from IS NULL;

ALTER TABLE data_sharing_consent
    ADD COLUMN IF NOT EXISTS valid_from TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS valid_until TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS supersedes_id UUID REFERENCES data_sharing_consent(id) ON DELETE SET NULL;

UPDATE data_sharing_consent
SET valid_from = COALESCE(valid_from, consent_date),
    valid_until = COALESCE(valid_until, withdrawal_date)
WHERE valid_from IS NULL;

ALTER TABLE party_relationship
    ADD COLUMN IF NOT EXISTS supersedes_id UUID REFERENCES party_relationship(id) ON DELETE SET NULL;

ALTER TABLE stakeholder_salience_assessment
    ADD COLUMN IF NOT EXISTS is_current BOOLEAN NOT NULL DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS supersedes_id UUID REFERENCES stakeholder_salience_assessment(id) ON DELETE SET NULL;

WITH ranked AS (
    SELECT id,
           ROW_NUMBER() OVER (
               PARTITION BY party_id, interest_id
               ORDER BY assessed_at DESC, id DESC
           ) AS position
    FROM stakeholder_salience_assessment
)
UPDATE stakeholder_salience_assessment s
SET is_current = ranked.position = 1
FROM ranked
WHERE ranked.id = s.id;

CREATE UNIQUE INDEX IF NOT EXISTS uq_current_salience_party_interest
    ON stakeholder_salience_assessment(
        party_id,
        COALESCE(interest_id, '00000000-0000-0000-0000-000000000000'::uuid)
    )
    WHERE is_current = TRUE;

ALTER TABLE role_assignment
    DROP CONSTRAINT IF EXISTS chk_role_valid_interval;
ALTER TABLE role_assignment
    ADD CONSTRAINT chk_role_valid_interval
    CHECK (valid_until IS NULL OR valid_from IS NULL OR valid_until > valid_from);

ALTER TABLE data_sharing_consent
    DROP CONSTRAINT IF EXISTS chk_consent_valid_interval;
ALTER TABLE data_sharing_consent
    ADD CONSTRAINT chk_consent_valid_interval
    CHECK (valid_until IS NULL OR valid_from IS NULL OR valid_until > valid_from);

ALTER TABLE party_relationship
    DROP CONSTRAINT IF EXISTS chk_party_relationship_valid_interval;
ALTER TABLE party_relationship
    ADD CONSTRAINT chk_party_relationship_valid_interval
    CHECK (valid_until IS NULL OR valid_from IS NULL OR valid_until >= valid_from);

ALTER TABLE location
    ADD COLUMN IF NOT EXISTS baseline_recorded_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS location_baseline (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    location_id UUID NOT NULL REFERENCES location(id) ON DELETE CASCADE,
    effective_from DATE NOT NULL,
    effective_until DATE,
    baseline_revenue NUMERIC(15,2),
    baseline_asset_value NUMERIC(15,2),
    baseline_cash_flow NUMERIC(15,2),
    baseline_cost NUMERIC(15,2),
    assumptions JSONB NOT NULL DEFAULT '{}'::jsonb,
    source_ref TEXT,
    supersedes_id UUID REFERENCES location_baseline(id) ON DELETE SET NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    recorded_by UUID,
    CHECK (effective_until IS NULL OR effective_until > effective_from),
    EXCLUDE USING gist (
        location_id WITH =,
        (daterange(effective_from, effective_until, '[)')) WITH &&
    )
);

CREATE INDEX IF NOT EXISTS idx_location_baseline_location
    ON location_baseline(location_id, effective_from DESC);

INSERT INTO location_baseline (
    location_id, effective_from, baseline_revenue, baseline_asset_value,
    baseline_cash_flow, baseline_cost, assumptions, source_ref
)
SELECT id,
       COALESCE(baseline_date, created_at::date),
       baseline_revenue,
       baseline_asset_value,
       baseline_cash_flow,
       baseline_cost,
       COALESCE(baseline_assumptions, '{}'::jsonb),
       baseline_source
FROM location
WHERE baseline_revenue IS NOT NULL
   OR baseline_asset_value IS NOT NULL
   OR baseline_cash_flow IS NOT NULL
   OR baseline_cost IS NOT NULL
ON CONFLICT DO NOTHING;

CREATE OR REPLACE VIEW v_current_location_baseline AS
SELECT DISTINCT ON (location_id)
       id,
       location_id,
       effective_from,
       effective_until,
       baseline_revenue,
       baseline_asset_value,
       baseline_cash_flow,
       baseline_cost,
       assumptions,
       source_ref,
       recorded_at
FROM location_baseline
WHERE effective_from <= CURRENT_DATE
  AND (effective_until IS NULL OR effective_until > CURRENT_DATE)
ORDER BY location_id, effective_from DESC, recorded_at DESC;

ALTER TABLE role_assignment
    DROP CONSTRAINT IF EXISTS ex_role_assignment_active_interval;
ALTER TABLE role_assignment
    ADD CONSTRAINT ex_role_assignment_active_interval
    EXCLUDE USING gist (
        farmer_id WITH =,
        (COALESCE(location_id, '00000000-0000-0000-0000-000000000000'::uuid)) WITH =,
        role WITH =,
        scope WITH =,
        (tstzrange(COALESCE(valid_from, '-infinity'::timestamptz), COALESCE(valid_until, 'infinity'::timestamptz), '[)')) WITH &&
    ) WHERE (status = 'active');

ALTER TABLE data_sharing_consent
    DROP CONSTRAINT IF EXISTS ex_consent_active_interval;
ALTER TABLE data_sharing_consent
    ADD CONSTRAINT ex_consent_active_interval
    EXCLUDE USING gist (
        farmer_id WITH =,
        data_type WITH =,
        (COALESCE(data_scope, '')) WITH =,
        recipient_type WITH =,
        (COALESCE(recipient_id, '00000000-0000-0000-0000-000000000000'::uuid)) WITH =,
        (COALESCE(purpose, '')) WITH =,
        (tstzrange(COALESCE(valid_from, '-infinity'::timestamptz), COALESCE(valid_until, 'infinity'::timestamptz), '[)')) WITH &&
    ) WHERE (status = 'active' AND consent_given = TRUE);

ALTER TABLE party_relationship
    DROP CONSTRAINT IF EXISTS ex_party_relationship_active_interval;
ALTER TABLE party_relationship
    ADD CONSTRAINT ex_party_relationship_active_interval
    EXCLUDE USING gist (
        from_party_id WITH =,
        to_party_id WITH =,
        relationship_type WITH =,
        scope_type WITH =,
        (COALESCE(scope_id, '00000000-0000-0000-0000-000000000000'::uuid)) WITH =,
        (daterange(COALESCE(valid_from, '-infinity'::date), COALESCE(valid_until, 'infinity'::date), '[]')) WITH &&
    ) WHERE (status = 'active');

COMMENT ON TABLE location_baseline IS 'Effective-dated location baseline history; location columns remain a current-state compatibility projection';
COMMENT ON VIEW v_current_location_baseline IS 'Current location baseline selected from effective-dated history';
