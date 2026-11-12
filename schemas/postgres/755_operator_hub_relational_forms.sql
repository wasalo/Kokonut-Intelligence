-- Give the Hub bounded labels for authorized locations, allow a tenant to add
-- another farm beneath an already-owned location, and enforce activity links.

BEGIN;

-- Keep the location-label projection inside the existing isolated scope-read
-- function owner. The API login still receives no direct tenant-table reads.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_catalog.pg_roles
         WHERE rolname = 'kokonut_operator_scope_read_owner'
    ) THEN
        RAISE EXCEPTION 'operator scope read owner is required before Hub location choices';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_catalog.pg_proc AS procedure
         WHERE procedure.proowner = (
             SELECT oid FROM pg_catalog.pg_roles
              WHERE rolname = 'kokonut_operator_scope_read_owner'
         )
           AND procedure.oid IS DISTINCT FROM pg_catalog.to_regprocedure(
               'kokonut_security.operator_scope_grant_read_allows(uuid,text,text,uuid)'
           )
           AND procedure.oid IS DISTINCT FROM pg_catalog.to_regprocedure(
               'kokonut_security.operator_scope_grant_read_scopes(uuid)'
           )
           AND procedure.oid IS DISTINCT FROM pg_catalog.to_regprocedure(
               'kokonut_security.operator_scope_grant_read_location_options(uuid)'
           )
    ) THEN
        RAISE EXCEPTION 'operator scope read owner has an unexpected function';
    END IF;
END;
$$;

GRANT SELECT (id, name, country, region, status)
    ON TABLE public.location TO kokonut_operator_scope_read_owner;

CREATE OR REPLACE FUNCTION kokonut_security.operator_scope_grant_read_location_options(
    requested_operator_id UUID
)
RETURNS TABLE(id UUID, name TEXT, country TEXT, region TEXT)
LANGUAGE SQL
STABLE
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
    SELECT location.id, location.name::TEXT, location.country::TEXT, location.region::TEXT
      FROM public.location AS location
     WHERE location.status = 'active'
       AND EXISTS (
            SELECT 1
              FROM public.operator_scope_grant AS grant_row
             WHERE grant_row.operator_id = requested_operator_id
               AND grant_row.location_id = location.id
               AND grant_row.revoked_at IS NULL
               AND kokonut_security.operator_scope_grant_read_allows(
                       grant_row.operator_id,
                       grant_row.resource,
                       grant_row.action,
                       grant_row.location_id
                   )
       )
     ORDER BY location.name, location.region, location.country, location.id
     LIMIT 200
$$;
ALTER FUNCTION kokonut_security.operator_scope_grant_read_location_options(UUID)
    OWNER TO kokonut_operator_scope_read_owner;
REVOKE ALL ON FUNCTION kokonut_security.operator_scope_grant_read_location_options(UUID)
    FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_operator_auth') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.operator_scope_grant_read_location_options(UUID)
            TO kokonut_operator_auth;
    END IF;
END;
$$;

-- The setup function owner may look up only the parent boundary and bounded
-- labels needed to add a farm without changing the existing location.
GRANT SELECT (id, organization_id, name, slug, country, region, status, boundary)
    ON TABLE public.location TO kokonut_location_setup_owner;
GRANT SELECT (id, location_id, slug, name, status)
    ON TABLE public.farm TO kokonut_location_setup_owner;

