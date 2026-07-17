-- Migration 306: make regional dimension score upserts deterministic.

BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS uq_regional_dimension_score_assessment_dimension
    ON regional_dimension_score (assessment_id, dimension_key);

COMMIT;
