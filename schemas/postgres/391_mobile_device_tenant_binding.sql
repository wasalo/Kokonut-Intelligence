-- Pin Field Collector enrollments to the verified organization owner that
-- approved them. Existing rows are deliberately left NULL: ownership cannot
-- be reconstructed safely from the current device row alone.

BEGIN;

ALTER TABLE mobile_device_enrollment
    ADD COLUMN IF NOT EXISTS tenant_organization_id UUID
        REFERENCES organization(id) ON DELETE RESTRICT;

ALTER TABLE mobile_device
    ADD COLUMN IF NOT EXISTS tenant_organization_id UUID
        REFERENCES organization(id) ON DELETE RESTRICT;

CREATE INDEX IF NOT EXISTS idx_mobile_device_tenant_location_active
    ON mobile_device (tenant_organization_id, location_id, device_id)
    WHERE status = 'active' AND tenant_organization_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_mobile_device_enrollment_tenant_location_active
    ON mobile_device_enrollment (tenant_organization_id, location_id, expires_at)
    WHERE used_at IS NULL AND revoked_at IS NULL
      AND tenant_organization_id IS NOT NULL;

CREATE OR REPLACE FUNCTION guard_mobile_tenant_binding()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF TG_OP = 'UPDATE' AND (
        NEW.location_id IS DISTINCT FROM OLD.location_id
        OR NEW.tenant_organization_id IS DISTINCT FROM OLD.tenant_organization_id
    ) THEN
        RAISE EXCEPTION 'mobile device and enrollment tenant bindings are immutable';
    END IF;

    IF TG_OP = 'INSERT' AND NEW.tenant_organization_id IS NOT NULL THEN
        PERFORM 1
          FROM location AS loc
          JOIN location_tenant_owner_verification AS owner
            ON owner.location_id = loc.id
           AND owner.organization_id = loc.organization_id
           AND owner.revoked_at IS NULL
          JOIN organization AS tenant
            ON tenant.id = owner.organization_id
           AND tenant.status = 'active'
         WHERE loc.id = NEW.location_id
           AND loc.status = 'active'
           AND owner.organization_id = NEW.tenant_organization_id
         FOR SHARE OF loc, owner, tenant;
        IF NOT FOUND THEN
            RAISE EXCEPTION 'mobile enrollment must match the current verified location owner';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_guard_mobile_device_tenant_binding ON mobile_device;
CREATE TRIGGER trg_guard_mobile_device_tenant_binding
BEFORE INSERT OR UPDATE ON mobile_device
FOR EACH ROW EXECUTE FUNCTION guard_mobile_tenant_binding();

DROP TRIGGER IF EXISTS trg_guard_mobile_enrollment_tenant_binding ON mobile_device_enrollment;
CREATE TRIGGER trg_guard_mobile_enrollment_tenant_binding
BEFORE INSERT OR UPDATE ON mobile_device_enrollment
FOR EACH ROW EXECUTE FUNCTION guard_mobile_tenant_binding();

COMMENT ON COLUMN mobile_device_enrollment.tenant_organization_id IS
    'Verified location owner at enrollment-code issuance; NULL legacy rows cannot register until re-enrolled.';
COMMENT ON COLUMN mobile_device.tenant_organization_id IS
    'Verified location owner at device registration; tenant-protected access fails after owner transfer until re-enrollment.';
COMMENT ON FUNCTION guard_mobile_tenant_binding() IS
    'Requires new Field Collector device/enrollment bindings to match the current verified owner and makes bindings immutable.';

COMMIT;
