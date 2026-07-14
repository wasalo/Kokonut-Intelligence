BEGIN;

-- RDF terms must have exactly one object representation. Remove exact
-- duplicates before replacing the NULL-unsafe legacy unique constraint.
DELETE FROM rdf_triple duplicate
USING rdf_triple retained
WHERE duplicate.id > retained.id
  AND duplicate.subject = retained.subject
  AND duplicate.predicate = retained.predicate
  AND duplicate.graph_name = retained.graph_name
  AND duplicate.object_value IS NOT DISTINCT FROM retained.object_value
  AND duplicate.object_iri IS NOT DISTINCT FROM retained.object_iri
  AND duplicate.object_type IS NOT DISTINCT FROM retained.object_type;

ALTER TABLE rdf_triple
    DROP CONSTRAINT IF EXISTS rdf_triple_subject_predicate_object_value_object_iri_graph_name_key;
ALTER TABLE rdf_triple
    DROP CONSTRAINT IF EXISTS rdf_triple_subject_predicate_object_value_object_iri_graph_name;

ALTER TABLE rdf_triple
    DROP CONSTRAINT IF EXISTS chk_rdf_triple_object_term;
ALTER TABLE rdf_triple
    ADD CONSTRAINT chk_rdf_triple_object_term
    CHECK ((object_value IS NULL) <> (object_iri IS NULL));

CREATE UNIQUE INDEX IF NOT EXISTS rdf_triple_literal_unique
    ON rdf_triple (subject, predicate, object_value, object_type, graph_name)
    WHERE object_value IS NOT NULL AND object_iri IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS rdf_triple_iri_unique
    ON rdf_triple (subject, predicate, object_iri, graph_name)
    WHERE object_iri IS NOT NULL AND object_value IS NULL;

