-- Mobile credential functions are internal Gateway operations. Replace their
-- historical PUBLIC grants with explicit application-runtime grants so an
-- isolated worker login cannot invoke unrelated SECURITY DEFINER functions.

BEGIN;

REVOKE ALL ON FUNCTION kokonut_security.resolve_mobile_device_token(TEXT)
    FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.redeem_mobile_enrollment(
    TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.set_mobile_device_context(
    TEXT, TEXT, UUID
) FROM PUBLIC;
REVOKE ALL ON FUNCTION kokonut_security.current_tenant_context()
    FROM PUBLIC;

DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_runtime') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.resolve_mobile_device_token(TEXT)
            TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.redeem_mobile_enrollment(
            TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT, TEXT
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.set_mobile_device_context(
            TEXT, TEXT, UUID
        ) TO kokonut_runtime;
        GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context()
            TO kokonut_runtime;
    END IF;
END;
$$;

COMMIT;
