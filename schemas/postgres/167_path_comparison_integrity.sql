BEGIN;

ALTER TABLE backcast_path_comparison
    ADD COLUMN IF NOT EXISTS evaluation_status VARCHAR(20) NOT NULL DEFAULT 'not_evaluated',
    ADD COLUMN IF NOT EXISTS score_completeness JSONB NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS scoring_version VARCHAR(20) NOT NULL DEFAULT 'v2',
    ADD COLUMN IF NOT EXISTS evaluated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE backcast_path_comparison
    DROP CONSTRAINT IF EXISTS chk_backcast_path_evaluation_status;
ALTER TABLE backcast_path_comparison
    ADD CONSTRAINT chk_backcast_path_evaluation_status
    CHECK (evaluation_status IN ('not_evaluated', 'incomplete', 'complete', 'indeterminate'));

ALTER TABLE backcast_path_comparison
    DROP CONSTRAINT IF EXISTS fk_backcast_path_winner_narrative;
ALTER TABLE backcast_path_comparison
    ADD CONSTRAINT fk_backcast_path_winner_narrative
    FOREIGN KEY (winner_narrative_id) REFERENCES threat_narrative(id)
    ON DELETE SET NULL NOT VALID;

UPDATE backcast_path_comparison
SET evaluation_status = 'incomplete', scoring_version = 'v1'
WHERE auto_scores <> '{}'::jsonb
   OR manual_scores <> '{}'::jsonb
   OR final_scores <> '{}'::jsonb;

CREATE TABLE IF NOT EXISTS backcast_path_premortem (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    comparison_id UUID NOT NULL REFERENCES backcast_path_comparison(id) ON DELETE CASCADE,
    narrative_id UUID NOT NULL REFERENCES threat_narrative(id) ON DELETE CASCADE,
    failure_modes JSONB NOT NULL DEFAULT '[]'::jsonb,
    assumptions JSONB NOT NULL DEFAULT '[]'::jsonb,
    early_warning_signals JSONB NOT NULL DEFAULT '[]'::jsonb,
    mitigations JSONB NOT NULL DEFAULT '[]'::jsonb,
    residual_risk_notes TEXT,
    evidence_notes TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'draft',
    submitted_by VARCHAR(100),
    submitted_at TIMESTAMPTZ,
    verified_by UUID,
    verified_at TIMESTAMPTZ,
    verification_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (comparison_id, narrative_id),
    CONSTRAINT chk_path_premortem_status
        CHECK (status IN ('draft', 'submitted', 'verified', 'rejected')),
    CONSTRAINT chk_path_premortem_json
        CHECK (
            jsonb_typeof(failure_modes) = 'array'
            AND jsonb_typeof(assumptions) = 'array'
            AND jsonb_typeof(early_warning_signals) = 'array'
            AND jsonb_typeof(mitigations) = 'array'
        ),
    CONSTRAINT chk_path_premortem_submission
        CHECK (status <> 'submitted' OR (submitted_by IS NOT NULL AND submitted_at IS NOT NULL)),
    CONSTRAINT chk_path_premortem_verification
        CHECK (
            status <> 'verified'
            OR (submitted_at IS NOT NULL AND verified_by IS NOT NULL
                AND verified_at IS NOT NULL AND verified_at >= submitted_at)
        )
);

CREATE INDEX IF NOT EXISTS idx_path_premortem_comparison
    ON backcast_path_premortem(comparison_id);
CREATE INDEX IF NOT EXISTS idx_path_premortem_status
    ON backcast_path_premortem(status, updated_at);

DROP VIEW IF EXISTS v_backcast_path_comparison_summary;
CREATE VIEW v_backcast_path_comparison_summary AS
SELECT
    bpc.id AS comparison_id,
    bpc.location_id,
    bpc.comparison_name,
    array_length(bpc.narrative_ids, 1) AS path_count,
    bpc.evaluation_status,
    bpc.score_completeness,
    bpc.scoring_version,
    bpc.evaluated_at,
    bpc.winner_narrative_id,
    bpc.winner_score,
    bpc.rationale,
    bpc.compared_by,
    bpc.created_at,
    bpc.updated_at,
    COALESCE(pm.premortem_path_count, 0) AS premortem_path_count,
    COALESCE(pm.verified_premortem_count, 0) AS verified_premortem_count,
    COALESCE(pm.verified_premortem_count, 0) = array_length(bpc.narrative_ids, 1)
        AS premortem_complete,
    nt.title AS winner_title
FROM backcast_path_comparison bpc
LEFT JOIN threat_narrative nt ON nt.id = bpc.winner_narrative_id
LEFT JOIN LATERAL (
    SELECT
        COUNT(DISTINCT p.narrative_id) AS premortem_path_count,
        COUNT(DISTINCT p.narrative_id) FILTER (WHERE p.status = 'verified')
            AS verified_premortem_count
    FROM backcast_path_premortem p
    WHERE p.comparison_id = bpc.id
) pm ON TRUE;

COMMIT;
