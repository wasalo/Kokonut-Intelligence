-- These public reporting projections aggregate governed records and are not
-- mutation surfaces. Preserve reads while preventing runtime grants from
-- becoming usable if any of the views is redefined as updatable.
BEGIN;

DO $$
DECLARE
    view_name TEXT;
    column_name TEXT;
    relation_oid REGCLASS;
    relation_kind "char";
    target_views CONSTANT TEXT[] := ARRAY[
        'v_public_attestation_summary',
        'v_public_ebf_scorecard_summary',
        'v_public_ebf_pillar_summary'
    ];
BEGIN
    FOREACH view_name IN ARRAY target_views LOOP
        relation_oid := pg_catalog.to_regclass(
            pg_catalog.format('public.%I', view_name)
        );
        IF relation_oid IS NULL THEN
            RAISE EXCEPTION 'required relation public.% is missing', view_name;
        END IF;

        SELECT class.relkind
          INTO relation_kind
          FROM pg_catalog.pg_class AS class
         WHERE class.oid = relation_oid;
        IF relation_kind <> 'v' THEN
            RAISE EXCEPTION 'public.% must remain a view', view_name;
        END IF;

        IF pg_catalog.pg_relation_is_updatable(relation_oid, TRUE) <> 0 THEN
            RAISE EXCEPTION 'public.% must remain non-updatable', view_name;
        END IF;

        IF EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = 'kokonut_runtime'
        ) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM kokonut_runtime',
                view_name
            );

            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = relation_oid
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                    'ON TABLE public.%2$I FROM kokonut_runtime',
                    column_name,
                    view_name
                );
            END LOOP;

            EXECUTE pg_catalog.format(
                'GRANT SELECT ON TABLE public.%I TO kokonut_runtime',
                view_name
            );
        END IF;

        EXECUTE pg_catalog.format(
            'COMMENT ON VIEW public.%I IS %L',
            view_name,
            'Public aggregate projection; kokonut_runtime may read but not mutate this view.'
        );
    END LOOP;
END;
$$;

COMMIT;
