-- ============================================================
-- 313_phase2_backfill_phase3_reference_validation.sql
-- Backfill normalized relationship entities and validate high-risk links.
-- ============================================================

-- Preserve metric provenance from the legacy UUID array. The explicit entity
-- becomes authoritative for new consumers while the source column remains for
-- compatibility until all writers migrate.
INSERT INTO metric_value_source (
    metric_value_id, source_entity_type, source_entity_id, contribution_role, sequence_order
)
SELECT mv.id, 'legacy_source_record', source_id, 'supporting', source_order
FROM metric_value mv
CROSS JOIN LATERAL unnest(mv.source_record_ids) WITH ORDINALITY AS source(source_id, source_order)
WHERE mv.source_record_ids IS NOT NULL
ON CONFLICT (metric_value_id, source_entity_type, source_entity_id, source_ref) DO NOTHING;

-- Expand the structured forecast assumption objects into one relationship
-- entity per assumption, retaining the original JSON columns as snapshots.
INSERT INTO forecast_assumption (
    scenario_id, assumption_key, value, source_type, source_ref, sequence_order
)
SELECT fs.id, assumption.key, assumption.value, assumption.source_type,
       assumption.source_ref, ROW_NUMBER() OVER (
           PARTITION BY fs.id, assumption.key ORDER BY assumption.source_type
       )::integer
FROM forecast_scenario fs
CROSS JOIN LATERAL (
    SELECT key, value, 'assumptions'::varchar AS source_type,
           'forecast_scenario.assumptions'::text AS source_ref
    FROM jsonb_each(CASE WHEN jsonb_typeof(fs.assumptions) = 'object' THEN fs.assumptions ELSE '{}'::jsonb END)
    UNION ALL
    SELECT key, value, 'price_assumptions'::varchar, 'forecast_scenario.price_assumptions'::text
    FROM jsonb_each(CASE WHEN jsonb_typeof(fs.price_assumptions) = 'object' THEN fs.price_assumptions ELSE '{}'::jsonb END)
    UNION ALL
    SELECT key, value, 'yield_assumptions'::varchar, 'forecast_scenario.yield_assumptions'::text
    FROM jsonb_each(CASE WHEN jsonb_typeof(fs.yield_assumptions) = 'object' THEN fs.yield_assumptions ELSE '{}'::jsonb END)
    UNION ALL
    SELECT key, value, 'cost_assumptions'::varchar, 'forecast_scenario.cost_assumptions'::text
    FROM jsonb_each(CASE WHEN jsonb_typeof(fs.cost_assumptions) = 'object' THEN fs.cost_assumptions ELSE '{}'::jsonb END)
    UNION ALL
    SELECT key, value, 'growth_assumptions'::varchar, 'forecast_scenario.growth_assumptions'::text
    FROM jsonb_each(CASE WHEN jsonb_typeof(fs.growth_assumptions) = 'object' THEN fs.growth_assumptions ELSE '{}'::jsonb END)
) assumption
ON CONFLICT (scenario_id, assumption_key, sequence_order) DO UPDATE SET
    value = EXCLUDED.value,
    source_type = EXCLUDED.source_type,
    source_ref = EXCLUDED.source_ref;

-- Normalize role permission objects when legacy permissions are an array of
-- {resource, action} objects. Invalid legacy entries remain in the snapshot
-- and are reported by the data-quality inventory rather than being invented.
INSERT INTO role_permission (role_assignment_id, resource, action)
SELECT ra.id, permission->>'resource', permission->>'action'
FROM role_assignment ra
CROSS JOIN LATERAL jsonb_array_elements(
    CASE WHEN jsonb_typeof(ra.permissions) = 'array' THEN ra.permissions ELSE '[]'::jsonb END
) permission
WHERE permission->>'resource' IS NOT NULL
  AND permission->>'action' IS NOT NULL
ON CONFLICT (role_assignment_id, resource, action) DO NOTHING;

INSERT INTO farmer_crop (farmer_id, crop_id, role, source_ref)
SELECT fp.id, c.id, 'primary', 'farmer_profile.primary_crops'
FROM farmer_profile fp
CROSS JOIN LATERAL unnest(fp.primary_crops) crop_name
JOIN crop c ON lower(c.name) = lower(crop_name)
ON CONFLICT (farmer_id, crop_id, season_key) DO NOTHING;

CREATE OR REPLACE VIEW v_metric_value_provenance AS
SELECT mv.id AS metric_value_id,
       mv.metric_id,
       mv.location_id,
       mv.period_start,
       mv.period_end,
       mvs.source_entity_type,
       mvs.source_entity_id,
       mvs.source_ref,
       mvs.contribution_role,
       mvs.sequence_order
FROM metric_value mv
JOIN metric_value_source mvs ON mvs.metric_value_id = mv.id;

CREATE OR REPLACE VIEW v_role_assignment_permissions AS
SELECT ra.id AS role_assignment_id,
       ra.farmer_id,
       ra.location_id,
       ra.role,
       rp.resource,
       rp.action,
       rp.status
FROM role_assignment ra
JOIN role_permission rp ON rp.role_assignment_id = ra.id;

