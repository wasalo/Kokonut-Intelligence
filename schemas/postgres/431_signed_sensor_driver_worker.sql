-- Isolate scheduled CSV sensor ingestion behind one signed location scope and
-- bounded SECURITY DEFINER operations. The legacy/manual sensor CLI remains
-- on its existing application identity until callers are separately moved.

BEGIN;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_sensor_ingestion_owner'
    ) THEN
        CREATE ROLE kokonut_sensor_ingestion_owner
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_sensor_ingestion_owner'
           AND (rolcanlogin OR rolsuper OR rolcreatedb OR rolcreaterole
                OR rolreplication OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'sensor ingestion function owner has unsafe role attributes';
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_roles WHERE rolname = 'kokonut_sensor_ingestion_login'
    ) THEN
        CREATE ROLE kokonut_sensor_ingestion_login
            NOLOGIN NOINHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE
            NOREPLICATION NOBYPASSRLS;
    ELSIF EXISTS (
        SELECT 1 FROM pg_roles
         WHERE rolname = 'kokonut_sensor_ingestion_login'
           AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication
                OR rolbypassrls OR rolinherit)
    ) THEN
        RAISE EXCEPTION 'sensor ingestion login has unsafe role attributes';
    END IF;

    IF EXISTS (
        SELECT 1
          FROM pg_auth_members AS membership
          JOIN pg_roles AS granted_role ON granted_role.oid = membership.roleid
          JOIN pg_roles AS member_role ON member_role.oid = membership.member
         WHERE granted_role.rolname = 'kokonut_sensor_ingestion_owner'
            OR member_role.rolname = 'kokonut_sensor_ingestion_owner'
            OR granted_role.rolname = 'kokonut_sensor_ingestion_login'
            OR (
                member_role.rolname = 'kokonut_sensor_ingestion_login'
                AND (
                    granted_role.rolname <> 'kokonut_worker_execution'
                    OR membership.admin_option
                    OR membership.inherit_option
                    OR NOT membership.set_option
                )
            )
    ) THEN
        RAISE EXCEPTION 'sensor ingestion owner/login has an unexpected role membership';
    END IF;
END;
$$;

GRANT kokonut_worker_execution TO kokonut_sensor_ingestion_login
    WITH INHERIT FALSE, SET TRUE;
GRANT USAGE ON SCHEMA kokonut_security TO kokonut_sensor_ingestion_login;
GRANT USAGE ON SCHEMA kokonut_security, public TO kokonut_sensor_ingestion_owner;
GRANT EXECUTE ON FUNCTION kokonut_security.current_worker_scope(TEXT, TEXT)
    TO kokonut_sensor_ingestion_owner;
GRANT EXECUTE ON FUNCTION public.digest(BYTEA, TEXT)
    TO kokonut_sensor_ingestion_owner;

GRANT SELECT (
    id, driver_id, instance_name, config, location_id, is_enabled,
    run_count, consecutive_failures
) ON public.driver_instance TO kokonut_sensor_ingestion_owner;
GRANT UPDATE (
    last_run_at, last_status, last_error, run_count, consecutive_failures, updated_at
) ON public.driver_instance TO kokonut_sensor_ingestion_owner;
GRANT INSERT (
    instance_id, status, records_fetched, records_written, duration_ms, error_message
) ON public.driver_instance_log TO kokonut_sensor_ingestion_owner;
GRANT SELECT (id, driver_name, driver_type, module_path, class_name, is_enabled)
    ON public.driver_registry TO kokonut_sensor_ingestion_owner;
GRANT SELECT (
    id, name, slug, sensor_type_id, location_id, plot_id, status, protocol
) ON public.sensor_device TO kokonut_sensor_ingestion_owner;
GRANT SELECT (id, name, unit, min_value, max_value)
    ON public.sensor_type TO kokonut_sensor_ingestion_owner;
GRANT SELECT (
    id, location_id, plot_id, sensor_id, sensor_type, reading_date,
    reading_time, value, unit, quality
) ON public.sensor_reading TO kokonut_sensor_ingestion_owner;
GRANT INSERT (
    location_id, plot_id, sensor_id, sensor_type, reading_date, reading_time,
    value, unit, quality, metadata, source_system, source_id, source_raw,
    schema_version
) ON public.sensor_reading TO kokonut_sensor_ingestion_owner;
GRANT INSERT (
    source_system, source_table, source_id, target_table, target_id, operation,
    payload_hash, status, error_message, rows_affected, processing_time_ms,
    processor_version, batch_id, validation_status, validation_errors,
    validation_warnings, dedupe_key, location_id
) ON public.ingestion_log TO kokonut_sensor_ingestion_owner;
GRANT INSERT (event_type, source_table, source_id, payload, priority, status)
    ON public.platform_event TO kokonut_sensor_ingestion_owner;