-- Evaluator identity is explicit and separate from Directus created_by.
ALTER TABLE attestation_record
    ADD COLUMN IF NOT EXISTS evaluator_id UUID REFERENCES evaluator(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_attestation_record_evaluator
    ON attestation_record (evaluator_id)
    WHERE evaluator_id IS NOT NULL;

-- Backfill only unambiguous source-attestation authorship already recorded by
-- the trust model. Ambiguous rows remain NULL for governed reconciliation.
WITH unambiguous AS (
    SELECT source_attestation_id, (ARRAY_AGG(evaluator_id ORDER BY evaluator_id))[1] AS evaluator_id
    FROM attestation_reference
    WHERE evaluator_id IS NOT NULL
    GROUP BY source_attestation_id
    HAVING COUNT(DISTINCT evaluator_id) = 1
)
UPDATE attestation_record attestation
SET evaluator_id = unambiguous.evaluator_id
FROM unambiguous
WHERE attestation.id = unambiguous.source_attestation_id
  AND attestation.evaluator_id IS NULL;

DROP VIEW IF EXISTS v_evaluator_trust_graph;
CREATE VIEW v_evaluator_trust_graph AS
SELECT
    reference.id AS reference_id,
    source_evaluator.id AS source_evaluator_id,
    source_evaluator.display_name AS source_name,
    source_evaluator.evaluator_type AS source_type,
    source_evaluator.trust_score AS source_trust,
    reference.reference_type AS edge_type,
    source_attestation.attestation_uid AS source_attestation_uid,
    target_attestation.attestation_uid AS target_attestation_uid,
    reference.strength AS edge_weight,
    reference.created_at
FROM attestation_reference reference
JOIN attestation_record source_attestation
  ON source_attestation.id = reference.source_attestation_id
JOIN attestation_record target_attestation
  ON target_attestation.id = reference.target_attestation_id
JOIN evaluator source_evaluator
  ON source_evaluator.id = reference.evaluator_id
WHERE reference.evaluator_id IS NOT NULL;

CREATE OR REPLACE VIEW v_evaluator_trust_edges AS
SELECT
    reference.id AS reference_id,
    source_attestation.evaluator_id AS source_evaluator_id,
    target_attestation.evaluator_id AS target_evaluator_id,
    reference.reference_type,
    reference.strength,
    reference.created_at
FROM attestation_reference reference
JOIN attestation_record source_attestation
  ON source_attestation.id = reference.source_attestation_id
JOIN attestation_record target_attestation
  ON target_attestation.id = reference.target_attestation_id
WHERE source_attestation.evaluator_id IS NOT NULL
  AND target_attestation.evaluator_id IS NOT NULL;

-- Cross-impact relationships and landscape edges are location-bound. Triggers
-- protect every writer without duplicating canonical location columns.
CREATE OR REPLACE FUNCTION enforce_threat_cross_impact_location()
RETURNS TRIGGER AS $$
DECLARE
    source_location UUID;
    target_location UUID;
BEGIN
    SELECT location_id INTO source_location FROM threat WHERE id = NEW.source_threat_id;
    SELECT location_id INTO target_location FROM threat WHERE id = NEW.target_threat_id;
    IF source_location IS NULL OR target_location IS NULL OR source_location <> target_location THEN
        RAISE EXCEPTION 'threat cross-impact endpoints must belong to the same location';
    END IF;
    IF NEW.source_threat_id = NEW.target_threat_id THEN
        RAISE EXCEPTION 'threat cross-impact self-loops are not allowed';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_threat_cross_impact_location ON threat_cross_impact;
CREATE TRIGGER trg_threat_cross_impact_location
BEFORE INSERT OR UPDATE OF source_threat_id, target_threat_id ON threat_cross_impact
FOR EACH ROW EXECUTE FUNCTION enforce_threat_cross_impact_location();

CREATE OR REPLACE FUNCTION enforce_landscape_edge_location()
RETURNS TRIGGER AS $$
DECLARE
    source_location UUID;
    target_location UUID;
BEGIN
    IF NEW.source_habitat_id IS NOT NULL THEN
        SELECT location_id INTO source_location FROM habitat_zone WHERE id = NEW.source_habitat_id;
        IF source_location IS DISTINCT FROM NEW.location_id THEN
            RAISE EXCEPTION 'corridor source habitat must belong to the corridor location';
        END IF;
    END IF;
    IF NEW.target_habitat_id IS NOT NULL THEN
        SELECT location_id INTO target_location FROM habitat_zone WHERE id = NEW.target_habitat_id;
        IF target_location IS DISTINCT FROM NEW.location_id THEN
            RAISE EXCEPTION 'corridor target habitat must belong to the corridor location';
        END IF;
    END IF;
    IF NEW.source_habitat_id IS NOT NULL
       AND NEW.source_habitat_id = NEW.target_habitat_id THEN
        RAISE EXCEPTION 'corridor self-loops are not allowed';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_wildlife_corridor_location ON wildlife_corridor;
CREATE TRIGGER trg_wildlife_corridor_location
BEFORE INSERT OR UPDATE OF location_id, source_habitat_id, target_habitat_id ON wildlife_corridor
FOR EACH ROW EXECUTE FUNCTION enforce_landscape_edge_location();

CREATE OR REPLACE FUNCTION enforce_buffer_habitat_location()
RETURNS TRIGGER AS $$
DECLARE
    habitat_location UUID;
BEGIN
    IF NEW.habitat_zone_id IS NOT NULL THEN
        SELECT location_id INTO habitat_location FROM habitat_zone WHERE id = NEW.habitat_zone_id;
        IF habitat_location IS DISTINCT FROM NEW.location_id THEN
            RAISE EXCEPTION 'buffer habitat must belong to the monitoring location';
        END IF;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_buffer_habitat_location ON buffer_zone_monitoring;
CREATE TRIGGER trg_buffer_habitat_location
BEFORE INSERT OR UPDATE OF location_id, habitat_zone_id ON buffer_zone_monitoring
FOR EACH ROW EXECUTE FUNCTION enforce_buffer_habitat_location();

COMMIT;
