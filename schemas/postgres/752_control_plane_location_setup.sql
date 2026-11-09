-- Authenticated, single-transaction location and farm setup from the Control Plane.
-- A DBA grants the global capability separately; creation records an explicit
-- tenant decision and gives the creator draft-only field activity access.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_location_setup_owner') THEN
        EXECUTE 'CREATE ROLE kokonut_location_setup_owner '
            'NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_location_setup_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'location setup owner must remain a non-login, unprivileged role';
    END IF;
    IF EXISTS (
        SELECT 1
          FROM pg_catalog.pg_auth_members membership
          JOIN pg_catalog.pg_roles role ON role.oid = membership.roleid
          JOIN pg_catalog.pg_roles member ON member.oid = membership.member
         WHERE role.rolname = 'kokonut_location_setup_owner'
            OR member.rolname = 'kokonut_location_setup_owner'
    ) THEN
        RAISE EXCEPTION 'location setup owner may not have or receive role memberships';
    END IF;
END;
$$;

ALTER TABLE kokonut_security.operator_global_capability
    DROP CONSTRAINT operator_global_capability_capability_code_check;
ALTER TABLE kokonut_security.operator_global_capability
    ADD CONSTRAINT operator_global_capability_capability_code_check
    CHECK (capability_code IN (
        'clickhouse_outbox:read',
        'clickhouse_outbox:replay',
        'clickhouse_outbox:resolve',
        'clickhouse_outbox:discard',
        'scheduler:read',
        'scheduler:enable',
        'scheduler:disable',
        'location_setup:create'
    ));

ALTER TABLE kokonut_security.operator_global_capability_audit
    DROP CONSTRAINT operator_global_capability_audit_capability_code_check;
ALTER TABLE kokonut_security.operator_global_capability_audit
    ADD CONSTRAINT operator_global_capability_audit_capability_code_check
    CHECK (capability_code IN (
        'clickhouse_outbox:read',
        'clickhouse_outbox:replay',
        'clickhouse_outbox:resolve',
        'clickhouse_outbox:discard',
        'scheduler:read',
        'scheduler:enable',
        'scheduler:disable',
        'location_setup:create'
    ));