GRANT SELECT (
    id, event_key, source_table, source_id, target_table, columns, rows, payload_hash
) ON public.clickhouse_outbox TO kokonut_sensor_ingestion_owner;
GRANT INSERT (
    event_key, source_table, source_id, target_table, columns, rows, payload_hash
) ON public.clickhouse_outbox TO kokonut_sensor_ingestion_owner;
GRANT UPDATE (updated_at) ON public.clickhouse_outbox
    TO kokonut_sensor_ingestion_owner;

-- The execution role can SET ROLE for bounded operations but cannot bypass
-- those functions by reading or writing the sensor source relations directly.
DO $$
DECLARE
    role_name TEXT;
    target_table RECORD;
BEGIN
    FOREACH role_name IN ARRAY ARRAY[
        'kokonut_worker_execution', 'kokonut_sensor_ingestion_login'
    ] LOOP
        IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = role_name) THEN
            EXECUTE format(
                'REVOKE ALL ON TABLE public.driver_instance, public.driver_instance_log, '
                || 'public.driver_registry, public.sensor_device, public.sensor_type, '
                || 'public.sensor_reading, public.ingestion_log, public.platform_event, '
                || 'public.clickhouse_outbox FROM %I', role_name
            );
            FOR target_table IN
                SELECT relation.relname,
                       string_agg(quote_ident(attribute.attname), ', ' ORDER BY attribute.attnum) AS columns
                  FROM pg_class AS relation
                  JOIN pg_namespace AS namespace ON namespace.oid = relation.relnamespace
                  JOIN pg_attribute AS attribute ON attribute.attrelid = relation.oid
                 WHERE namespace.nspname = 'public'
                   AND relation.relname IN (
                       'driver_instance', 'driver_instance_log', 'driver_registry',
                       'sensor_device', 'sensor_type', 'sensor_reading', 'ingestion_log',
                       'platform_event', 'clickhouse_outbox'
                   )
                   AND attribute.attnum > 0 AND NOT attribute.attisdropped
                 GROUP BY relation.relname
            LOOP
                EXECUTE format(
                    'REVOKE ALL (%s) ON TABLE public.%I FROM %I',
                    target_table.columns, target_table.relname, role_name
                );
            END LOOP;
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.resolve_sensor_driver_instance(
    requested_instance_id UUID,
    requested_location_id UUID
)
RETURNS TABLE (
    instance_id UUID,
    instance_name TEXT,
    driver_name TEXT,
    module_path TEXT,
    class_name TEXT,
    driver_type TEXT,
    config JSONB,
    location_id UUID
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    worker_scope RECORD;
BEGIN
    IF session_user <> 'kokonut_sensor_ingestion_login' THEN
        RAISE EXCEPTION 'sensor driver lookup requires its dedicated login'
            USING ERRCODE = '42501';
    END IF;
    SELECT scope.tenant_id, scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope('sensor_driver', 'ingest') AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'signed sensor-driver ingestion scope is required'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'sensor driver location differs from signed worker scope'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT instance.id, instance.instance_name::TEXT, driver.driver_name::TEXT,
           driver.module_path::TEXT, driver.class_name::TEXT,
           driver.driver_type::TEXT, instance.config, instance.location_id
      FROM public.driver_instance AS instance
      JOIN public.driver_registry AS driver ON driver.id = instance.driver_id
     WHERE instance.id = requested_instance_id
       AND instance.location_id = worker_scope.location_id
       AND instance.is_enabled IS TRUE
       AND octet_length(instance.config::TEXT) <= 65536
       AND driver.is_enabled IS TRUE
       AND driver.driver_name = 'sensor_csv'
       AND driver.driver_type = 'sensor'
       AND driver.module_path = 'services.ingestion.drivers.sensor_csv'
       AND driver.class_name = 'Driver';
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.read_sensor_driver_catalog(
    requested_location_id UUID
)
RETURNS TABLE (
    sensor_id UUID,
    sensor_name TEXT,
    sensor_slug TEXT,
    sensor_type_id UUID,
    sensor_type TEXT,
    location_id UUID,
    plot_id UUID,
    sensor_status TEXT,
    protocol TEXT,
    unit TEXT,
    min_value NUMERIC,
    max_value NUMERIC
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    worker_scope RECORD;
BEGIN
    IF session_user <> 'kokonut_sensor_ingestion_login' THEN
        RAISE EXCEPTION 'sensor catalog lookup requires its dedicated login'
            USING ERRCODE = '42501';
    END IF;
    SELECT scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope('sensor_driver', 'ingest') AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'signed sensor-driver ingestion scope is required'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'sensor catalog location differs from signed worker scope'
            USING ERRCODE = '42501';
    END IF;

    RETURN QUERY
    SELECT device.id, device.name::TEXT, device.slug::TEXT,
           sensor_kind.id, sensor_kind.name::TEXT, device.location_id,
           device.plot_id, device.status::TEXT, device.protocol::TEXT,
           sensor_kind.unit::TEXT, sensor_kind.min_value, sensor_kind.max_value
      FROM public.sensor_device AS device
      JOIN public.sensor_type AS sensor_kind ON sensor_kind.id = device.sensor_type_id
     WHERE device.location_id = worker_scope.location_id;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.store_sensor_driver_batch(
    requested_instance_id UUID,
    requested_location_id UUID,
    requested_records JSONB
)
RETURNS TABLE (records_fetched INTEGER, records_written INTEGER, records_rejected INTEGER)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    worker_scope RECORD;
    instance_row RECORD;
    item JSONB;
    record_json JSONB;
    source_digest TEXT;
    source_key TEXT;
    record_index INTEGER;
    source_index INTEGER;
    payload_hash TEXT;
    validation_status TEXT;
    validation_errors JSONB;
    validation_warnings JSONB;
    dedupe_key TEXT;
    device_identifier TEXT;
    reading_date_value DATE;
    reading_time_value TIME;
    reading_value NUMERIC;
    device_row RECORD;
    minimum_value NUMERIC;
    maximum_value NUMERIC;
    reading_quality TEXT;
    reading_id UUID;
    stored_value NUMERIC;
    stored_unit TEXT;
    stored_plot_id UUID;
    created BOOLEAN;
    projection_timestamp TEXT;
    projection_columns JSONB;
    projection_rows JSONB;
    projection_hash TEXT;
    inserted_outbox_id UUID;
    error_text TEXT;
BEGIN
    IF session_user <> 'kokonut_sensor_ingestion_login' THEN
        RAISE EXCEPTION 'sensor ingestion requires its dedicated login'
            USING ERRCODE = '42501';
    END IF;
    SELECT scope.tenant_id, scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope('sensor_driver', 'ingest') AS scope;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'signed sensor-driver ingestion scope is required'
            USING ERRCODE = '42501';
    END IF;
    IF requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'sensor batch location differs from signed worker scope'
            USING ERRCODE = '42501';
    END IF;
    IF requested_records IS NULL
       OR jsonb_typeof(requested_records) IS DISTINCT FROM 'array' THEN
        RAISE EXCEPTION 'sensor batch must be an array with at most 10000 records'
            USING ERRCODE = '22023';
    END IF;
    IF jsonb_array_length(requested_records) > 10000
       OR octet_length(requested_records::TEXT) > 67108864 THEN
        RAISE EXCEPTION 'sensor batch exceeds its record or payload limit'
            USING ERRCODE = '22023';
    END IF;

    SELECT instance.id
      INTO instance_row
      FROM public.driver_instance AS instance
      JOIN public.driver_registry AS driver ON driver.id = instance.driver_id
     WHERE instance.id = requested_instance_id
       AND instance.location_id = worker_scope.location_id
       AND instance.is_enabled IS TRUE
       AND octet_length(instance.config::TEXT) <= 65536
       AND driver.is_enabled IS TRUE
       AND driver.driver_name = 'sensor_csv'
       AND driver.driver_type = 'sensor'
       AND driver.module_path = 'services.ingestion.drivers.sensor_csv'
       AND driver.class_name = 'Driver'
     FOR SHARE OF instance;
    IF NOT FOUND THEN
        RAISE EXCEPTION 'enabled sensor driver instance was not found in signed scope'
            USING ERRCODE = '42501';
    END IF;

    records_fetched := jsonb_array_length(requested_records);
    records_written := 0;
    records_rejected := 0;
    projection_columns := jsonb_build_array(
        'timestamp', 'sensor_id', 'sensor_type', 'location_id', 'plot_id',
        'value', 'unit', 'quality', 'metadata'
    );

    FOR item IN SELECT value FROM jsonb_array_elements(requested_records)
    LOOP
        IF jsonb_typeof(item) IS DISTINCT FROM 'object'
           OR jsonb_typeof(item->'record') IS DISTINCT FROM 'object'
           OR jsonb_typeof(item->'validation_errors') IS DISTINCT FROM 'array'
           OR jsonb_typeof(item->'validation_warnings') IS DISTINCT FROM 'array' THEN
            RAISE EXCEPTION 'sensor batch item has an invalid shape'
                USING ERRCODE = '22023';
        END IF;
        source_digest := item->>'source_id_sha256';
        payload_hash := item->>'payload_hash';
        IF source_digest IS NULL OR source_digest !~ '^[0-9a-f]{64}$'
           OR payload_hash IS NULL OR payload_hash !~ '^[0-9a-f]{64}$' THEN
            RAISE EXCEPTION 'sensor batch hashes must be SHA-256 hex digests'
                USING ERRCODE = '22023';
        END IF;
        BEGIN
            source_index := (item->>'source_index')::INTEGER;
            record_index := (item->>'record_index')::INTEGER;
        EXCEPTION WHEN OTHERS THEN
            RAISE EXCEPTION 'sensor batch indexes must be integers'
                USING ERRCODE = '22023';
        END;
        IF source_index IS NULL OR record_index IS NULL
           OR source_index < 0 OR source_index >= 100
           OR record_index < 0 OR record_index >= 10000 THEN
            RAISE EXCEPTION 'sensor batch indexes are outside their bounds'
                USING ERRCODE = '22023';
        END IF;
        record_json := item->'record';
        validation_status := item->>'validation_status';
        validation_errors := item->'validation_errors';
        validation_warnings := item->'validation_warnings';
        dedupe_key := NULLIF(item->>'dedupe_key', '');
        IF validation_status IS NULL
           OR validation_status NOT IN ('accepted', 'suspect', 'rejected')
           OR jsonb_array_length(validation_errors) > 16
           OR jsonb_array_length(validation_warnings) > 16
           OR octet_length(record_json::TEXT) > 65536 THEN
            RAISE EXCEPTION 'sensor batch validation metadata exceeds its contract'
                USING ERRCODE = '22023';
        END IF;
        IF EXISTS (
            SELECT 1 FROM jsonb_array_elements_text(validation_errors) AS error(value)
             WHERE length(error.value) > 512
        ) OR EXISTS (
            SELECT 1 FROM jsonb_array_elements_text(validation_warnings) AS warning(value)
             WHERE length(warning.value) > 512
        ) THEN
            RAISE EXCEPTION 'sensor validation messages exceed their contract'
                USING ERRCODE = '22023';
        END IF;
        IF validation_status <> 'rejected'
           AND jsonb_array_length(validation_errors) > 0 THEN
            RAISE EXCEPTION 'non-rejected sensor batch record cannot contain validation errors'
                USING ERRCODE = '22023';
        END IF;
        IF validation_status = 'accepted'
           AND jsonb_array_length(validation_warnings) > 0 THEN
            validation_status := 'suspect';
        END IF;

        source_key := requested_instance_id::TEXT || ':' || source_digest || ':' || record_index::TEXT;
        IF validation_status = 'rejected' THEN
            SELECT string_agg(error.value, '; ' ORDER BY error.ordinality)
              INTO error_text
              FROM jsonb_array_elements_text(validation_errors)
                   WITH ORDINALITY AS error(value, ordinality);
            INSERT INTO public.ingestion_log (
                source_system, source_table, source_id, target_table, target_id,
                operation, payload_hash, status, error_message, rows_affected,
                processing_time_ms, processor_version, validation_status,
                validation_errors, validation_warnings, dedupe_key, location_id
            ) VALUES (
                'sensor_driver', 'sensor_driver_record', source_key,
                'sensor_reading', NULL, 'insert', payload_hash, 'failed',
                COALESCE(error_text, 'sensor record was rejected'), 0, 0,
                '1.0.0', 'rejected', validation_errors, validation_warnings,
                dedupe_key, worker_scope.location_id
            );
            records_rejected := records_rejected + 1;
            CONTINUE;
        END IF;

        device_identifier := NULLIF(btrim(record_json->>'device_id'), '');
        IF device_identifier IS NULL THEN
            RAISE EXCEPTION 'accepted sensor record requires a device_id'
                USING ERRCODE = '22023';
        END IF;
        BEGIN
            IF record_json->>'reading_date' !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
               OR COALESCE(record_json->>'reading_time', '00:00:00') !~ '^[0-9]{2}:[0-9]{2}:[0-9]{2}$' THEN
                RAISE EXCEPTION 'sensor timestamp must use the canonical date/time format';
            END IF;
            reading_date_value := (record_json->>'reading_date')::DATE;
            reading_time_value := COALESCE(NULLIF(record_json->>'reading_time', ''), '00:00:00')::TIME;
            reading_value := (record_json->>'value')::NUMERIC;
        EXCEPTION WHEN OTHERS THEN
            RAISE EXCEPTION 'accepted sensor record has an invalid timestamp or number'
                USING ERRCODE = '22023';
        END;
        IF reading_value::TEXT IN ('NaN', 'Infinity', '-Infinity') THEN
            RAISE EXCEPTION 'sensor value must be finite' USING ERRCODE = '22023';
        END IF;

        SELECT device.id, device.name, device.slug, device.sensor_type_id,
               sensor_kind.name AS sensor_type, device.location_id,
               device.plot_id, device.status, device.protocol, sensor_kind.unit,
               sensor_kind.min_value, sensor_kind.max_value
          INTO device_row
          FROM public.sensor_device AS device
          JOIN public.sensor_type AS sensor_kind ON sensor_kind.id = device.sensor_type_id
         WHERE device.location_id = worker_scope.location_id
           AND (device.id::TEXT = device_identifier OR device.slug = device_identifier)
         ORDER BY (device.id::TEXT = device_identifier) DESC
         LIMIT 1;
        IF NOT FOUND THEN
            validation_status := 'rejected';
            validation_errors := validation_errors || jsonb_build_array(
                'sensor is not registered in the instance location'
            );
            SELECT string_agg(error.value, '; ' ORDER BY error.ordinality)
              INTO error_text
              FROM jsonb_array_elements_text(validation_errors)
                   WITH ORDINALITY AS error(value, ordinality);
            INSERT INTO public.ingestion_log (
                source_system, source_table, source_id, target_table, target_id,
                operation, payload_hash, status, error_message, rows_affected,
                processing_time_ms, processor_version, validation_status,
                validation_errors, validation_warnings, dedupe_key, location_id
            ) VALUES (
                'sensor_driver', 'sensor_driver_record', source_key,
                'sensor_reading', NULL, 'insert', payload_hash, 'failed',
                error_text, 0, 0, '1.0.0', 'rejected', validation_errors,
                validation_warnings, dedupe_key, worker_scope.location_id
            );
            records_rejected := records_rejected + 1;
            CONTINUE;
        END IF;

        minimum_value := COALESCE(
            device_row.min_value,
            CASE device_row.sensor_type
                WHEN 'soil_moisture' THEN 0 WHEN 'soil_temperature' THEN -40
                WHEN 'air_temperature' THEN -50 WHEN 'humidity' THEN 0
                WHEN 'light' THEN 0 WHEN 'rainfall' THEN 0 WHEN 'water_level' THEN 0
            END
        );
        maximum_value := COALESCE(
            device_row.max_value,
            CASE device_row.sensor_type
                WHEN 'soil_moisture' THEN 100 WHEN 'soil_temperature' THEN 80
                WHEN 'air_temperature' THEN 60 WHEN 'humidity' THEN 100
                WHEN 'light' THEN 200000 WHEN 'rainfall' THEN 500 WHEN 'water_level' THEN 10000
            END
        );
        IF minimum_value IS NOT NULL AND maximum_value IS NOT NULL
           AND (reading_value < minimum_value OR reading_value > maximum_value) THEN
            validation_status := 'suspect';
            IF NOT validation_warnings ? 'value outside configured sensor range' THEN
                validation_warnings := validation_warnings
                    || jsonb_build_array('value outside configured sensor range');
            END IF;
        END IF;
        reading_quality := CASE WHEN validation_status = 'suspect' THEN 'suspect' ELSE 'good' END;

        INSERT INTO public.sensor_reading (
            location_id, plot_id, sensor_id, sensor_type, reading_date,
            reading_time, value, unit, quality, metadata, source_system,
            source_id, source_raw, schema_version
        ) VALUES (
            worker_scope.location_id, device_row.plot_id, device_row.id,
            device_row.sensor_type, reading_date_value, reading_time_value,
            reading_value, device_row.unit, reading_quality,
            jsonb_build_object(
                'driver_instance_id', requested_instance_id,
                'source_id_sha256', source_digest,
                'source_index', source_index,
                'record_index', record_index
            ),
            'sensor_driver', source_key, record_json, 'field-ingestion-v1'
        )
        ON CONFLICT (sensor_id, reading_date, reading_time) DO NOTHING
        RETURNING id, value, unit, plot_id
             INTO reading_id, stored_value, stored_unit, stored_plot_id;
        created := FOUND;
        IF NOT created THEN
            SELECT existing.id, existing.value, existing.quality, existing.unit, existing.plot_id
              INTO reading_id, stored_value, reading_quality, stored_unit, stored_plot_id
              FROM public.sensor_reading AS existing
             WHERE existing.sensor_id = device_row.id
               AND existing.reading_date = reading_date_value
               AND existing.reading_time = reading_time_value;
            IF NOT FOUND OR stored_value IS DISTINCT FROM reading_value::NUMERIC(12,4)
               OR reading_quality IS DISTINCT FROM
                    (CASE WHEN validation_status = 'suspect' THEN 'suspect' ELSE 'good' END) THEN
                RAISE EXCEPTION 'sensor timestamp conflicts with an existing reading'
                    USING ERRCODE = '23505';
            END IF;
        END IF;

        projection_timestamp := to_char(
            (reading_date_value + reading_time_value), 'YYYY-MM-DD HH24:MI:SS'
        ) || '+00:00';
        projection_rows := jsonb_build_array(jsonb_build_array(
            projection_timestamp, device_row.id::TEXT, device_row.sensor_type,
            worker_scope.location_id::TEXT,
            CASE WHEN stored_plot_id IS NULL THEN NULL ELSE stored_plot_id::TEXT END,
            stored_value::DOUBLE PRECISION, stored_unit, reading_quality, '{}'::JSONB
        ));
        projection_hash := encode(public.digest(convert_to(
            '{"reading_id":' || to_json(reading_id::TEXT)::TEXT ||
            ',"timestamp":' || to_json(projection_timestamp)::TEXT ||
            ',"value":' || to_json(stored_value::TEXT)::TEXT || '}',
            'UTF8'
        ), 'sha256'), 'hex');
        INSERT INTO public.clickhouse_outbox (
            event_key, source_table, source_id, target_table, columns, rows, payload_hash
        ) VALUES (
            'sensor_reading:sensor_readings:' || reading_id::TEXT,
            'sensor_reading', reading_id::TEXT, 'sensor_readings',
            projection_columns, projection_rows, projection_hash
        )
        ON CONFLICT (event_key) DO UPDATE SET updated_at = statement_timestamp()
        WHERE public.clickhouse_outbox.payload_hash = EXCLUDED.payload_hash
          AND public.clickhouse_outbox.source_table = EXCLUDED.source_table
          AND public.clickhouse_outbox.source_id = EXCLUDED.source_id
          AND public.clickhouse_outbox.target_table = EXCLUDED.target_table
          AND public.clickhouse_outbox.columns = EXCLUDED.columns
          AND public.clickhouse_outbox.rows = EXCLUDED.rows
        RETURNING id INTO inserted_outbox_id;
        IF inserted_outbox_id IS NULL THEN
            RAISE EXCEPTION 'sensor projection conflicts with an existing outbox event'
                USING ERRCODE = '23505';
        END IF;

        IF created THEN
            INSERT INTO public.platform_event (
                event_type, source_table, source_id, payload, priority, status
            ) VALUES (
                'sensor_reading', 'sensor_reading', reading_id,
                jsonb_build_object(
                    'sensor_id', device_row.id::TEXT,
                    'sensor_type', device_row.sensor_type,
                    'location_id', worker_scope.location_id::TEXT,
                    'value', stored_value::DOUBLE PRECISION,
                    'quality', reading_quality,
                    'reading_date', reading_date_value::TEXT,
                    'reading_time', reading_time_value::TEXT
                ), 'normal', 'pending'
            );
            records_written := records_written + 1;
        END IF;

        SELECT string_agg(error.value, '; ' ORDER BY error.ordinality)
          INTO error_text
          FROM jsonb_array_elements_text(validation_errors)
               WITH ORDINALITY AS error(value, ordinality);
        INSERT INTO public.ingestion_log (
            source_system, source_table, source_id, target_table, target_id,
            operation, payload_hash, status, error_message, rows_affected,
            processing_time_ms, processor_version, validation_status,
            validation_errors, validation_warnings, dedupe_key, location_id
        ) VALUES (
            'sensor_driver', 'sensor_driver_record', source_key,
            'sensor_reading', reading_id, 'insert', payload_hash, 'success',
            NULLIF(error_text, ''), 1, 0, '1.0.0', validation_status,
            validation_errors, validation_warnings, dedupe_key,
            worker_scope.location_id
        );
    END LOOP;
    RETURN NEXT;
END;
$$;

CREATE OR REPLACE FUNCTION kokonut_security.update_sensor_driver_status(
    requested_instance_id UUID,
    requested_location_id UUID,
    requested_status TEXT,
    requested_records_fetched INTEGER,
    requested_records_written INTEGER,
    requested_duration_ms INTEGER,
    requested_error TEXT
)
RETURNS BOOLEAN
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = pg_catalog
AS $$
DECLARE
    worker_scope RECORD;
BEGIN
    IF session_user <> 'kokonut_sensor_ingestion_login' THEN
        RAISE EXCEPTION 'sensor status update requires its dedicated login'
            USING ERRCODE = '42501';
    END IF;
    SELECT scope.location_id
      INTO worker_scope
      FROM kokonut_security.current_worker_scope('sensor_driver', 'ingest') AS scope;
    IF NOT FOUND OR requested_location_id IS DISTINCT FROM worker_scope.location_id THEN
        RAISE EXCEPTION 'signed sensor-driver ingestion scope is required'
            USING ERRCODE = '42501';
    END IF;
    IF requested_status IS NULL OR requested_status NOT IN ('success', 'failed')
       OR requested_records_fetched IS NULL OR requested_records_written IS NULL
       OR requested_duration_ms IS NULL
       OR requested_records_fetched < 0 OR requested_records_written < 0
       OR requested_records_written > requested_records_fetched
       OR requested_duration_ms < 0 OR requested_duration_ms > 600000
       OR (requested_error IS NOT NULL AND length(requested_error) > 500) THEN
        RAISE EXCEPTION 'sensor driver status values are invalid'
            USING ERRCODE = '22023';
    END IF;

    INSERT INTO public.driver_instance_log (
        instance_id, status, records_fetched, records_written, duration_ms, error_message
    )
    SELECT instance.id, requested_status, requested_records_fetched,
           requested_records_written, requested_duration_ms, requested_error
      FROM public.driver_instance AS instance
      JOIN public.driver_registry AS driver ON driver.id = instance.driver_id
     WHERE instance.id = requested_instance_id
       AND instance.location_id = worker_scope.location_id
       AND driver.driver_name = 'sensor_csv'
       AND driver.driver_type = 'sensor'
       AND driver.module_path = 'services.ingestion.drivers.sensor_csv'
       AND driver.class_name = 'Driver';
    IF NOT FOUND THEN
        RETURN FALSE;
    END IF;

    IF requested_status = 'success' THEN
        UPDATE public.driver_instance
           SET last_run_at = statement_timestamp(), last_status = requested_status,
               run_count = run_count + 1, consecutive_failures = 0,
               updated_at = statement_timestamp()
         WHERE id = requested_instance_id AND location_id = worker_scope.location_id;
    ELSE
        UPDATE public.driver_instance
           SET last_run_at = statement_timestamp(), last_status = requested_status,
               last_error = requested_error, run_count = run_count + 1,
               consecutive_failures = consecutive_failures + 1,
               updated_at = statement_timestamp()
         WHERE id = requested_instance_id AND location_id = worker_scope.location_id;
    END IF;
    RETURN FOUND;
END;
$$;

ALTER FUNCTION kokonut_security.resolve_sensor_driver_instance(UUID, UUID)
    OWNER TO kokonut_sensor_ingestion_owner;
ALTER FUNCTION kokonut_security.read_sensor_driver_catalog(UUID)
    OWNER TO kokonut_sensor_ingestion_owner;
ALTER FUNCTION kokonut_security.store_sensor_driver_batch(UUID, UUID, JSONB)
    OWNER TO kokonut_sensor_ingestion_owner;
ALTER FUNCTION kokonut_security.update_sensor_driver_status(UUID, UUID, TEXT, INTEGER, INTEGER, INTEGER, TEXT)
    OWNER TO kokonut_sensor_ingestion_owner;

-- These policies are dormant until an operator enables and forces RLS on the
-- source relations. They make the SECURITY DEFINER boundary survive that
-- later hardening without granting the login any direct relation privileges.
-- Event/outbox lineage is constructed from the scoped reading inside the
-- bounded writer; policies validate its event family and signed scope without
-- opening a cross-table RLS lookup from the policy expression.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public'
                   AND tablename = 'driver_registry' AND policyname = 'sensor_worker_registry_read') THEN
        CREATE POLICY sensor_worker_registry_read ON public.driver_registry
            FOR SELECT TO kokonut_sensor_ingestion_owner
            USING (driver_name = 'sensor_csv' AND driver_type = 'sensor'
                   AND module_path = 'services.ingestion.drivers.sensor_csv'
                   AND class_name = 'Driver'
                   AND EXISTS (SELECT 1 FROM kokonut_security.current_worker_scope('sensor_driver', 'ingest')));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public'
                   AND tablename = 'driver_instance' AND policyname = 'sensor_worker_instance_read') THEN
        CREATE POLICY sensor_worker_instance_read ON public.driver_instance
            FOR SELECT TO kokonut_sensor_ingestion_owner
            USING (location_id = (SELECT scope.location_id
                                    FROM kokonut_security.current_worker_scope('sensor_driver', 'ingest') AS scope));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public'
                   AND tablename = 'driver_instance' AND policyname = 'sensor_worker_instance_update') THEN
        CREATE POLICY sensor_worker_instance_update ON public.driver_instance
            FOR UPDATE TO kokonut_sensor_ingestion_owner
            USING (location_id = (SELECT scope.location_id
                                    FROM kokonut_security.current_worker_scope('sensor_driver', 'ingest') AS scope))
            WITH CHECK (location_id = (SELECT scope.location_id
                                         FROM kokonut_security.current_worker_scope('sensor_driver', 'ingest') AS scope));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public'
                   AND tablename = 'driver_instance_log' AND policyname = 'sensor_worker_run_log_insert') THEN
        CREATE POLICY sensor_worker_run_log_insert ON public.driver_instance_log
            FOR INSERT TO kokonut_sensor_ingestion_owner
            WITH CHECK (EXISTS (
                SELECT 1 FROM public.driver_instance AS instance
                 WHERE instance.id = instance_id
                   AND instance.location_id = (SELECT scope.location_id
                        FROM kokonut_security.current_worker_scope('sensor_driver', 'ingest') AS scope)
            ));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public'
                   AND tablename = 'sensor_device' AND policyname = 'sensor_worker_device_read') THEN
        CREATE POLICY sensor_worker_device_read ON public.sensor_device
            FOR SELECT TO kokonut_sensor_ingestion_owner
            USING (location_id = (SELECT scope.location_id
                                    FROM kokonut_security.current_worker_scope('sensor_driver', 'ingest') AS scope));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public'
                   AND tablename = 'sensor_type' AND policyname = 'sensor_worker_type_read') THEN
        CREATE POLICY sensor_worker_type_read ON public.sensor_type
            FOR SELECT TO kokonut_sensor_ingestion_owner
            -- sensor_type is shared reference metadata, not tenant data. Keep
            -- it available only while a signed sensor-ingestion grant is active;
            -- location scoping remains enforced on sensor_device.
            USING (EXISTS (
                SELECT 1 FROM kokonut_security.current_worker_scope('sensor_driver', 'ingest')
            ));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public'
                   AND tablename = 'sensor_reading' AND policyname = 'sensor_worker_reading_read') THEN
        CREATE POLICY sensor_worker_reading_read ON public.sensor_reading
            FOR SELECT TO kokonut_sensor_ingestion_owner
            USING (location_id = (SELECT scope.location_id
                                    FROM kokonut_security.current_worker_scope('sensor_driver', 'ingest') AS scope));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public'
                   AND tablename = 'sensor_reading' AND policyname = 'sensor_worker_reading_insert') THEN
        CREATE POLICY sensor_worker_reading_insert ON public.sensor_reading
            FOR INSERT TO kokonut_sensor_ingestion_owner
            WITH CHECK (location_id = (SELECT scope.location_id
                                         FROM kokonut_security.current_worker_scope('sensor_driver', 'ingest') AS scope));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public'
                   AND tablename = 'ingestion_log' AND policyname = 'sensor_worker_ingestion_audit_insert') THEN
        CREATE POLICY sensor_worker_ingestion_audit_insert ON public.ingestion_log
            FOR INSERT TO kokonut_sensor_ingestion_owner
            WITH CHECK (location_id = (SELECT scope.location_id
                                         FROM kokonut_security.current_worker_scope('sensor_driver', 'ingest') AS scope));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public'
                   AND tablename = 'clickhouse_outbox' AND policyname = 'sensor_worker_outbox_read') THEN
        CREATE POLICY sensor_worker_outbox_read ON public.clickhouse_outbox
            FOR SELECT TO kokonut_sensor_ingestion_owner
            USING (source_table = 'sensor_reading' AND EXISTS (
                SELECT 1 FROM kokonut_security.current_worker_scope('sensor_driver', 'ingest')
            ));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public'
                   AND tablename = 'clickhouse_outbox' AND policyname = 'sensor_worker_outbox_insert') THEN
        CREATE POLICY sensor_worker_outbox_insert ON public.clickhouse_outbox
            FOR INSERT TO kokonut_sensor_ingestion_owner
            WITH CHECK (source_table = 'sensor_reading' AND EXISTS (
                SELECT 1 FROM kokonut_security.current_worker_scope('sensor_driver', 'ingest')
            ));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public'
                   AND tablename = 'clickhouse_outbox' AND policyname = 'sensor_worker_outbox_update') THEN
        CREATE POLICY sensor_worker_outbox_update ON public.clickhouse_outbox
            FOR UPDATE TO kokonut_sensor_ingestion_owner
            USING (source_table = 'sensor_reading' AND EXISTS (
                SELECT 1 FROM kokonut_security.current_worker_scope('sensor_driver', 'ingest')
            ))
            WITH CHECK (source_table = 'sensor_reading' AND EXISTS (
                SELECT 1 FROM kokonut_security.current_worker_scope('sensor_driver', 'ingest')
            ));
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname = 'public'
                   AND tablename = 'platform_event' AND policyname = 'sensor_worker_event_insert') THEN
        CREATE POLICY sensor_worker_event_insert ON public.platform_event
            FOR INSERT TO kokonut_sensor_ingestion_owner
            WITH CHECK (source_table = 'sensor_reading' AND EXISTS (
                SELECT 1 FROM kokonut_security.current_worker_scope('sensor_driver', 'ingest')
            ));
    END IF;
