-- Shared activation identity for typed graph, RDF, and IRI metadata.
BEGIN;

CREATE TABLE IF NOT EXISTS graph_rebuild_coordinator (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    status VARCHAR(20) NOT NULL DEFAULT 'building'
        CHECK (status IN ('building', 'active', 'failed')),
    source_cutoff TIMESTAMPTZ NOT NULL,
    requested_by VARCHAR(200) NOT NULL,
    typed_generation_id UUID,
    rdf_generation_id UUID,
    error_message TEXT,
    requested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    CHECK (completed_at IS NULL OR completed_at >= requested_at)
);

ALTER TABLE graph_projection_generation ADD COLUMN IF NOT EXISTS rebuild_id UUID;
ALTER TABLE rdf_graph_generation ADD COLUMN IF NOT EXISTS rebuild_id UUID;
ALTER TABLE iri_registry ADD COLUMN IF NOT EXISTS rebuild_id UUID;
ALTER TABLE iri_registry ADD COLUMN IF NOT EXISTS source_cutoff TIMESTAMPTZ;

ALTER TABLE graph_projection_generation DROP CONSTRAINT IF EXISTS fk_graph_generation_rebuild;
ALTER TABLE graph_projection_generation ADD CONSTRAINT fk_graph_generation_rebuild
    FOREIGN KEY (rebuild_id) REFERENCES graph_rebuild_coordinator(id) ON DELETE SET NULL;
ALTER TABLE rdf_graph_generation DROP CONSTRAINT IF EXISTS fk_rdf_generation_rebuild;
ALTER TABLE rdf_graph_generation ADD CONSTRAINT fk_rdf_generation_rebuild
    FOREIGN KEY (rebuild_id) REFERENCES graph_rebuild_coordinator(id) ON DELETE SET NULL;
ALTER TABLE iri_registry DROP CONSTRAINT IF EXISTS fk_iri_rebuild;
ALTER TABLE iri_registry ADD CONSTRAINT fk_iri_rebuild
    FOREIGN KEY (rebuild_id) REFERENCES graph_rebuild_coordinator(id) ON DELETE SET NULL;
ALTER TABLE graph_rebuild_coordinator DROP CONSTRAINT IF EXISTS fk_coordinator_typed_generation;
ALTER TABLE graph_rebuild_coordinator ADD CONSTRAINT fk_coordinator_typed_generation
    FOREIGN KEY (typed_generation_id) REFERENCES graph_projection_generation(id) DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE graph_rebuild_coordinator DROP CONSTRAINT IF EXISTS fk_coordinator_rdf_generation;
ALTER TABLE graph_rebuild_coordinator ADD CONSTRAINT fk_coordinator_rdf_generation
    FOREIGN KEY (rdf_generation_id) REFERENCES rdf_graph_generation(id) DEFERRABLE INITIALLY DEFERRED;

CREATE INDEX IF NOT EXISTS idx_graph_rebuild_status ON graph_rebuild_coordinator(status, requested_at DESC);
CREATE INDEX IF NOT EXISTS idx_graph_generation_rebuild ON graph_projection_generation(rebuild_id);
CREATE INDEX IF NOT EXISTS idx_rdf_generation_rebuild ON rdf_graph_generation(rebuild_id);
CREATE INDEX IF NOT EXISTS idx_iri_rebuild ON iri_registry(rebuild_id);

COMMIT;
