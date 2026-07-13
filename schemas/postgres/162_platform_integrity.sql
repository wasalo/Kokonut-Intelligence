-- 162_platform_integrity.sql
-- Reviewer attribution for governed metric verification.

BEGIN;

ALTER TABLE metric_value
    ADD COLUMN IF NOT EXISTS verified_by UUID,
    ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS verification_notes TEXT;

ALTER TABLE metric_value DROP CONSTRAINT IF EXISTS chk_metric_value_verification;
ALTER TABLE metric_value ADD CONSTRAINT chk_metric_value_verification CHECK (
    verified = FALSE
    OR (verified_by IS NOT NULL AND verified_at IS NOT NULL)
) NOT VALID;

CREATE INDEX IF NOT EXISTS idx_metric_value_verification
    ON metric_value (verified, verified_at);

INSERT INTO schema_version (version, description, applied_by)
VALUES ('platform-integrity-v1', 'Reviewer attribution for governed metric verification', 'schema 162')
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;

COMMIT;