CREATE OR REPLACE FUNCTION kokonut_security.operator_global_capability_allows(
    requested_session_token_hash TEXT,
    requested_capability_code TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    resolved_operator_id UUID;
BEGIN
    IF requested_capability_code NOT IN (
        'clickhouse_outbox:read',
        'clickhouse_outbox:replay',
        'clickhouse_outbox:resolve',
        'clickhouse_outbox:discard',
        'scheduler:read',
        'scheduler:enable',
        'scheduler:disable',
        'location_setup:create'
    ) THEN
        RETURN FALSE;
    END IF;
    resolved_operator_id := kokonut_security.resolve_clickhouse_outbox_operator_session(
        requested_session_token_hash
    );
    RETURN EXISTS (
        SELECT 1
          FROM kokonut_security.operator_global_capability capability
         WHERE capability.operator_id = resolved_operator_id
           AND capability.capability_code = requested_capability_code
           AND capability.revoked_at IS NULL
    );
END;
$$;
ALTER FUNCTION kokonut_security.operator_global_capability_allows(TEXT, TEXT)
    OWNER TO kokonut_operator_capability_owner;
REVOKE ALL ON FUNCTION kokonut_security.operator_global_capability_allows(TEXT, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.operator_global_capability_allows(TEXT, TEXT)
    TO kokonut_operator_auth;

CREATE OR REPLACE FUNCTION kokonut_security.grant_operator_global_capability(
    requested_operator_id UUID,
    requested_capability_code TEXT,
    requested_approved_by TEXT,
    requested_reason TEXT
)
RETURNS UUID
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    granted_id UUID;
BEGIN
    IF session_user IN ('kokonut_runtime', 'kokonut_operator_auth', 'kokonut_clickhouse_outbox_operator_login') THEN
        RAISE EXCEPTION 'DBA-approved capability provisioning is required' USING ERRCODE = '42501';
    END IF;
    IF requested_capability_code NOT IN (
        'clickhouse_outbox:read',
        'clickhouse_outbox:replay',
        'clickhouse_outbox:resolve',
        'clickhouse_outbox:discard',
        'scheduler:read',
        'scheduler:enable',
        'scheduler:disable',
        'location_setup:create'
    ) OR btrim(coalesce(requested_approved_by, '')) = ''
      OR btrim(coalesce(requested_reason, '')) = '' THEN
        RAISE EXCEPTION 'capability, approver, and reason are required' USING ERRCODE = '22023';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM public.operator_identity
         WHERE id = requested_operator_id AND enabled
    ) THEN
        RAISE EXCEPTION 'enabled operator identity is required' USING ERRCODE = '22023';
    END IF;
    INSERT INTO kokonut_security.operator_global_capability (
        operator_id, capability_code, granted_by_db_role, approved_by, grant_reason
    ) VALUES (
        requested_operator_id,
        requested_capability_code,
        session_user::TEXT,
        btrim(requested_approved_by),
        btrim(requested_reason)
    )
    RETURNING id INTO granted_id;
    INSERT INTO kokonut_security.operator_global_capability_audit (
        capability_id, operator_id, capability_code, action, actor_db_role, approved_by, reason
    ) VALUES (
        granted_id,
        requested_operator_id,
        requested_capability_code,
        'granted',
        session_user::TEXT,
        btrim(requested_approved_by),
        btrim(requested_reason)
    );
    RETURN granted_id;
END;
$$;
ALTER FUNCTION kokonut_security.grant_operator_global_capability(UUID, TEXT, TEXT, TEXT)
    OWNER TO kokonut_operator_capability_owner;
REVOKE ALL ON FUNCTION kokonut_security.grant_operator_global_capability(UUID, TEXT, TEXT, TEXT) FROM PUBLIC;

CREATE TABLE kokonut_security.location_setup_audit (
    id UUID PRIMARY KEY DEFAULT pg_catalog.gen_random_uuid(),
    operator_id UUID NOT NULL REFERENCES public.operator_identity(id) ON DELETE RESTRICT,
    organization_id UUID NOT NULL REFERENCES public.organization(id) ON DELETE RESTRICT,
    location_id UUID NOT NULL REFERENCES public.location(id) ON DELETE RESTRICT,
    farm_id UUID NOT NULL REFERENCES public.farm(id) ON DELETE RESTRICT,
    owner_decision_reference TEXT NOT NULL
        CHECK (length(btrim(owner_decision_reference)) BETWEEN 3 AND 2000),
    database_principal TEXT NOT NULL DEFAULT SESSION_USER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT pg_catalog.clock_timestamp()
);
ALTER TABLE kokonut_security.location_setup_audit OWNER TO kokonut_location_setup_owner;
ALTER TABLE kokonut_security.location_setup_audit ENABLE ROW LEVEL SECURITY;
ALTER TABLE kokonut_security.location_setup_audit FORCE ROW LEVEL SECURITY;
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_policies
         WHERE schemaname = 'kokonut_security'
           AND tablename = 'location_setup_audit'
           AND policyname = 'location_setup_audit_owner_all'
    ) THEN
        CREATE POLICY location_setup_audit_owner_all
            ON kokonut_security.location_setup_audit
            FOR ALL TO kokonut_location_setup_owner USING (true) WITH CHECK (true);
    END IF;
END;
$$;
REVOKE ALL ON TABLE kokonut_security.location_setup_audit FROM PUBLIC;

CREATE OR REPLACE FUNCTION kokonut_security.prevent_location_setup_audit_mutation()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $$
BEGIN
    RAISE EXCEPTION 'location setup audit is append-only';
END;
$$;
REVOKE ALL ON FUNCTION kokonut_security.prevent_location_setup_audit_mutation() FROM PUBLIC;
CREATE TRIGGER trg_location_setup_audit_append_only
    BEFORE UPDATE OR DELETE ON kokonut_security.location_setup_audit
    FOR EACH ROW EXECUTE FUNCTION kokonut_security.prevent_location_setup_audit_mutation();
CREATE TRIGGER trg_location_setup_audit_no_truncate
    BEFORE TRUNCATE ON kokonut_security.location_setup_audit
    FOR EACH STATEMENT EXECUTE FUNCTION kokonut_security.prevent_location_setup_audit_mutation();

CREATE OR REPLACE FUNCTION kokonut_security.location_setup_capability_allows(
    requested_operator_id UUID
)
RETURNS BOOLEAN
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
    SELECT EXISTS (
        SELECT 1
          FROM kokonut_security.operator_global_capability capability
          JOIN public.operator_identity identity
            ON identity.id = capability.operator_id AND identity.enabled
         WHERE capability.operator_id = requested_operator_id
           AND capability.capability_code = 'location_setup:create'
           AND capability.revoked_at IS NULL
    )
