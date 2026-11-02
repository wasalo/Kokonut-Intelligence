-- Keep location solution creation receipts private to their bounded writer.
-- Runtime compatibility provisioning grants broad table access, so this
-- forward migration reapplies the direct-access denial without changing the
-- column grants held by kokonut_solution_creator_owner.

BEGIN;

DO $$
DECLARE
    target_role TEXT;
    column_name TEXT;
    receipt_relation REGCLASS;
BEGIN
    receipt_relation := pg_catalog.to_regclass(
        'public.location_solution_creation_receipt'
    );
    IF receipt_relation IS NULL THEN
        RAISE EXCEPTION 'required relation public.location_solution_creation_receipt is missing';
    END IF;

    FOREACH target_role IN ARRAY ARRAY[
        'PUBLIC', 'kokonut_runtime', 'kokonut_directus_runtime'
    ] LOOP
        IF target_role = 'PUBLIC' OR EXISTS (
            SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = target_role
        ) THEN
            EXECUTE pg_catalog.format(
                'REVOKE ALL PRIVILEGES ON TABLE public.location_solution_creation_receipt FROM %s',
                CASE WHEN target_role = 'PUBLIC'
                    THEN 'PUBLIC'
                    ELSE pg_catalog.quote_ident(target_role)
                END
            );

            FOR column_name IN
                SELECT attribute.attname
                  FROM pg_catalog.pg_attribute AS attribute
                 WHERE attribute.attrelid = receipt_relation
                   AND attribute.attnum > 0
                   AND NOT attribute.attisdropped
            LOOP
                EXECUTE pg_catalog.format(
                    'REVOKE SELECT (%1$I), INSERT (%1$I), UPDATE (%1$I), REFERENCES (%1$I) '
                    'ON TABLE public.location_solution_creation_receipt FROM %2$s',
                    column_name,
                    CASE WHEN target_role = 'PUBLIC'
                        THEN 'PUBLIC'
                        ELSE pg_catalog.quote_ident(target_role)
                    END
                );
            END LOOP;
        END IF;
    END LOOP;

    COMMENT ON TABLE public.location_solution_creation_receipt IS
        'Private idempotency receipts for kokonut_security.create_location_solution. Direct runtime, Directus, and PUBLIC access is denied; the bounded function owner retains its explicit column grants.';
END;
$$;

COMMIT;
