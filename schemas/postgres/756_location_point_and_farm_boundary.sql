-- Locations use a representative point; parcel geometry belongs to farms.
-- Keep optional location-area context independent from farm-boundary validation.
BEGIN;

CREATE OR REPLACE FUNCTION kokonut_security.create_operator_location_setup(
    requested_session_token_hash TEXT,
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
    requested_operator_id UUID;
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
    IF NOT kokonut_security.location_setup_capability_allows(requested_session_token_hash) THEN
        RAISE EXCEPTION 'location setup capability is required' USING ERRCODE = '42501';
    END IF;
    requested_operator_id := kokonut_security.resolve_clickhouse_outbox_operator_session(
        requested_session_token_hash
    );
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
    IF location_geojson IS NOT NULL AND location_geojson <> 'null'::JSONB THEN
        IF jsonb_typeof(location_geojson) <> 'object'
           OR location_geojson->>'type' IS DISTINCT FROM 'Polygon'
           OR jsonb_typeof(location_geojson->'coordinates') IS DISTINCT FROM 'array' THEN
            RAISE EXCEPTION 'optional location area must be Polygon GeoJSON' USING ERRCODE = '22023';
        END IF;
        location_boundary := public.ST_SetSRID(
            public.ST_GeomFromGeoJSON(location_geojson::TEXT), 4326
        )::public.geometry(POLYGON, 4326);
        IF public.ST_IsEmpty(location_boundary)
           OR NOT public.ST_IsValid(location_boundary) THEN
            RAISE EXCEPTION 'optional location area must be a valid Polygon' USING ERRCODE = '22023';
        END IF;
    END IF;
    location_center := public.ST_SetSRID(
        public.ST_MakePoint(location_longitude, location_latitude), 4326
    );

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
       OR NOT public.ST_IsValid(farm_boundary) THEN
        RAISE EXCEPTION 'farm boundary must be a valid Polygon' USING ERRCODE = '22023';
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
               boundary = COALESCE(location_boundary, boundary),
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

CREATE OR REPLACE FUNCTION kokonut_security.create_operator_farm_for_location(
    requested_session_token_hash TEXT,
    requested_organization_id UUID,
    requested_location_id UUID,
    requested_farm JSONB,
    requested_owner_decision_reference TEXT
)
RETURNS JSONB
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    requested_operator_id UUID;
    organization_name TEXT;
    location_name TEXT;
    location_boundary public.geometry(POLYGON, 4326);
    farm_name TEXT;
    farm_slug TEXT;
    farm_description TEXT;
    farm_area NUMERIC(12, 4);
    farm_kind TEXT;
    farm_area_unit TEXT;
    farm_geojson JSONB;
    farm_boundary public.geometry(POLYGON, 4326);
    farm_center public.geometry(POINT, 4326);
    created_farm_id UUID;
    granted_scopes JSONB;
    scope_row RECORD;
BEGIN
    IF NOT kokonut_security.location_setup_capability_allows(requested_session_token_hash) THEN
        RAISE EXCEPTION 'location setup capability is required' USING ERRCODE = '42501';
    END IF;
    requested_operator_id := kokonut_security.resolve_clickhouse_outbox_operator_session(
        requested_session_token_hash
    );
    IF requested_farm IS NULL OR jsonb_typeof(requested_farm) <> 'object' THEN
        RAISE EXCEPTION 'farm details are required' USING ERRCODE = '22023';
    END IF;
    IF requested_owner_decision_reference IS NULL
       OR length(btrim(requested_owner_decision_reference)) NOT BETWEEN 3 AND 2000 THEN
        RAISE EXCEPTION 'owner decision reference is required' USING ERRCODE = '22023';
    END IF;

    SELECT organization.name INTO organization_name
      FROM public.organization AS organization
     WHERE organization.id = requested_organization_id
       AND organization.status = 'active';
    IF organization_name IS NULL THEN
        RAISE EXCEPTION 'active tenant organization was not found' USING ERRCODE = '22023';
    END IF;

    SELECT location.name, location.boundary
      INTO location_name, location_boundary
      FROM public.location AS location
     WHERE location.id = requested_location_id
       AND location.organization_id = requested_organization_id
       AND location.status = 'active'
       AND EXISTS (
            SELECT 1
              FROM public.location_tenant_owner_verification AS owner
             WHERE owner.location_id = location.id
               AND owner.organization_id = requested_organization_id
               AND owner.revoked_at IS NULL
       )
       AND EXISTS (
            SELECT 1
              FROM public.organization_member AS membership
              JOIN public.farm AS owned_farm
                ON owned_farm.id = membership.farm_id
               AND owned_farm.location_id = location.id
             WHERE membership.location_id = location.id
               AND membership.organization_id = requested_organization_id
               AND membership.membership_type = 'owned'
               AND membership.status = 'active'
       )
       AND NOT EXISTS (
            SELECT 1
              FROM public.organization_member AS other_owner
             WHERE other_owner.location_id = location.id
               AND other_owner.membership_type = 'owned'
               AND other_owner.status = 'active'
               AND other_owner.organization_id <> requested_organization_id
       )
     FOR SHARE;
    IF location_name IS NULL THEN
        RAISE EXCEPTION 'selected location is unavailable to this tenant or needs an ownership review'
            USING ERRCODE = '55000';
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
    IF public.ST_IsEmpty(farm_boundary) OR NOT public.ST_IsValid(farm_boundary) THEN
        RAISE EXCEPTION 'farm boundary must be a valid Polygon' USING ERRCODE = '22023';
    END IF;
    -- Location is an administrative/geographic grouping. The farm polygon
    -- describes the parcel and need not be clipped to the parent location area.

    farm_center := public.ST_PointOnSurface(farm_boundary);

    INSERT INTO public.farm (
        location_id, name, slug, description, farm_type, total_area, area_unit,
        boundary, center, status, created_by, updated_by
    ) VALUES (
        requested_location_id, farm_name, farm_slug, farm_description, farm_kind,
        farm_area, farm_area_unit, farm_boundary, farm_center, 'active',
        requested_operator_id, requested_operator_id
    ) RETURNING id INTO created_farm_id;

    -- Tenant ownership is recorded once for the location and its primary
    -- farm. Additional farms inherit the tenant through farm.location_id;
    -- do not duplicate the active owned membership for this location.
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
            requested_location_id, 'location_setup:' || requested_operator_id::TEXT,
            requested_organization_id
        ) ON CONFLICT (operator_id, resource, action, location_id)
            WHERE revoked_at IS NULL DO NOTHING;
    END LOOP;

    INSERT INTO kokonut_security.location_setup_audit (
        operator_id, organization_id, location_id, farm_id, owner_decision_reference
    ) VALUES (
        requested_operator_id, requested_organization_id, requested_location_id,
        created_farm_id, btrim(requested_owner_decision_reference)
    );

    SELECT pg_catalog.jsonb_agg(pg_catalog.jsonb_build_object(
               'resource', scope.resource,
               'action', scope.action,
               'location_id', requested_location_id
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
        'location_id', requested_location_id,
        'location_created', FALSE,
        'location_name', location_name,
        'farm_id', created_farm_id,
        'farm_created', TRUE,
        'farm_name', farm_name,
        'organization_id', requested_organization_id,
        'organization_name', organization_name,
        'starter_scopes', granted_scopes
    );
EXCEPTION
    WHEN unique_violation THEN
        RAISE EXCEPTION 'farm slug or owner decision reference already exists'
            USING ERRCODE = '23505';
END;
$$;

ALTER FUNCTION kokonut_security.create_operator_location_setup(TEXT, UUID, JSONB, JSONB, TEXT)
    OWNER TO kokonut_location_setup_owner;
REVOKE ALL ON FUNCTION kokonut_security.create_operator_location_setup(TEXT, UUID, JSONB, JSONB, TEXT) FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_operator_auth') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.create_operator_location_setup(TEXT, UUID, JSONB, JSONB, TEXT)
            TO kokonut_operator_auth;
        GRANT EXECUTE ON FUNCTION kokonut_security.create_operator_farm_for_location(TEXT, UUID, UUID, JSONB, TEXT)
            TO kokonut_operator_auth;
    END IF;
END;
$$;
ALTER FUNCTION kokonut_security.create_operator_farm_for_location(TEXT, UUID, UUID, JSONB, TEXT)
    OWNER TO kokonut_location_setup_owner;
REVOKE ALL ON FUNCTION kokonut_security.create_operator_farm_for_location(TEXT, UUID, UUID, JSONB, TEXT) FROM PUBLIC;
COMMENT ON FUNCTION kokonut_security.create_operator_location_setup(TEXT, UUID, JSONB, JSONB, TEXT) IS
    'Creates a tenant-qualified location and farm; location point is required, location area is optional, farm parcel boundary is required, and tenant assignment is audited.';
COMMENT ON FUNCTION kokonut_security.create_operator_farm_for_location(TEXT, UUID, UUID, JSONB, TEXT) IS
    'Adds a farm under an owned location; farm parcel boundary is validated independently from optional location area.';

COMMIT;
