-- Graph node/edge types are versioned projection contracts. New type keys
-- accompany reviewed schema/projection changes; the runtime worker updates the
-- projection/generation and materialized node/edge rows while triggers read this
-- catalog.
BEGIN;

DO $$
DECLARE
    table_name TEXT;
    column_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['graph_node_type', 'graph_edge_type']
    LOOP
        IF to_regclass(format('public.%I', table_name)) IS NULL THEN
            RAISE EXCEPTION 'required graph projection type relation public.% is missing', table_name;
        END IF;

        IF EXISTS (SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime') THEN
            EXECUTE format(
                'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM kokonut_runtime',
                table_name
            );

            FOR column_name IN
                SELECT attname
                  FROM pg_catalog.pg_attribute
                 WHERE attrelid = to_regclass(format('public.%I', table_name))
                   AND attnum > 0
                   AND NOT attisdropped
            LOOP
                EXECUTE format(
                    'REVOKE INSERT (%1$I) ON TABLE public.%2$I FROM kokonut_runtime',
                    column_name,
                    table_name
                );
                EXECUTE format(
                    'REVOKE UPDATE (%1$I) ON TABLE public.%2$I FROM kokonut_runtime',
                    column_name,
                    table_name
                );
                EXECUTE format(
                    'REVOKE REFERENCES (%1$I) ON TABLE public.%2$I FROM kokonut_runtime',
                    column_name,
                    table_name
                );
            END LOOP;

            EXECUTE format(
                'GRANT SELECT ON TABLE public.%I TO kokonut_runtime',
                table_name
            );
        END IF;
    END LOOP;
END;
$$;

COMMENT ON TABLE public.graph_node_type IS
    'Versioned graph projection node-type contract. kokonut_runtime has read-only access; changes require a reviewed projection/schema migration.';
COMMENT ON TABLE public.graph_edge_type IS
    'Versioned graph projection edge-type contract. kokonut_runtime has read-only access; changes require a reviewed projection/schema migration.';

COMMIT;
