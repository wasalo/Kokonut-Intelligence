-- Extend signed cache invalidation to the existing sensor/harvest handlers.
-- The worker still receives no direct event or cache-table access.

BEGIN;

DO $$
BEGIN
    IF to_regprocedure(
        'kokonut_security.invalidate_worker_computation_cache(uuid,text)'
    ) IS NULL THEN
        RAISE EXCEPTION 'migration 415 signed cache function is required';
    END IF;
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_cache_invalidation_owner'
    ) OR NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_worker_execution'
    ) THEN
        RAISE EXCEPTION 'signed cache invalidation roles are required';
    END IF;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.invalidate_worker_computation_cache(
    requested_event_id UUID,
    requested_event_type TEXT
)
RETURNS INTEGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    worker_scope RECORD;
    source_event RECORD;
    target_computation_type TEXT;
    invalidation_count INTEGER;
BEGIN
    SELECT scope.tenant_id, scope.location_id, scope.actor_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope(
          'computation_cache', 'invalidate'
      ) AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'signed cache invalidation scope is required'
            USING ERRCODE = '42501';
    END IF;

    IF requested_event_id IS NULL THEN
        RAISE EXCEPTION 'event ID is required'
            USING ERRCODE = '42501';
    END IF;

    target_computation_type := CASE requested_event_type
        WHEN 'metric_computed' THEN 'analytics'
        WHEN 'crisp_scored' THEN 'crisp'
        WHEN 'sensor_reading' THEN 'metric'
        WHEN 'harvest_recorded' THEN 'metric'
        ELSE NULL
    END;
    IF target_computation_type IS NULL THEN
        RAISE EXCEPTION 'event type is not allowed for cache invalidation'
            USING ERRCODE = '42501';
    END IF;

    SELECT event.event_type, event.payload ->> 'location_id' AS location_id
      INTO source_event
      FROM public.platform_event AS event
     WHERE event.id = requested_event_id;
    IF NOT FOUND
       OR source_event.event_type IS DISTINCT FROM requested_event_type
       OR LOWER(source_event.location_id)
            IS DISTINCT FROM worker_scope.location_id::TEXT THEN
        RAISE EXCEPTION 'event does not match the signed cache invalidation scope'
            USING ERRCODE = '42501';
    END IF;

    UPDATE public.cache_entry AS cache
       SET is_valid = FALSE,
           invalidation_reason = requested_event_type || ':' || requested_event_type,
           invalidated_at = statement_timestamp()
     WHERE cache.is_valid IS TRUE
       AND cache.location_id = worker_scope.location_id
       AND cache.computation_type = target_computation_type;
    GET DIAGNOSTICS invalidation_count = ROW_COUNT;
    RETURN invalidation_count;
END;
$$;

ALTER FUNCTION kokonut_security.invalidate_worker_computation_cache(UUID, TEXT)
    OWNER TO kokonut_cache_invalidation_owner;
REVOKE ALL ON FUNCTION kokonut_security.invalidate_worker_computation_cache(
    UUID, TEXT
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION kokonut_security.invalidate_worker_computation_cache(
    UUID, TEXT
) TO kokonut_worker_execution;

COMMENT ON FUNCTION kokonut_security.invalidate_worker_computation_cache(UUID, TEXT) IS
    'Invalidates the allowlisted analytics, CRISP, or metric cache type for one matching event and signed worker location.';

INSERT INTO public.event_handler (
    handler_name, event_type, module_path, function_name, priority_order
) VALUES
    (
        'sensor_cache_invalidator', 'sensor_reading', 'services.cache.events',
        'handle_sensor_reading', 5
    ),
    (
        'harvest_cache_invalidator', 'harvest_recorded', 'services.cache.events',
        'handle_harvest_recorded', 5
    )
ON CONFLICT (handler_name) DO UPDATE
SET event_type = EXCLUDED.event_type,
    module_path = EXCLUDED.module_path,
    function_name = EXCLUDED.function_name,
    priority_order = EXCLUDED.priority_order,
    updated_at = statement_timestamp();

COMMIT;