$$;
ALTER FUNCTION kokonut_security.location_setup_capability_allows(UUID)
    OWNER TO kokonut_operator_capability_owner;
REVOKE ALL ON FUNCTION kokonut_security.location_setup_capability_allows(UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.location_setup_capability_allows(UUID)
    TO kokonut_location_setup_owner;

GRANT USAGE, CREATE ON SCHEMA kokonut_security TO kokonut_location_setup_owner;
GRANT USAGE ON SCHEMA public TO kokonut_location_setup_owner;
GRANT SELECT (id, org_key, name, status) ON TABLE public.organization
    TO kokonut_location_setup_owner;
GRANT SELECT (id, name) ON TABLE public.location, public.farm
    TO kokonut_location_setup_owner;
GRANT SELECT (id, organization_id, slug) ON TABLE public.location
    TO kokonut_location_setup_owner;
GRANT SELECT (id, location_id, slug) ON TABLE public.farm
    TO kokonut_location_setup_owner;
GRANT UPDATE (
    name, description, boundary, center, country, region, sub_region,
    timezone, latitude, longitude, status, organization_id, updated_by
) ON TABLE public.location TO kokonut_location_setup_owner;
GRANT UPDATE (
    name, description, farm_type, total_area, area_unit, boundary, center,
    status, updated_by
) ON TABLE public.farm TO kokonut_location_setup_owner;
GRANT SELECT (id, organization_id, location_id, farm_id, membership_type, role, status, metadata)
    ON TABLE public.organization_member TO kokonut_location_setup_owner;
GRANT SELECT (location_id, organization_id, revoked_at)
    ON TABLE public.location_tenant_owner_verification TO kokonut_location_setup_owner;
GRANT SELECT (operator_id, resource, action, location_id, organization_id, revoked_at)
    ON TABLE public.operator_scope_grant TO kokonut_location_setup_owner;
GRANT SELECT (operator_id, organization_id, revoked_at)
    ON TABLE public.operator_organization_membership TO kokonut_location_setup_owner;
GRANT INSERT (
    name, slug, description, boundary, center, country, region, sub_region,
    timezone, latitude, longitude, status, organization_id, created_by, updated_by
) ON TABLE public.location TO kokonut_location_setup_owner;
GRANT INSERT (
    location_id, name, slug, description, farm_type, total_area, area_unit,
    boundary, center, status, created_by, updated_by
) ON TABLE public.farm TO kokonut_location_setup_owner;
GRANT INSERT (
    organization_id, location_id, farm_id, membership_type, role, status, metadata
) ON TABLE public.organization_member TO kokonut_location_setup_owner;
GRANT INSERT (
    location_id, organization_id, decision_reference, confirmed_by, confirmed_at
) ON TABLE public.location_tenant_owner_verification TO kokonut_location_setup_owner;
GRANT INSERT (
    operator_id, organization_id, membership_role, granted_by
) ON TABLE public.operator_organization_membership TO kokonut_location_setup_owner;
GRANT INSERT (
    operator_id, resource, action, location_id, granted_by, organization_id
) ON TABLE public.operator_scope_grant TO kokonut_location_setup_owner;
GRANT INSERT (
    operator_id, organization_id, location_id, farm_id, owner_decision_reference
) ON TABLE kokonut_security.location_setup_audit TO kokonut_location_setup_owner;

DO $$
DECLARE
    relation_name TEXT;
    relation_oid REGCLASS;
    policy_name TEXT;
BEGIN
    FOREACH relation_name IN ARRAY ARRAY[
        'public.location',
        'public.farm',
        'public.organization_member',
        'public.location_tenant_owner_verification',
        'public.operator_organization_membership',
        'public.operator_scope_grant'
    ] LOOP
        relation_oid := relation_name::REGCLASS;
        policy_name := 'location_setup_owner_' || split_part(relation_name, '.', 2) || '_insert';
        IF NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_policies
             WHERE schemaname = split_part(relation_name, '.', 1)
               AND tablename = split_part(relation_name, '.', 2)
               AND policyname = policy_name
        ) THEN
            EXECUTE format(
                'CREATE POLICY %I ON %s FOR INSERT TO kokonut_location_setup_owner WITH CHECK (true)',
                policy_name,
                relation_oid
            );
        END IF;
    END LOOP;
END;
$$;

-- Existing same-slug records can be completed by setup, so the definer also
-- needs narrowly scoped UPDATE policies where those tables already enforce RLS.
DO $$
DECLARE
    relation_name TEXT;
    relation_oid REGCLASS;
    policy_name TEXT;
