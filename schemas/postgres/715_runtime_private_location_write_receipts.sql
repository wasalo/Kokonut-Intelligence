-- Keep bounded location-write idempotency receipts inaccessible to broad
-- runtime, Directus, and PUBLIC grants. The SECURITY DEFINER function owners
-- retain their narrowly granted receipt columns and replay behavior.

BEGIN;

DO $$
DECLARE
    receipt_table TEXT;
    target_role TEXT;
    target_role_sql TEXT;
    receipt_relation REGCLASS;
    column_name TEXT;
BEGIN
    FOREACH receipt_table IN ARRAY ARRAY[
        'composting_capture_receipt',
        'operating_capacity_draft_receipt',
        'operating_capacity_draft_revision_receipt',
        'operating_capacity_draft_submission_receipt',
        'operating_demand_draft_receipt',
        'operating_demand_draft_revision_receipt',
        'operating_demand_draft_submission_receipt',
        'operating_pilot_coaching_session_receipt',
        'pesticide_impact_capture_receipt',
        'pollinator_habitat_capture_receipt',
        'pollinator_hive_capture_receipt',
        'pollinator_hive_inspection_capture_receipt',
        'pollinator_observation_capture_receipt',
        'pollution_incident_operation_receipt',
        'recycling_capture_receipt',
        'solution_adoption_program_creation_receipt',
        'solution_experiment_creation_receipt',
        'solution_experiment_protocol_approval_receipt',
        'solution_experiment_start_receipt',
        'solution_experiment_submission_receipt',
        'solution_gate_definition_receipt',
        'solution_nonpromotion_transition_receipt',
        'waste_stream_capture_receipt'
    ] LOOP
        receipt_relation := pg_catalog.to_regclass(
            pg_catalog.format('public.%I', receipt_table)
        );
        IF receipt_relation IS NULL THEN
            RAISE EXCEPTION 'required receipt relation public.% is missing', receipt_table;
        END IF;

        FOREACH target_role IN ARRAY ARRAY[
            'PUBLIC', 'kokonut_runtime', 'kokonut_directus_runtime'
        ] LOOP
            IF target_role = 'PUBLIC' OR EXISTS (
                SELECT 1
                  FROM pg_catalog.pg_roles
                 WHERE rolname = target_role
            ) THEN
                target_role_sql := CASE
                    WHEN target_role = 'PUBLIC' THEN 'PUBLIC'
                    ELSE pg_catalog.quote_ident(target_role)
                END;

                EXECUTE pg_catalog.format(
                    'REVOKE ALL PRIVILEGES ON TABLE public.%I FROM %s',
                    receipt_table,
                    target_role_sql
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
                        'ON TABLE public.%2$I FROM %3$s',
                        column_name,
                        receipt_table,
                        target_role_sql
                    );
                END LOOP;
            END IF;
        END LOOP;

        EXECUTE pg_catalog.format(
            'COMMENT ON TABLE public.%I IS %L',
            receipt_table,
            'Private idempotency receipt for a bounded location-scoped writer. Direct runtime, Directus, and PUBLIC table/column access is denied; the bounded function owner retains explicit grants.'
        );
    END LOOP;
END;
$$;

COMMIT;
