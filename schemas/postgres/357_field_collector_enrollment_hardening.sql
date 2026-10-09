-- ============================================================
-- 357_field_collector_enrollment_hardening.sql
-- Trusted device enrollment, revocation metadata, and public form scope.
-- ============================================================

ALTER TABLE mobile_form
    ADD COLUMN IF NOT EXISTS is_public BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE mobile_device
    ADD COLUMN IF NOT EXISTS revoked_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS mobile_device_enrollment (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code_hash           TEXT NOT NULL UNIQUE,
    user_id             VARCHAR(200) NOT NULL,
    location_id         UUID NOT NULL REFERENCES location(id),
    created_by          VARCHAR(200) NOT NULL,
    expires_at          TIMESTAMPTZ NOT NULL,
    used_at             TIMESTAMPTZ,
    consumed_device_id  VARCHAR(200),
    revoked_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_mobile_device_enrollment_expiry CHECK (expires_at > created_at)
);

CREATE INDEX IF NOT EXISTS idx_mobile_device_enrollment_location_expiry
    ON mobile_device_enrollment (location_id, expires_at);
CREATE INDEX IF NOT EXISTS idx_mobile_device_enrollment_active
    ON mobile_device_enrollment (expires_at)
    WHERE used_at IS NULL AND revoked_at IS NULL;

INSERT INTO schema_version (version, description, applied_by)
VALUES (
    'field-collector-enrollment-v1',
    'Trusted Field Collector enrollment, revocation metadata, and public form scope (schema 357)',
    'schema 357'
)
ON CONFLICT (version) DO UPDATE SET
    description = EXCLUDED.description,
    applied_by = EXCLUDED.applied_by;
