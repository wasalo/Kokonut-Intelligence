CREATE ROLE kokonut_runtime NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
CREATE ROLE kokonut_directus_runtime NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;

CREATE SCHEMA kokonut_security;
CREATE TABLE organization (
    id UUID PRIMARY KEY,
    org_key TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE location (
    id UUID PRIMARY KEY,
    organization_id UUID NOT NULL REFERENCES organization(id),
    status TEXT NOT NULL DEFAULT 'active'
);
CREATE TABLE operator_identity (
    id UUID PRIMARY KEY,
    enabled BOOLEAN NOT NULL DEFAULT TRUE
);
CREATE TABLE operator_organization_membership (
    operator_id UUID NOT NULL REFERENCES operator_identity(id),
    organization_id UUID NOT NULL REFERENCES organization(id),
    revoked_at TIMESTAMPTZ,
    PRIMARY KEY (operator_id, organization_id)
);
CREATE TABLE location_tenant_owner_verification (
    location_id UUID NOT NULL REFERENCES location(id),
    organization_id UUID NOT NULL REFERENCES organization(id),
    revoked_at TIMESTAMPTZ,
    PRIMARY KEY (location_id, organization_id)
);
CREATE TABLE location_organization_share (
    location_id UUID NOT NULL REFERENCES location(id),
    organization_id UUID NOT NULL REFERENCES organization(id),
    revoked_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ,
    PRIMARY KEY (location_id, organization_id)
);
CREATE TABLE operator_scope_grant (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES operator_identity(id),
    resource TEXT NOT NULL,
    action TEXT NOT NULL,
    location_id UUID NOT NULL REFERENCES location(id),
    organization_id UUID NOT NULL REFERENCES organization(id),
    revoked_at TIMESTAMPTZ
);
CREATE TABLE farm (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL REFERENCES location(id)
);
CREATE TABLE plot (
    id UUID PRIMARY KEY,
    farm_id UUID NOT NULL REFERENCES farm(id)
);
CREATE TABLE crop_cycle (
    id UUID PRIMARY KEY,
    location_id UUID NOT NULL REFERENCES location(id)
);
CREATE TABLE farm_activity (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    plot_id UUID REFERENCES plot(id),
    crop_cycle_id UUID REFERENCES crop_cycle(id),
    location_id UUID NOT NULL REFERENCES location(id),
    activity_type VARCHAR(100) NOT NULL,
    activity_date DATE NOT NULL,
    description TEXT,
    labor_hours NUMERIC(8,2),
    labor_cost NUMERIC(12,2),
    materials_used JSONB DEFAULT '[]',
    evidence_urls TEXT[],
    evidence_hashes TEXT[],
    notes TEXT,
    status VARCHAR(50) DEFAULT 'draft',
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    rejection_reason TEXT,
    schema_version VARCHAR(20),
    source_system VARCHAR(100),
    source_id VARCHAR(255),
    source_raw JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID,
    updated_by UUID
);

INSERT INTO organization (id, org_key) VALUES
    ('a0000000-0000-0000-0000-000000000701', 'kokonut-network'),
    ('a0000000-0000-0000-0000-000000000702', 'other-tenant');
INSERT INTO location (id, organization_id) VALUES
    ('a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000701'),
    ('a0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000702');
INSERT INTO operator_identity (id) VALUES
    ('a0000000-0000-0000-0000-000000000901'),
    ('a0000000-0000-0000-0000-000000000902'),
    ('a0000000-0000-0000-0000-000000000903'),
    ('a0000000-0000-0000-0000-000000000904');
INSERT INTO operator_organization_membership (operator_id, organization_id) VALUES
    ('a0000000-0000-0000-0000-000000000901', 'a0000000-0000-0000-0000-000000000701'),
    ('a0000000-0000-0000-0000-000000000902', 'a0000000-0000-0000-0000-000000000701'),
    ('a0000000-0000-0000-0000-000000000903', 'a0000000-0000-0000-0000-000000000701'),
    ('a0000000-0000-0000-0000-000000000904', 'a0000000-0000-0000-0000-000000000702');
INSERT INTO location_tenant_owner_verification (location_id, organization_id) VALUES
    ('a0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000701'),
    ('a0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000702');
INSERT INTO farm (id, location_id) VALUES
    ('a0000000-0000-0000-0000-000000000101', 'a0000000-0000-0000-0000-000000000001'),
    ('a0000000-0000-0000-0000-000000000102', 'a0000000-0000-0000-0000-000000000002');
INSERT INTO plot (id, farm_id) VALUES
    ('a0000000-0000-0000-0000-000000000201', 'a0000000-0000-0000-0000-000000000101'),
    ('a0000000-0000-0000-0000-000000000202', 'a0000000-0000-0000-0000-000000000102');
INSERT INTO crop_cycle (id, location_id) VALUES
    ('a0000000-0000-0000-0000-000000000301', 'a0000000-0000-0000-0000-000000000001'),
    ('a0000000-0000-0000-0000-000000000302', 'a0000000-0000-0000-0000-000000000002');

INSERT INTO operator_scope_grant (operator_id, resource, action, location_id, organization_id)
SELECT scopes.operator_id, 'farm_activity', scopes.action, locations.location_id, location.organization_id
  FROM (VALUES
      ('a0000000-0000-0000-0000-000000000901'::uuid, 'create_draft'),
      ('a0000000-0000-0000-0000-000000000901'::uuid, 'read_detail'),
      ('a0000000-0000-0000-0000-000000000901'::uuid, 'edit_draft'),
      ('a0000000-0000-0000-0000-000000000901'::uuid, 'submit'),
      ('a0000000-0000-0000-0000-000000000901'::uuid, 'verify'),
      ('a0000000-0000-0000-0000-000000000901'::uuid, 'publish'),
      ('a0000000-0000-0000-0000-000000000902'::uuid, 'read_detail'),
      ('a0000000-0000-0000-0000-000000000902'::uuid, 'verify'),
      ('a0000000-0000-0000-0000-000000000903'::uuid, 'read_detail'),
      ('a0000000-0000-0000-0000-000000000903'::uuid, 'publish'),
      ('a0000000-0000-0000-0000-000000000904'::uuid, 'create_draft')
  ) AS scopes(operator_id, action)
  JOIN (VALUES
      ('a0000000-0000-0000-0000-000000000901'::uuid, 'a0000000-0000-0000-0000-000000000001'::uuid),
      ('a0000000-0000-0000-0000-000000000902'::uuid, 'a0000000-0000-0000-0000-000000000001'::uuid),
      ('a0000000-0000-0000-0000-000000000903'::uuid, 'a0000000-0000-0000-0000-000000000001'::uuid),
      ('a0000000-0000-0000-0000-000000000904'::uuid, 'a0000000-0000-0000-0000-000000000002'::uuid)
  ) AS locations(operator_id, location_id) ON locations.operator_id = scopes.operator_id
  JOIN location ON location.id = locations.location_id;

CREATE OR REPLACE FUNCTION public.operator_scope_grant_allows(
    requested_operator_id UUID,
    requested_resource TEXT,
    requested_action TEXT,
    requested_location_id UUID
)
RETURNS BOOLEAN LANGUAGE SQL STABLE SECURITY INVOKER AS $$
    SELECT EXISTS (
        SELECT 1
          FROM operator_scope_grant AS grant_row
          JOIN operator_identity AS identity
            ON identity.id = grant_row.operator_id AND identity.enabled
          JOIN location AS loc ON loc.id = grant_row.location_id
          JOIN organization AS tenant
            ON tenant.id = grant_row.organization_id
           AND tenant.id = loc.organization_id
           AND tenant.status = 'active'
          JOIN operator_organization_membership AS membership
            ON membership.operator_id = grant_row.operator_id
           AND membership.organization_id = grant_row.organization_id
           AND membership.revoked_at IS NULL
          JOIN location_tenant_owner_verification AS owner
            ON owner.location_id = loc.id
           AND owner.organization_id = loc.organization_id
           AND owner.revoked_at IS NULL
         WHERE grant_row.operator_id = requested_operator_id
           AND grant_row.resource = requested_resource
           AND grant_row.action = requested_action
           AND grant_row.location_id = requested_location_id
           AND grant_row.organization_id IS NOT NULL
           AND grant_row.revoked_at IS NULL
           AND (
               grant_row.organization_id = owner.organization_id
               OR EXISTS (
                   SELECT 1 FROM location_organization_share AS share
                    WHERE share.location_id = loc.id
                      AND share.organization_id = grant_row.organization_id
                      AND share.revoked_at IS NULL
                      AND (share.expires_at IS NULL OR share.expires_at > NOW())
               )
           )
    );
$$;

CREATE OR REPLACE FUNCTION kokonut_security.current_tenant_context()
RETURNS TABLE (tenant_id UUID, location_id UUID, actor_id UUID, actor_type TEXT)
LANGUAGE SQL STABLE AS $$
    SELECT NULLIF(current_setting('kokonut.tenant_id', TRUE), '')::UUID,
           NULLIF(current_setting('kokonut.location_id', TRUE), '')::UUID,
           NULLIF(current_setting('kokonut.actor_id', TRUE), '')::UUID,
           NULLIF(current_setting('kokonut.actor_type', TRUE), '')
    WHERE NULLIF(current_setting('kokonut.tenant_id', TRUE), '') IS NOT NULL
$$;

GRANT USAGE ON SCHEMA public, kokonut_security TO kokonut_runtime, kokonut_directus_runtime;
GRANT EXECUTE ON FUNCTION kokonut_security.current_tenant_context() TO PUBLIC;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO kokonut_runtime;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO kokonut_directus_runtime;