BEGIN
    FOREACH relation_name IN ARRAY ARRAY[
        'public.location',
        'public.farm'
    ] LOOP
        relation_oid := relation_name::REGCLASS;
        policy_name := 'location_setup_owner_' || split_part(relation_name, '.', 2) || '_update';
        IF EXISTS (
            SELECT 1 FROM pg_catalog.pg_class relation
             WHERE relation.oid = relation_oid AND relation.relrowsecurity
        ) AND NOT EXISTS (
            SELECT 1 FROM pg_catalog.pg_policies
             WHERE schemaname = split_part(relation_name, '.', 1)
               AND tablename = split_part(relation_name, '.', 2)
               AND policyname = policy_name
        ) THEN
            EXECUTE format(
                'CREATE POLICY %I ON %s FOR UPDATE TO kokonut_location_setup_owner USING (true) WITH CHECK (true)',
                policy_name,
                relation_oid
            );
        END IF;
    END LOOP;
END;
$$;

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class relation
        JOIN pg_catalog.pg_namespace namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public' AND relation.relname = 'organization'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_policies
         WHERE schemaname = 'public' AND tablename = 'organization'
           AND policyname = 'location_setup_owner_organization_read'
    ) THEN
        CREATE POLICY location_setup_owner_organization_read
            ON public.organization FOR SELECT TO kokonut_location_setup_owner USING (true);
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class relation
        JOIN pg_catalog.pg_namespace namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public' AND relation.relname = 'location'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_policies
         WHERE schemaname = 'public' AND tablename = 'location'
           AND policyname = 'location_setup_owner_location_read'
    ) THEN
        CREATE POLICY location_setup_owner_location_read
            ON public.location FOR SELECT TO kokonut_location_setup_owner USING (true);
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class relation
        JOIN pg_catalog.pg_namespace namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public' AND relation.relname = 'farm'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_policies
         WHERE schemaname = 'public' AND tablename = 'farm'
           AND policyname = 'location_setup_owner_farm_read'
    ) THEN
        CREATE POLICY location_setup_owner_farm_read
            ON public.farm FOR SELECT TO kokonut_location_setup_owner USING (true);
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class relation
        JOIN pg_catalog.pg_namespace namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public' AND relation.relname = 'operator_organization_membership'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_policies
         WHERE schemaname = 'public' AND tablename = 'operator_organization_membership'
           AND policyname = 'location_setup_owner_membership_read'
    ) THEN
        CREATE POLICY location_setup_owner_membership_read
            ON public.operator_organization_membership
            FOR SELECT TO kokonut_location_setup_owner USING (true);
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class relation
        JOIN pg_catalog.pg_namespace namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public' AND relation.relname = 'organization_member'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_policies
         WHERE schemaname = 'public' AND tablename = 'organization_member'
           AND policyname = 'location_setup_owner_organization_member_read'
    ) THEN
        CREATE POLICY location_setup_owner_organization_member_read
            ON public.organization_member FOR SELECT TO kokonut_location_setup_owner USING (true);
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class relation
        JOIN pg_catalog.pg_namespace namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public' AND relation.relname = 'location_tenant_owner_verification'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_policies
         WHERE schemaname = 'public' AND tablename = 'location_tenant_owner_verification'
           AND policyname = 'location_setup_owner_tenant_owner_read'
    ) THEN
        CREATE POLICY location_setup_owner_tenant_owner_read
            ON public.location_tenant_owner_verification FOR SELECT TO kokonut_location_setup_owner USING (true);
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_class relation
        JOIN pg_catalog.pg_namespace namespace ON namespace.oid = relation.relnamespace
        WHERE namespace.nspname = 'public' AND relation.relname = 'operator_scope_grant'
          AND relation.relrowsecurity
    ) AND NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_policies
         WHERE schemaname = 'public' AND tablename = 'operator_scope_grant'
           AND policyname = 'location_setup_owner_scope_read'
    ) THEN
        CREATE POLICY location_setup_owner_scope_read
            ON public.operator_scope_grant FOR SELECT TO kokonut_location_setup_owner USING (true);
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_setup_organizations(
    requested_operator_id UUID
)
RETURNS TABLE(id UUID, org_key TEXT, name TEXT)
LANGUAGE plpgsql
SECURITY DEFINER
    SET search_path = pg_catalog