END;
$$;

REVOKE ALL ON FUNCTION kokonut_security.resolve_sensor_driver_instance(UUID, UUID)
    FROM PUBLIC, kokonut_runtime, kokonut_worker_login, kokonut_worker_execution;
REVOKE ALL ON FUNCTION kokonut_security.read_sensor_driver_catalog(UUID)
    FROM PUBLIC, kokonut_runtime, kokonut_worker_login, kokonut_worker_execution;
REVOKE ALL ON FUNCTION kokonut_security.store_sensor_driver_batch(UUID, UUID, JSONB)
    FROM PUBLIC, kokonut_runtime, kokonut_worker_login, kokonut_worker_execution;
REVOKE ALL ON FUNCTION kokonut_security.update_sensor_driver_status(UUID, UUID, TEXT, INTEGER, INTEGER, INTEGER, TEXT)
    FROM PUBLIC, kokonut_runtime, kokonut_worker_login, kokonut_worker_execution;

GRANT EXECUTE ON FUNCTION kokonut_security.resolve_sensor_driver_instance(UUID, UUID),
    kokonut_security.read_sensor_driver_catalog(UUID),
    kokonut_security.store_sensor_driver_batch(UUID, UUID, JSONB),
    kokonut_security.update_sensor_driver_status(UUID, UUID, TEXT, INTEGER, INTEGER, INTEGER, TEXT)
TO kokonut_worker_execution;

COMMENT ON FUNCTION kokonut_security.resolve_sensor_driver_instance(UUID, UUID) IS
    'Returns one enabled code-allowlisted sensor CSV instance only within a signed sensor_driver/ingest location.';
COMMENT ON FUNCTION kokonut_security.read_sensor_driver_catalog(UUID) IS
    'Returns sensor devices and type bounds only within the signed sensor_driver/ingest location.';
COMMENT ON FUNCTION kokonut_security.store_sensor_driver_batch(UUID, UUID, JSONB) IS
    'Atomically records a bounded signed sensor CSV batch, ingestion audit, sensor events, and ClickHouse projection intents.';
COMMENT ON FUNCTION kokonut_security.update_sensor_driver_status(UUID, UUID, TEXT, INTEGER, INTEGER, INTEGER, TEXT) IS
    'Updates one code-allowlisted sensor driver instance run status only within the signed location.';

COMMIT;
