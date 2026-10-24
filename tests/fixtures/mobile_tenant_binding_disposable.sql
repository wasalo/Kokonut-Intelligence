-- Disposable PostgreSQL acceptance for migration 391 only.
-- Execute against an empty throwaway database: this fixture creates test tables.
\set ON_ERROR_STOP on

CREATE TABLE organization (
    id UUID PRIMARY KEY,
    status TEXT NOT NULL
);
CREATE TABLE location (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organization(id),
    status TEXT NOT NULL
);
CREATE TABLE location_tenant_owner_verification (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL REFERENCES location(id),
    organization_id UUID NOT NULL REFERENCES organization(id),
    revoked_at TIMESTAMPTZ
);
CREATE TABLE mobile_device_enrollment (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL REFERENCES location(id),
    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
);
CREATE TABLE mobile_device (
    id UUID PRIMARY KEY,
    device_id TEXT NOT NULL UNIQUE,
    location_id UUID NOT NULL REFERENCES location(id),
    status TEXT NOT NULL,
    revoked_at TIMESTAMPTZ,
    device_token_hash TEXT
);

INSERT INTO organization (id, status) VALUES
    ('a0000000-0000-0000-0000-000000000801', 'active'),
    ('a0000000-0000-0000-0000-000000000802', 'active');
INSERT INTO location (id, organization_id, status)
VALUES (
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000801',
    'active'
);
INSERT INTO location_tenant_owner_verification (id, location_id, organization_id)
VALUES (
    'a0000000-0000-0000-0000-000000000901',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000801'
);

-- Existing rows deliberately have no tenant columns yet and must remain legacy NULL rows.
INSERT INTO mobile_device_enrollment (id, location_id, expires_at)
VALUES (
    'a0000000-0000-0000-0000-000000000911',
    'a0000000-0000-0000-0000-000000000001',
    NOW() + INTERVAL '1 hour'
);
INSERT INTO mobile_device (id, device_id, location_id, status, device_token_hash)
VALUES (
    'a0000000-0000-0000-0000-000000000921',
    'legacy-owner-device',
    'a0000000-0000-0000-0000-000000000001',
    'active',
    'synthetic-token-hash'
);

\ir ../../schemas/postgres/391_mobile_device_tenant_binding.sql
\ir ../../schemas/postgres/391_mobile_device_tenant_binding.sql

DO $$
BEGIN
    IF (SELECT tenant_organization_id FROM mobile_device
         WHERE device_id = 'legacy-owner-device') IS NOT NULL THEN
        RAISE EXCEPTION 'migration must not infer a legacy device owner';
    END IF;
    IF (SELECT tenant_organization_id FROM mobile_device_enrollment
         WHERE id = 'a0000000-0000-0000-0000-000000000911') IS NOT NULL THEN
        RAISE EXCEPTION 'migration must not infer a legacy enrollment owner';
    END IF;
END;
$$;

INSERT INTO mobile_device_enrollment (
    id, location_id, expires_at, tenant_organization_id
) VALUES (
    'a0000000-0000-0000-0000-000000000912',
    'a0000000-0000-0000-0000-000000000001',
    NOW() + INTERVAL '1 hour',
    'a0000000-0000-0000-0000-000000000801'
);
INSERT INTO mobile_device (
    id, device_id, location_id, status, device_token_hash, tenant_organization_id
) VALUES (
    'a0000000-0000-0000-0000-000000000922',
    'current-owner-device',
    'a0000000-0000-0000-0000-000000000001',
    'active',
    'synthetic-current-token-hash',
    'a0000000-0000-0000-0000-000000000801'
);

DO $$
BEGIN
    BEGIN
        INSERT INTO mobile_device_enrollment (
            id, location_id, expires_at, tenant_organization_id
        ) VALUES (
            'a0000000-0000-0000-0000-000000000913',
            'a0000000-0000-0000-0000-000000000001',
            NOW() + INTERVAL '1 hour',
            'a0000000-0000-0000-0000-000000000802'
        );
        RAISE EXCEPTION 'wrong-owner enrollment unexpectedly succeeded';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM NOT LIKE '%must match the current verified location owner%' THEN
            RAISE;
        END IF;
    END;

    BEGIN
        INSERT INTO mobile_device (
            id, device_id, location_id, status, device_token_hash, tenant_organization_id
        ) VALUES (
            'a0000000-0000-0000-0000-000000000923',
            'wrong-owner-device',
            'a0000000-0000-0000-0000-000000000001',
            'active',
            'synthetic-wrong-token-hash',
            'a0000000-0000-0000-0000-000000000802'
        );
        RAISE EXCEPTION 'wrong-owner device insert unexpectedly succeeded';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM NOT LIKE '%must match the current verified location owner%' THEN
            RAISE;
        END IF;
    END;

    BEGIN
        UPDATE mobile_device
           SET tenant_organization_id = 'a0000000-0000-0000-0000-000000000802'
         WHERE device_id = 'current-owner-device';
        RAISE EXCEPTION 'device tenant binding unexpectedly changed';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM NOT LIKE '%tenant bindings are immutable%' THEN
            RAISE;
        END IF;
    END;

    BEGIN
        UPDATE mobile_device_enrollment
           SET tenant_organization_id = 'a0000000-0000-0000-0000-000000000802'
         WHERE id = 'a0000000-0000-0000-0000-000000000912';
        RAISE EXCEPTION 'enrollment tenant binding unexpectedly changed';
    EXCEPTION WHEN raise_exception THEN
        IF SQLERRM NOT LIKE '%tenant bindings are immutable%' THEN
            RAISE;
        END IF;
    END;
END;
$$;

-- Simulate a verified owner transfer. The existing device remains pinned to the
-- former organization and the runtime context predicate must stop authorizing it.
UPDATE location_tenant_owner_verification
   SET revoked_at = NOW()
 WHERE location_id = 'a0000000-0000-0000-0000-000000000001'
   AND revoked_at IS NULL;
UPDATE location
   SET organization_id = 'a0000000-0000-0000-0000-000000000802'
 WHERE id = 'a0000000-0000-0000-0000-000000000001';
INSERT INTO location_tenant_owner_verification (id, location_id, organization_id)
VALUES (
    'a0000000-0000-0000-0000-000000000902',
    'a0000000-0000-0000-0000-000000000001',
    'a0000000-0000-0000-0000-000000000802'
);

DO $$
DECLARE
    authorized_rows INTEGER;
BEGIN
    SELECT COUNT(*) INTO authorized_rows
      FROM mobile_device AS device
      JOIN location AS loc ON loc.id = device.location_id
      JOIN location_tenant_owner_verification AS owner
        ON owner.location_id = loc.id
       AND owner.organization_id = loc.organization_id
       AND owner.revoked_at IS NULL
      JOIN organization AS tenant
        ON tenant.id = owner.organization_id
       AND tenant.status = 'active'
     WHERE device.device_id = 'current-owner-device'
       AND device.tenant_organization_id = loc.organization_id
       AND device.status = 'active'
       AND device.device_token_hash IS NOT NULL;
    IF authorized_rows <> 0 THEN
        RAISE EXCEPTION 'former-owner device retained protected access';
    END IF;
END;
$$;

INSERT INTO mobile_device (
    id, device_id, location_id, status, device_token_hash, tenant_organization_id
) VALUES (
    'a0000000-0000-0000-0000-000000000924',
    'reenrolled-current-owner-device',
    'a0000000-0000-0000-0000-000000000001',
    'active',
    'synthetic-new-token-hash',
    'a0000000-0000-0000-0000-000000000802'
);

SELECT 'migration 391 disposable acceptance passed' AS result;
