-- 163_carbon_retirement_integrity.sql
-- Approval-safe, concurrent-safe legacy carbon credit retirement.

BEGIN;

ALTER TABLE carbon_credit
    ADD COLUMN IF NOT EXISTS reserved_tonnes NUMERIC(12,4) NOT NULL DEFAULT 0;

ALTER TABLE credit_retirement
    ADD COLUMN IF NOT EXISTS idempotency_key VARCHAR(255),
    ADD COLUMN IF NOT EXISTS confirmed_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ;

UPDATE credit_retirement
SET idempotency_key = 'legacy:' || id::text
WHERE idempotency_key IS NULL;

ALTER TABLE credit_retirement ALTER COLUMN idempotency_key SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_credit_retirement_idempotency_key
    ON credit_retirement (idempotency_key);

DROP VIEW IF EXISTS v_public_carbon_credit_inventory;
DROP VIEW IF EXISTS v_carbon_credit_balance;

ALTER TABLE carbon_credit DROP COLUMN available_tonnes;
ALTER TABLE carbon_credit ADD COLUMN available_tonnes NUMERIC(12,4)
    GENERATED ALWAYS AS (issuable_tonnes - retired_tonnes - reserved_tonnes) STORED;

ALTER TABLE carbon_credit DROP CONSTRAINT IF EXISTS chk_carbon_credit_quantities;
ALTER TABLE carbon_credit ADD CONSTRAINT chk_carbon_credit_quantities CHECK (
    initial_sequestration_tonnes >= 0
    AND current_sequestration_tonnes >= 0
    AND issuable_tonnes >= 0
    AND retired_tonnes >= 0
    AND reserved_tonnes >= 0
    AND retired_tonnes + reserved_tonnes <= issuable_tonnes
);

ALTER TABLE credit_retirement DROP CONSTRAINT IF EXISTS chk_credit_retire_lifecycle;
ALTER TABLE credit_retirement ADD CONSTRAINT chk_credit_retire_lifecycle
    CHECK (status IN ('draft', 'submitted', 'verified', 'published', 'rejected', 'cancelled'));

ALTER TABLE credit_retirement DROP CONSTRAINT IF EXISTS chk_credit_retire_approval;
ALTER TABLE credit_retirement ADD CONSTRAINT chk_credit_retire_approval CHECK (
    status NOT IN ('verified', 'published')
    OR (
        reviewer_id IS NOT NULL
        AND review_date IS NOT NULL
        AND confirmed_at IS NOT NULL
        AND (created_by IS NULL OR reviewer_id <> created_by)
    )
);

CREATE OR REPLACE VIEW v_public_carbon_credit_inventory AS
SELECT
    cc.id, cc.credit_code, cc.location_id, l.name AS location_name,
    cc.vintage_year, cc.methodology, cc.current_sequestration_tonnes,
    cc.issuable_tonnes, cc.retired_tonnes, cc.reserved_tonnes,
    cc.available_tonnes, cc.effective_price_per_tonne_usd,
    cc.total_value_usd, cc.buffer_pool_pct, cc.evidence_maturity,
    em.label AS evidence_maturity_label, cc.external_verifier,
    cc.methodology_ref, cc.attestation_uid, cc.attested_at, cc.status
FROM carbon_credit cc
JOIN location l ON l.id = cc.location_id
LEFT JOIN evidence_maturity_level em ON em.level = cc.evidence_maturity
WHERE cc.status = 'published'
  AND cc.evidence_maturity = 6
  AND EXISTS (
      SELECT 1 FROM farm_registry_record fr
      WHERE fr.location_id = cc.location_id
        AND fr.status IN ('verified', 'published')
  );

CREATE OR REPLACE VIEW v_carbon_credit_balance AS
SELECT
    cc.location_id, l.name AS location_name, COUNT(*) AS total_credits,
    SUM(cc.issuable_tonnes) AS total_issuable_tonnes,
    SUM(cc.retired_tonnes) AS total_retired_tonnes,
    SUM(cc.reserved_tonnes) AS total_reserved_tonnes,
    SUM(cc.available_tonnes) AS total_available_tonnes,
    SUM(cc.total_value_usd) AS total_value_usd,
    COUNT(*) FILTER (WHERE cc.status = 'published') AS published_count,
    COUNT(*) FILTER (WHERE cc.status = 'retired') AS retired_count,
    MAX(cc.vintage_year) AS latest_vintage
FROM carbon_credit cc
JOIN location l ON l.id = cc.location_id
WHERE cc.status IN ('published', 'retired')
GROUP BY cc.location_id, l.name;

INSERT INTO schema_version (version, description, applied_by)
VALUES ('carbon-retirement-integrity-v1', 'Approval-safe carbon retirement reservations', 'schema 163')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;

COMMIT;