AS $$
BEGIN
    IF NOT kokonut_security.location_setup_capability_allows(requested_operator_id) THEN
        RAISE EXCEPTION 'location setup capability is required' USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT organization.id, organization.org_key::TEXT, organization.name::TEXT
      FROM public.organization
     WHERE organization.status = 'active'
     ORDER BY organization.name, organization.org_key
     LIMIT 200;
END;
$$;
ALTER FUNCTION kokonut_security.list_location_setup_organizations(UUID)
    OWNER TO kokonut_location_setup_owner;
REVOKE ALL ON FUNCTION kokonut_security.list_location_setup_organizations(UUID) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.list_location_setup_organizations(UUID)
    TO kokonut_operator_auth;

CREATE OR REPLACE FUNCTION kokonut_security.create_operator_location_setup(
    requested_operator_id UUID,
    requested_organization_id UUID,
    requested_location JSONB,
    requested_farm JSONB,
    requested_owner_decision_reference TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
    SET search_path = pg_catalog
AS $$
DECLARE
    organization_name TEXT;
    location_name TEXT;
    location_slug TEXT;
    location_description TEXT;
    location_country TEXT;
    location_region TEXT;
    location_sub_region TEXT;
    location_timezone TEXT;
    location_latitude DOUBLE PRECISION;
    location_longitude DOUBLE PRECISION;
    location_geojson JSONB;
    location_boundary public.geometry(POLYGON, 4326);
    location_center public.geometry(POINT, 4326);
    existing_location_id UUID;
    existing_location_organization_id UUID;
    existing_owner_organization_id UUID;
    existing_owned_membership_id UUID;
    existing_farm_id UUID;
    existing_farm_location_id UUID;
    farm_name TEXT;
    farm_slug TEXT;
    farm_description TEXT;
    farm_area NUMERIC(12, 4);
    farm_kind TEXT;
    farm_area_unit TEXT;
    farm_geojson JSONB;
    farm_boundary public.geometry(POLYGON, 4326);
    farm_center public.geometry(POINT, 4326);
    created_location_id UUID;
    created_farm_id UUID;
    location_created BOOLEAN := FALSE;
    farm_created BOOLEAN := FALSE;
    granted_scopes JSONB;
    scope_row RECORD;
BEGIN
    IF NOT kokonut_security.location_setup_capability_allows(requested_operator_id) THEN
        RAISE EXCEPTION 'location setup capability is required' USING ERRCODE = '42501';
    END IF;
    IF requested_location IS NULL OR jsonb_typeof(requested_location) <> 'object'
       OR requested_farm IS NULL OR jsonb_typeof(requested_farm) <> 'object' THEN
        RAISE EXCEPTION 'location and farm details are required' USING ERRCODE = '22023';
    END IF;
    IF requested_owner_decision_reference IS NULL
       OR length(btrim(requested_owner_decision_reference)) NOT BETWEEN 3 AND 2000 THEN
        RAISE EXCEPTION 'owner decision reference is required' USING ERRCODE = '22023';
    END IF;

    SELECT organization.name INTO organization_name
      FROM public.organization
     WHERE organization.id = requested_organization_id
       AND organization.status = 'active';
    IF organization_name IS NULL THEN
        RAISE EXCEPTION 'active tenant organization was not found' USING ERRCODE = '22023';
    END IF;

    location_name := btrim(requested_location->>'name');
    location_slug := lower(btrim(requested_location->>'slug'));
    location_description := NULLIF(btrim(requested_location->>'description'), '');
    location_country := btrim(requested_location->>'country');
    location_region := btrim(requested_location->>'region');
    location_sub_region := NULLIF(btrim(requested_location->>'sub_region'), '');
    location_timezone := btrim(requested_location->>'timezone');
    IF location_name IS NULL OR length(location_name) NOT BETWEEN 1 AND 255
       OR location_slug IS NULL OR location_slug !~ '^[a-z0-9]+(-[a-z0-9]+)*$'
       OR length(location_slug) > 255
       OR location_country IS NULL OR length(location_country) NOT BETWEEN 1 AND 100
       OR location_region IS NULL OR length(location_region) NOT BETWEEN 1 AND 255
       OR location_timezone IS NULL OR length(location_timezone) NOT BETWEEN 1 AND 50 THEN
        RAISE EXCEPTION 'location name, slug, country, region, and timezone are required' USING ERRCODE = '22023';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_timezone_names timezone_name
         WHERE timezone_name.name = location_timezone
    ) THEN
        RAISE EXCEPTION 'location timezone must be a valid IANA time zone' USING ERRCODE = '22023';
    END IF;
    IF jsonb_typeof(requested_location->'latitude') IS DISTINCT FROM 'number'
       OR jsonb_typeof(requested_location->'longitude') IS DISTINCT FROM 'number' THEN
        RAISE EXCEPTION 'location latitude and longitude are required' USING ERRCODE = '22023';
    END IF;
    location_latitude := (requested_location->>'latitude')::DOUBLE PRECISION;
    location_longitude := (requested_location->>'longitude')::DOUBLE PRECISION;
    IF location_latitude NOT BETWEEN -90 AND 90
       OR location_longitude NOT BETWEEN -180 AND 180 THEN
        RAISE EXCEPTION 'location coordinates are outside valid ranges' USING ERRCODE = '22023';
    END IF;
    location_geojson := requested_location->'boundary_geojson';
    IF location_geojson IS NULL OR jsonb_typeof(location_geojson) <> 'object'
       OR location_geojson->>'type' IS DISTINCT FROM 'Polygon'
       OR jsonb_typeof(location_geojson->'coordinates') IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'location boundary must be Polygon GeoJSON' USING ERRCODE = '22023';
    END IF;
    location_boundary := public.ST_SetSRID(
        public.ST_GeomFromGeoJSON(location_geojson::TEXT), 4326
    )::public.geometry(POLYGON, 4326);
    IF public.ST_IsEmpty(location_boundary)
       OR NOT public.ST_IsValid(location_boundary) THEN
        RAISE EXCEPTION 'location boundary must be a valid Polygon' USING ERRCODE = '22023';
    END IF;
    location_center := public.ST_SetSRID(
        public.ST_MakePoint(location_longitude, location_latitude), 4326
    );
    IF NOT public.ST_Covers(location_boundary, location_center) THEN
        RAISE EXCEPTION 'location coordinates must fall inside the location boundary' USING ERRCODE = '22023';
    END IF;

    farm_name := btrim(requested_farm->>'name');
    farm_slug := lower(btrim(requested_farm->>'slug'));
    farm_description := NULLIF(btrim(requested_farm->>'description'), '');
    farm_kind := lower(btrim(requested_farm->>'farm_type'));
    farm_area_unit := lower(btrim(requested_farm->>'area_unit'));
    IF farm_name IS NULL OR length(farm_name) NOT BETWEEN 1 AND 255
       OR farm_slug IS NULL OR farm_slug !~ '^[a-z0-9]+(-[a-z0-9]+)*$'
       OR length(farm_slug) > 255
       OR farm_kind IS NULL
       OR farm_kind NOT IN ('conventional', 'organic', 'syntropic', 'agroforestry', 'hybrid')
       OR farm_area_unit IS NULL
       OR farm_area_unit NOT IN ('hectares', 'acres', 'square_meters')
       OR jsonb_typeof(requested_farm->'total_area') IS DISTINCT FROM 'number' THEN
        RAISE EXCEPTION 'farm name, slug, type, area, and area unit are required' USING ERRCODE = '22023';
    END IF;
    farm_area := (requested_farm->>'total_area')::NUMERIC(12, 4);
    IF farm_area <= 0 THEN
        RAISE EXCEPTION 'farm area must be greater than zero' USING ERRCODE = '22023';
    END IF;
    farm_geojson := requested_farm->'boundary_geojson';
    IF farm_geojson IS NULL OR jsonb_typeof(farm_geojson) <> 'object'
       OR farm_geojson->>'type' IS DISTINCT FROM 'Polygon'
       OR jsonb_typeof(farm_geojson->'coordinates') IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'farm boundary must be Polygon GeoJSON' USING ERRCODE = '22023';
    END IF;
    farm_boundary := public.ST_SetSRID(
        public.ST_GeomFromGeoJSON(farm_geojson::TEXT), 4326
    )::public.geometry(POLYGON, 4326);
    IF public.ST_IsEmpty(farm_boundary)
       OR NOT public.ST_IsValid(farm_boundary)
       OR NOT public.ST_Covers(location_boundary, farm_boundary) THEN
        RAISE EXCEPTION 'farm boundary must be valid and fit inside the location boundary' USING ERRCODE = '22023';
    END IF;
    farm_center := public.ST_PointOnSurface(farm_boundary);

    SELECT location.id, location.organization_id
      INTO existing_location_id, existing_location_organization_id
      FROM public.location
     WHERE location.slug = location_slug
     FOR UPDATE;

    IF existing_location_id IS NULL THEN
        INSERT INTO public.location (
            name, slug, description, boundary, center, country, region, sub_region,
            timezone, latitude, longitude, status, organization_id, created_by, updated_by
        ) VALUES (
            location_name, location_slug, location_description, location_boundary,
            location_center, location_country, location_region, location_sub_region,
            location_timezone, location_latitude, location_longitude, 'active',
            requested_organization_id, requested_operator_id, requested_operator_id
        ) RETURNING id INTO created_location_id;
        location_created := TRUE;
    ELSE
        IF existing_location_organization_id IS NOT NULL
           AND existing_location_organization_id <> requested_organization_id THEN
            RAISE EXCEPTION 'location belongs to another tenant; use the audited tenant-transfer workflow'
                USING ERRCODE = '55000';
        END IF;
        SELECT owner.organization_id INTO existing_owner_organization_id
          FROM public.location_tenant_owner_verification owner
         WHERE owner.location_id = existing_location_id AND owner.revoked_at IS NULL;
        IF existing_owner_organization_id IS NOT NULL
           AND existing_owner_organization_id <> requested_organization_id THEN
            RAISE EXCEPTION 'location has a different verified tenant; use the audited tenant-transfer workflow'
                USING ERRCODE = '55000';
        END IF;
    IF EXISTS (
            SELECT 1 FROM public.organization_member member
             WHERE member.location_id = existing_location_id
               AND member.membership_type = 'owned'
               AND member.status = 'active'
               AND member.organization_id <> requested_organization_id
        ) THEN
            RAISE EXCEPTION 'location has another active owner relationship; resolve it before setup'
                USING ERRCODE = '55000';
        END IF;
        UPDATE public.location
           SET name = location_name,
               description = location_description,
               boundary = location_boundary,
               center = location_center,
               country = location_country,
               region = location_region,
               sub_region = location_sub_region,
               timezone = location_timezone,
               latitude = location_latitude,
               longitude = location_longitude,
               status = 'active',
               organization_id = requested_organization_id,
               updated_by = requested_operator_id
         WHERE id = existing_location_id
        RETURNING id INTO created_location_id;
    END IF;

    SELECT farm.id, farm.location_id
      INTO existing_farm_id, existing_farm_location_id
      FROM public.farm
     WHERE farm.slug = farm_slug
     FOR UPDATE;
    IF existing_farm_id IS NOT NULL AND existing_farm_location_id <> created_location_id THEN
        RAISE EXCEPTION 'farm slug already belongs to another location' USING ERRCODE = '23505';
    ELSIF existing_farm_id IS NULL THEN
        INSERT INTO public.farm (
            location_id, name, slug, description, farm_type, total_area, area_unit,
            boundary, center, status, created_by, updated_by
        ) VALUES (
            created_location_id, farm_name, farm_slug, farm_description, farm_kind,
            farm_area, farm_area_unit, farm_boundary, farm_center, 'active',
            requested_operator_id, requested_operator_id
        ) RETURNING id INTO created_farm_id;
        farm_created := TRUE;
    ELSE
        UPDATE public.farm
           SET name = farm_name,
               description = farm_description,
               farm_type = farm_kind,
               total_area = farm_area,
               area_unit = farm_area_unit,
               boundary = farm_boundary,
               center = farm_center,
               status = 'active',
               updated_by = requested_operator_id
         WHERE id = existing_farm_id
        RETURNING id INTO created_farm_id;
    END IF;

    SELECT owner.organization_id INTO existing_owner_organization_id
      FROM public.location_tenant_owner_verification owner
     WHERE owner.location_id = created_location_id AND owner.revoked_at IS NULL;
    IF existing_owner_organization_id IS NULL THEN
        INSERT INTO public.location_tenant_owner_verification (
            location_id, organization_id, decision_reference, confirmed_by
        ) VALUES (
            created_location_id,
            requested_organization_id,
            btrim(requested_owner_decision_reference),
            'operator:' || requested_operator_id::TEXT
        );
    ELSIF existing_owner_organization_id <> requested_organization_id THEN
        RAISE EXCEPTION 'location has a different verified tenant; use the audited tenant-transfer workflow'
            USING ERRCODE = '55000';
    END IF;

    IF EXISTS (
        SELECT 1 FROM public.organization_member member
         WHERE member.location_id = created_location_id
           AND member.organization_id = requested_organization_id
           AND member.membership_type = 'owned'
           AND member.status = 'active'
           AND member.farm_id IS DISTINCT FROM created_farm_id
    ) THEN
        RAISE EXCEPTION 'location already has a different active owned farm relationship; resolve it before setup'
            USING ERRCODE = '55000';
    END IF;
    SELECT member.id INTO existing_owned_membership_id
      FROM public.organization_member member
     WHERE member.location_id = created_location_id
       AND member.organization_id = requested_organization_id
       AND member.farm_id = created_farm_id
       AND member.membership_type = 'owned'
       AND member.status = 'active'
     ORDER BY member.created_at, member.id
     LIMIT 1;
    IF existing_owned_membership_id IS NULL THEN
        INSERT INTO public.organization_member (
            organization_id, location_id, farm_id, membership_type, role, status, metadata
        ) VALUES (
            requested_organization_id, created_location_id, created_farm_id,
            'owned', 'primary', 'active',
            pg_catalog.jsonb_build_object(
                'ownership_reconciliation', 'owner_confirmed',
                'setup_source', 'control_plane'
            )
        );
    END IF;
    INSERT INTO public.operator_organization_membership (
        operator_id, organization_id, membership_role, granted_by
    ) VALUES (
        requested_operator_id, requested_organization_id, 'operator',
        'location_setup:' || requested_operator_id::TEXT
    ) ON CONFLICT (operator_id, organization_id) WHERE revoked_at IS NULL DO NOTHING;

    FOR scope_row IN
        SELECT scope.resource, scope.action
          FROM (VALUES
            ('location', 'read'),
            ('farm_activity', 'read'),
            ('farm_activity', 'read_detail'),
            ('farm_activity', 'create_draft'),
            ('farm_activity', 'edit_draft')
          ) AS scope(resource, action)
    LOOP
        INSERT INTO public.operator_scope_grant (
            operator_id, resource, action, location_id, granted_by, organization_id
        ) VALUES (
            requested_operator_id, scope_row.resource, scope_row.action,
            created_location_id, 'location_setup:' || requested_operator_id::TEXT,
            requested_organization_id
        ) ON CONFLICT (operator_id, resource, action, location_id)
            WHERE revoked_at IS NULL DO NOTHING;
    END LOOP;

    INSERT INTO kokonut_security.location_setup_audit (
        operator_id, organization_id, location_id, farm_id, owner_decision_reference
    ) VALUES (
        requested_operator_id, requested_organization_id, created_location_id,
        created_farm_id, btrim(requested_owner_decision_reference)
    );

    SELECT pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object(
               'resource', scope.resource,
               'action', scope.action,
               'location_id', created_location_id
           ) ORDER BY scope.resource, scope.action)
      INTO granted_scopes
      FROM (VALUES
        ('location', 'read'),
        ('farm_activity', 'read'),
        ('farm_activity', 'read_detail'),
        ('farm_activity', 'create_draft'),
        ('farm_activity', 'edit_draft')
      ) AS scope(resource, action);

    RETURN pg_catalog.jsonb_build_object(
        'location_id', created_location_id,
        'location_created', location_created,
        'location_name', location_name,
        'farm_id', created_farm_id,
        'farm_created', farm_created,
        'farm_name', farm_name,
        'organization_id', requested_organization_id,
        'organization_name', organization_name,
        'starter_scopes', granted_scopes
    );
