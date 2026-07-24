-- Tranche 2: generation-safe RDF rebuilds and concurrency-safe IRIs.
BEGIN;

CREATE TABLE IF NOT EXISTS rdf_graph_generation (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    graph_name VARCHAR(100) NOT NULL REFERENCES rdf_named_graph(name) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'building'
        CHECK (status IN ('building', 'active', 'superseded', 'failed')),
    source_cutoff TIMESTAMPTZ NOT NULL,
    triple_count BIGINT NOT NULL DEFAULT 0 CHECK (triple_count >= 0),
    content_hash VARCHAR(64),
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    CHECK (completed_at IS NULL OR completed_at >= started_at)
);

ALTER TABLE rdf_named_graph
    ADD COLUMN IF NOT EXISTS active_generation_id UUID,
    ADD COLUMN IF NOT EXISTS source_cutoff TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS content_hash VARCHAR(64);

ALTER TABLE rdf_triple ADD COLUMN IF NOT EXISTS generation_id UUID;
ALTER TABLE rdf_triple DROP CONSTRAINT IF EXISTS fk_rdf_triple_generation;
ALTER TABLE rdf_triple ADD CONSTRAINT fk_rdf_triple_generation
    FOREIGN KEY (generation_id) REFERENCES rdf_graph_generation(id) ON DELETE CASCADE;

-- Preserve pre-generation data as an active generation before new builders run.
DO $$
DECLARE graph_row RECORD; generation UUID;
BEGIN
    FOR graph_row IN SELECT name FROM rdf_named_graph LOOP
        SELECT id INTO generation FROM rdf_graph_generation
        WHERE graph_name = graph_row.name AND status = 'active' ORDER BY started_at DESC LIMIT 1;
        IF generation IS NULL THEN
            INSERT INTO rdf_graph_generation (graph_name, status, source_cutoff, triple_count, completed_at)
            SELECT graph_row.name, 'active', COALESCE(MAX(created_at), NOW()), COUNT(*), NOW()
            FROM rdf_triple WHERE graph_name = graph_row.name
            RETURNING id INTO generation;
            UPDATE rdf_triple SET generation_id = generation WHERE graph_name = graph_row.name AND generation_id IS NULL;
        END IF;
        UPDATE rdf_named_graph SET active_generation_id = generation,
            source_cutoff = COALESCE(source_cutoff, NOW()) WHERE name = graph_row.name;
    END LOOP;
END $$;

ALTER TABLE rdf_triple DROP CONSTRAINT IF EXISTS rdf_triple_subject_predicate_object_value_object_iri_graph_name_key;
DROP INDEX IF EXISTS rdf_triple_literal_unique;
DROP INDEX IF EXISTS rdf_triple_iri_unique;
CREATE UNIQUE INDEX IF NOT EXISTS uq_rdf_triple_generation_terms
    ON rdf_triple (generation_id, subject, predicate, object_value, object_iri, graph_name);
CREATE INDEX IF NOT EXISTS idx_rdf_triple_active_generation
    ON rdf_triple (graph_name, generation_id);

ALTER TABLE rdf_graph_generation DROP CONSTRAINT IF EXISTS fk_rdf_generation_named_graph;
ALTER TABLE rdf_graph_generation ADD CONSTRAINT fk_rdf_generation_named_graph
    FOREIGN KEY (graph_name) REFERENCES rdf_named_graph(name) ON DELETE CASCADE;
ALTER TABLE rdf_named_graph DROP CONSTRAINT IF EXISTS fk_rdf_named_graph_active_generation;
ALTER TABLE rdf_named_graph ADD CONSTRAINT fk_rdf_named_graph_active_generation
    FOREIGN KEY (active_generation_id) REFERENCES rdf_graph_generation(id) DEFERRABLE INITIALLY DEFERRED;
CREATE UNIQUE INDEX IF NOT EXISTS uq_rdf_graph_generation_active
    ON rdf_graph_generation(graph_name) WHERE status = 'active';

-- Existing installations may contain more than one current IRI. Keep the
-- newest version and make the invariant enforceable for future writes.
WITH ranked AS (
    SELECT id, ROW_NUMBER() OVER (PARTITION BY entity_type, entity_id ORDER BY version DESC, created_at DESC, id DESC) AS rank
    FROM iri_registry WHERE is_current = TRUE
)
UPDATE iri_registry SET is_current = FALSE
WHERE id IN (SELECT id FROM ranked WHERE rank > 1);
CREATE UNIQUE INDEX IF NOT EXISTS uq_iri_one_current
    ON iri_registry(entity_type, entity_id) WHERE is_current = TRUE;

COMMIT;