CREATE OR REPLACE FUNCTION kokonut_security.list_location_setup_locations(
    requested_session_token_hash TEXT,
    requested_organization_id UUID
)
RETURNS TABLE(
    id UUID,
    name TEXT,
    slug TEXT,
    country TEXT,
    region TEXT,
    active_farm_count BIGINT
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
BEGIN
    IF NOT kokonut_security.location_setup_capability_allows(requested_session_token_hash) THEN
        RAISE EXCEPTION 'location setup capability is required' USING ERRCODE = '42501';
    END IF;
    RETURN QUERY
    SELECT location.id, location.name::TEXT, location.slug::TEXT,
           location.country::TEXT, location.region::TEXT,
           count(DISTINCT farm.id) FILTER (WHERE farm.status = 'active')
      FROM public.location AS location
      JOIN public.organization AS organization
        ON organization.id = location.organization_id
       AND organization.status = 'active'
      JOIN public.location_tenant_owner_verification AS owner
        ON owner.location_id = location.id
       AND owner.organization_id = requested_organization_id
       AND owner.revoked_at IS NULL
      JOIN public.organization_member AS membership
        ON membership.location_id = location.id
       AND membership.organization_id = requested_organization_id
       AND membership.membership_type = 'owned'
       AND membership.status = 'active'
       AND membership.farm_id IS NOT NULL
      JOIN public.farm AS owned_farm
        ON owned_farm.id = membership.farm_id
       AND owned_farm.location_id = location.id
       AND owned_farm.status = 'active'
      LEFT JOIN public.farm AS farm
        ON farm.location_id = location.id
     WHERE location.organization_id = requested_organization_id
       AND location.status = 'active'
     GROUP BY location.id, location.name, location.slug, location.country, location.region
     ORDER BY location.name, location.region, location.id
     LIMIT 200;
END;
$$;
ALTER FUNCTION kokonut_security.list_location_setup_locations(TEXT, UUID)
    OWNER TO kokonut_location_setup_owner;
REVOKE ALL ON FUNCTION kokonut_security.list_location_setup_locations(TEXT, UUID)
    FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_operator_auth') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.list_location_setup_locations(TEXT, UUID)
            TO kokonut_operator_auth;
    END IF;
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
    IF location_boundary IS NULL OR NOT public.ST_Covers(location_boundary, farm_boundary) THEN
        RAISE EXCEPTION 'farm boundary must fit within the selected location boundary' USING ERRCODE = '22023';
    END IF;
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
ALTER FUNCTION kokonut_security.create_operator_farm_for_location(TEXT, UUID, UUID, JSONB, TEXT)
    OWNER TO kokonut_location_setup_owner;
REVOKE ALL ON FUNCTION kokonut_security.create_operator_farm_for_location(TEXT, UUID, UUID, JSONB, TEXT)
    FROM PUBLIC;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_operator_auth') THEN
        GRANT EXECUTE ON FUNCTION kokonut_security.create_operator_farm_for_location(TEXT, UUID, UUID, JSONB, TEXT)
            TO kokonut_operator_auth;
    END IF;
END;
$$;

-- Activity rows may link a farm, plot, cycle and task only when every chosen
-- relation resolves to the same location and is mutually consistent.
CREATE OR REPLACE FUNCTION public.validate_farm_activity_scope()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    expected_location UUID;
    plot_farm_id UUID;
    cycle_plot_id UUID;
    cycle_farm_id UUID;
    task_farm_id UUID;
    task_plot_id UUID;
    task_cycle_id UUID;
    task_location_id UUID;
BEGIN
    IF NEW.farm_id IS NOT NULL THEN
        SELECT farm.location_id INTO expected_location
          FROM public.farm AS farm
         WHERE farm.id = NEW.farm_id;
        IF expected_location IS NULL OR expected_location <> NEW.location_id THEN
            RAISE EXCEPTION 'farm activity location does not match its farm';
        END IF;
    END IF;

    IF NEW.plot_id IS NOT NULL THEN
        SELECT plot.farm_id, farm.location_id
          INTO plot_farm_id, expected_location
          FROM public.plot AS plot
          JOIN public.farm AS farm ON farm.id = plot.farm_id
         WHERE plot.id = NEW.plot_id;
        IF plot_farm_id IS NULL OR expected_location IS DISTINCT FROM NEW.location_id THEN
            RAISE EXCEPTION 'farm activity location does not match its plot';
        END IF;
        IF NEW.farm_id IS NOT NULL AND plot_farm_id <> NEW.farm_id THEN
            RAISE EXCEPTION 'farm activity farm does not match its plot';
        END IF;
    END IF;

    IF NEW.crop_cycle_id IS NOT NULL THEN
        SELECT cycle.plot_id, plot.farm_id, farm.location_id
          INTO cycle_plot_id, cycle_farm_id, expected_location
          FROM public.crop_cycle AS cycle
          JOIN public.plot AS plot ON plot.id = cycle.plot_id
          JOIN public.farm AS farm ON farm.id = plot.farm_id
         WHERE cycle.id = NEW.crop_cycle_id
           AND cycle.location_id = NEW.location_id;
        IF cycle_plot_id IS NULL OR expected_location IS DISTINCT FROM NEW.location_id THEN
            RAISE EXCEPTION 'farm activity location does not match its crop cycle';
        END IF;
        IF NEW.plot_id IS NOT NULL AND cycle_plot_id <> NEW.plot_id THEN
            RAISE EXCEPTION 'farm activity crop cycle does not match its plot';
        END IF;
        IF NEW.farm_id IS NOT NULL AND cycle_farm_id <> NEW.farm_id THEN
            RAISE EXCEPTION 'farm activity crop cycle does not match its farm';
        END IF;
    END IF;

    IF NEW.farm_task_id IS NOT NULL THEN
        SELECT task.farm_id, task.plot_id, task.crop_cycle_id, task.location_id
          INTO task_farm_id, task_plot_id, task_cycle_id, task_location_id
          FROM public.farm_task AS task
         WHERE task.id = NEW.farm_task_id;
        IF task_location_id IS NULL OR task_location_id <> NEW.location_id THEN
            RAISE EXCEPTION 'farm activity location does not match its task';
        END IF;
        IF NEW.farm_id IS NOT NULL AND task_farm_id IS NOT NULL
           AND task_farm_id <> NEW.farm_id THEN
            RAISE EXCEPTION 'farm activity farm does not match its task';
        END IF;
        IF NEW.plot_id IS NOT NULL AND task_plot_id IS NOT NULL
           AND task_plot_id <> NEW.plot_id THEN
            RAISE EXCEPTION 'farm activity plot does not match its task';
        END IF;
        IF NEW.crop_cycle_id IS NOT NULL AND task_cycle_id IS NOT NULL
           AND task_cycle_id <> NEW.crop_cycle_id THEN
            RAISE EXCEPTION 'farm activity crop cycle does not match its task';
        END IF;
    END IF;

    RETURN NEW;
END;
$$;
DROP TRIGGER IF EXISTS trg_farm_activity_scope ON public.farm_activity;
CREATE TRIGGER trg_farm_activity_scope
    BEFORE INSERT OR UPDATE OF farm_id, farm_task_id, plot_id, crop_cycle_id, location_id
    ON public.farm_activity
    FOR EACH ROW
    EXECUTE FUNCTION public.validate_farm_activity_scope();

COMMENT ON FUNCTION kokonut_security.create_operator_farm_for_location(TEXT, UUID, UUID, JSONB, TEXT) IS
    'Adds a farm through the existing location-to-farm relation under a verified, already-owned location without modifying the location or duplicating its owner membership; applies the existing draft-only starter scopes and appends owner-decision evidence.';
COMMENT ON FUNCTION kokonut_security.operator_scope_grant_read_location_options(UUID) IS
    'Returns bounded human-readable labels only for active locations with at least one current tenant-valid operator grant.';

COMMIT;