EXCEPTION
    WHEN unique_violation THEN
        RAISE EXCEPTION 'location slug, farm slug, or owner decision reference already exists'
            USING ERRCODE = '23505';
END;
$$;
ALTER FUNCTION kokonut_security.create_operator_location_setup(UUID, UUID, JSONB, JSONB, TEXT)
    OWNER TO kokonut_location_setup_owner;
REVOKE ALL ON FUNCTION kokonut_security.create_operator_location_setup(UUID, UUID, JSONB, JSONB, TEXT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.create_operator_location_setup(UUID, UUID, JSONB, JSONB, TEXT)
    TO kokonut_operator_auth;

COMMENT ON FUNCTION kokonut_security.create_operator_location_setup(UUID, UUID, JSONB, JSONB, TEXT) IS
    'Creates or completes one tenant-qualified location and farm from an authenticated Control Plane setup flow; preserves baseline/history fields, confirms tenant assignment from the submitted decision reference, and gives only location-read plus draft-only field activity scopes.';
COMMENT ON TABLE kokonut_security.location_setup_audit IS
    'Append-only evidence for Control Plane location/farm setup, including the explicit tenant-owner decision reference.';

REVOKE CREATE ON SCHEMA kokonut_security FROM kokonut_location_setup_owner;

COMMIT;