CREATE OR REPLACE FUNCTION validate_party_scope_reference()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.scope_type = 'network' THEN
        IF NEW.scope_id IS NOT NULL THEN
            RAISE EXCEPTION '% scope_id must be NULL for network scope', TG_TABLE_NAME;
        END IF;
        RETURN NEW;
    END IF;

    IF NEW.scope_id IS NULL THEN
        RAISE EXCEPTION '% scope_id is required for % scope', TG_TABLE_NAME, NEW.scope_type;
    END IF;

    IF NEW.scope_type = 'organization' AND NOT EXISTS (SELECT 1 FROM organization WHERE id = NEW.scope_id) THEN
        RAISE EXCEPTION 'unknown organization scope %', NEW.scope_id;
    ELSIF NEW.scope_type = 'location' AND NOT EXISTS (SELECT 1 FROM location WHERE id = NEW.scope_id) THEN
        RAISE EXCEPTION 'unknown location scope %', NEW.scope_id;
    ELSIF NEW.scope_type = 'farm' AND NOT EXISTS (SELECT 1 FROM farm WHERE id = NEW.scope_id) THEN
        RAISE EXCEPTION 'unknown farm scope %', NEW.scope_id;
    ELSIF NEW.scope_type = 'cooperative' AND NOT EXISTS (SELECT 1 FROM cooperative WHERE id = NEW.scope_id) THEN
        RAISE EXCEPTION 'unknown cooperative scope %', NEW.scope_id;
    ELSIF NEW.scope_type = 'value_stream' AND NOT EXISTS (SELECT 1 FROM value_stream_definition WHERE id = NEW.scope_id) THEN
        RAISE EXCEPTION 'unknown value-stream scope %', NEW.scope_id;
    ELSIF NEW.scope_type = 'initiative' AND NOT EXISTS (SELECT 1 FROM strategy_initiative WHERE id = NEW.scope_id) THEN
        RAISE EXCEPTION 'unknown initiative scope %', NEW.scope_id;
    ELSIF NEW.scope_type = 'decision' AND NOT EXISTS (SELECT 1 FROM stakeholder_decision WHERE id = NEW.scope_id) THEN
        RAISE EXCEPTION 'unknown decision scope %', NEW.scope_id;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_party_relationship_scope_reference ON party_relationship;
CREATE CONSTRAINT TRIGGER trg_party_relationship_scope_reference
AFTER INSERT OR UPDATE OF scope_type, scope_id ON party_relationship
DEFERRABLE INITIALLY IMMEDIATE
FOR EACH ROW EXECUTE FUNCTION validate_party_scope_reference();

DROP TRIGGER IF EXISTS trg_stakeholder_interest_scope_reference ON stakeholder_interest;
CREATE CONSTRAINT TRIGGER trg_stakeholder_interest_scope_reference
AFTER INSERT OR UPDATE OF scope_type, scope_id ON stakeholder_interest
DEFERRABLE INITIALLY IMMEDIATE
FOR EACH ROW EXECUTE FUNCTION validate_party_scope_reference();

CREATE OR REPLACE FUNCTION validate_strategy_advantage_link_target()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.entity_type = 'capability' AND NOT EXISTS (SELECT 1 FROM business_capability WHERE id = NEW.entity_id) THEN
        RAISE EXCEPTION 'unknown capability target %', NEW.entity_id;
    ELSIF NEW.entity_type = 'process' AND NOT EXISTS (SELECT 1 FROM process_map WHERE id = NEW.entity_id) THEN
        RAISE EXCEPTION 'unknown process target %', NEW.entity_id;
    ELSIF NEW.entity_type = 'service' AND NOT EXISTS (SELECT 1 FROM service_registry WHERE id = NEW.entity_id) THEN
        RAISE EXCEPTION 'unknown service target %', NEW.entity_id;
    ELSIF NEW.entity_type = 'value_stream' AND NOT EXISTS (SELECT 1 FROM value_stream_definition WHERE id = NEW.entity_id) THEN
        RAISE EXCEPTION 'unknown value-stream target %', NEW.entity_id;
    ELSIF NEW.entity_type = 'strategy_choice' AND NOT EXISTS (SELECT 1 FROM strategy_choice WHERE id = NEW.entity_id) THEN
        RAISE EXCEPTION 'unknown strategy-choice target %', NEW.entity_id;
    ELSIF NEW.entity_type = 'investment' AND NOT EXISTS (SELECT 1 FROM strategy_investment_case WHERE id = NEW.entity_id) THEN
        RAISE EXCEPTION 'unknown investment target %', NEW.entity_id;
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_strategy_advantage_link_target ON strategy_advantage_link;
CREATE CONSTRAINT TRIGGER trg_strategy_advantage_link_target
AFTER INSERT OR UPDATE OF entity_type, entity_id ON strategy_advantage_link
DEFERRABLE INITIALLY IMMEDIATE
FOR EACH ROW EXECUTE FUNCTION validate_strategy_advantage_link_target();

DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM party_relationship
        WHERE scope_type = 'network' AND scope_id IS NOT NULL
    ) THEN
        RAISE EXCEPTION 'party_relationship contains network rows with scope IDs';
    END IF;
END;
$$;

COMMENT ON VIEW v_metric_value_provenance IS 'Normalized metric provenance projection for consumers migrating from source_record_ids';
COMMENT ON VIEW v_role_assignment_permissions IS 'Normalized role permissions projection for consumers migrating from permissions JSON';
